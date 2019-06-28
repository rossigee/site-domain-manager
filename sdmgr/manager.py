#import threading
import asyncio
import orm
import dns.resolver
import socket

import importlib

from sdmgr.db import *

import logging
_logger = logging.getLogger(__name__)


def resolve(hostname):
    return socket.gethostbyname(hostname)

def fetch_records_from_dns(domain, type):
    entries = dns.resolver.query(domain, type)
    return [x.to_text() for x in entries]

class Manager:
    def __init__(self):
        self.registrar_agents = {}
        self.dns_agents = {}
        self.hosting_agents = {}
        self.waf_agents = {}

        self.taskq = asyncio.Queue()

        # TODO: Connect to Google to fetch/verify the GSV codes via API?


    async def __init_agents(self):
        try:
            coros = []

            _logger.debug("Initialising Registrar agents...")
            agents = await Registrar.objects.filter(active=True).all()
            for agentdata in agents:
                agent_module = importlib.import_module(agentdata.agent_module)
                agent_class = getattr(agent_module, "Agent")
                agent = agent_class(agentdata)
                coros.append(agent.start())
                self.registrar_agents[agent.id] = agent

            _logger.debug("Initialising DNS provider agents...")
            agents = await DNSProvider.objects.filter(active=True).all()
            for agentdata in agents:
                agent_module = importlib.import_module(agentdata.agent_module)
                agent_class = getattr(agent_module, "Agent")
                agent = agent_class(agentdata)
                coros.append(agent.start())
                self.dns_agents[agent.id] = agent

            _logger.debug("Initialising site hosting agents...")
            agents = await Hosting.objects.filter(active=True).all()
            for agentdata in agents:
                agent_module = importlib.import_module(agentdata.agent_module)
                agent_class = getattr(agent_module, "Agent")
                agent = agent_class(agentdata)
                coros.append(agent.start())
                self.hosting_agents[agent.id] = agent

            _logger.debug("Initialising WAF provider agents...")
            agents = await WAFProvider.objects.filter(active=True).all()
            for agentdata in agents:
                agent_module = importlib.import_module(agentdata.agent_module)
                agent_class = getattr(agent_module, "Agent")
                agent = agent_class(agentdata)
                coros.append(agent.start())
                self.waf_agents[agent.id] = agent

            _logger.debug("Starting agents...")
            # TODO: run simultaneously
            for coro in coros:
                await coro

        except Exception as e:
            _logger.exception(e)


    async def reconcile(self):
        _logger.info(f"Reconciling data sources...")

        try:
            # Get list of registered domains (Marcaria, Namecheap, IONOS)...
            registered_domains = await self.gather_registered_domains()
            _logger.info(f"Total registered domains: {len(registered_domains)}")

            # Get list of hosted domains (Route53)...
            hosted_domains = await self.gather_hosted_domains()
            _logger.info(f"Total hosted domains: {len(hosted_domains)}")

            # Get list of known domains (in our state db)...
            domains = [x.name for x in await Domain.objects.filter(active=True).all()]
            _logger.info(f"Total known domains: {len(domains)}")

            # Get metrics for 'registered but not hosted' (i.e. holding domains)
            domains_to_create = []

            # Get metrics for 'hosted but not registered' (i.e. expired/misconfig)

            # For all registered and hosted domains...

        except Exception as e:
            _logger.exception(e)


    async def check_domain(self, domain):
        await domain.load()
        if domain.site is None:
            raise Exception(f"No hosting configured for domain {domain.name}.")
        #await domain.site.load()
        if domain.waf is None:
            raise Exception(f"No WAF configured for domain {domain.name}.")
        #await domain.waf.load()

        # Check the registrar and hosting are as expected

            # Update if not

            # Report that we had to update it

        # Check the domain's NS records are under our control
        await self.check_domain_ns_records(domain)

        # Check the site hosting details for the domain
        await self.check_domain_a_records(domain)

        # Check the site hosting details for the domain
        await self.check_site_ssl_certs(domain.site)

        # Obtain the IP(s) the WAF should be pointing from site hosting
        _logger.debug(f"Looking up IPs for '{domain.site.label}' site...")
        hosting_ips = await self.fetch_ips_for_site(domain)
        _logger.info(f"Found IPs for '{domain.site.label}': {hosting_ips}")

        # Obtain the hostnames the WAF *is* listening/filtering/proxying
        # HTTP requests for
        _logger.debug(f"Looking up current aliases for '{domain.site.label}' site...")
        current_aliases = await self.fetch_aliases_for_site(domain.site)
        _logger.info(f"Found {len(current_aliases)} current aliases for '{domain.site.label}'.")

        # Obtain the hostnames the WAF should be listening/filtering/proxying
        # HTTP requests for
        _logger.debug(f"Looking up expected aliases for '{domain.site.label}' site...")
        expected_aliases = await self.gather_aliases_for_site(domain.site)
        _logger.info(f"Found {len(expected_aliases)} expected aliases for '{domain.site.label}'.")

        # Update hosting config if lists differ
        if len(current_aliases) != len(expected_aliases):
            await self.update_aliases_for_site(domain.site, expected_aliases)

        # Check the WAF provider has correct details for the domain
        await self.check_waf_provider_aliases(domain, expected_aliases, hosting_ips)

        # Check that the Google Site Verification code is in place
        await self.check_domain_google_site_verification(domain)

        return "OK"

    async def check_domain_ns_records(self, domain):
        if domain.dns is None:
            _logger.warning(f"No DNS configured for domain '{domain.name}'")

        try:
            agent = self.dns_agents[domain.dns.id]
            _logger.info(f"Checking DNS NS records for {domain.name} with {agent.label}...")
        except KeyError:
            _logger.warning(f"No DNS provider assigned for '{domain.name}'.")
            return "No DNS provider assigned to the domain."

        # Create domain via DNS provider if necessary
        try:
            r53_ns = await agent.get_ns_records(domain.name)
            if len(r53_ns) < 4:
                _logger.warning("Unexpected number of NS entries.")
            if len(r53_ns) < 1:
                _logger.warning(f"Creating missing DNS zone for '{domain.name}' with {agent.label}...")
                await agent.create_domain(domain.name)
                r53_ns = await agent.get_ns_records(domain.name)
            r53_ns_resolved = [resolve(x) for x in r53_ns]

        except Exception as e:
            _logger.exception(e)
            return str(e)

        # What do public nameservers tell us?
        dns_ns = []
        dns_ns_resolved = []
        try:
            dns_ns = fetch_records_from_dns(domain.name, 'NS')
            dns_ns_resolved = [resolve(x) for x in dns_ns]

            # If they match, job done.
            if len(dns_ns) > 0 and set(r53_ns_resolved) == set(dns_ns_resolved):
                _logger.info(f"DNS NS records for {domain.name} with {agent.label} as expected.")
                return "OK"

            # Otherwise, something needs to be done about it
            _logger.warning(f"NS records for '{domain.name}' not configured correctly.")

        except dns.resolver.NoAnswer:
            _logger.warning(f"No response for NS record lookup for '{domain.name}'.")

        except dns.resolver.NoNameservers:
            _logger.warning(f"Could not find NS records for '{domain.name}'.")

        # Ensure NS records are set with registrar
        registrar_agent = self.registrar_agents[domain.registrar.id]
        await registrar_agent.set_ns_records(domain, r53_ns)
        _logger.warning(f"Update of NS records for '{domain.name}' requested via {registrar_agent.label}.")
        return f"Request to update NS records sent via {registrar_agent.label}."

    async def check_domain_a_records(self, domain):
        if domain.dns is None:
            _logger.warning(f"No DNS configured for domain '{domain.name}'")

        try:
            agent = self.dns_agents[domain.dns.id]
            _logger.info(f"Checking DNS NS records for {domain.name} with {agent.label}...")
        except KeyError:
            _logger.warning(f"No DNS provider assigned for '{domain.name}'.")
            return "No DNS provider assigned to the domain."

        await domain.site.load()
        hosting_ips = await self.fetch_hosting_ips_for_domain(domain)

        def dns_a_record_already_set(a_record):
            try:
                dns_a = fetch_records_from_dns(a_record, 'A')
                return len(dns_a) > 0 and set(dns_a) == set(hosting_ips)
            except dns.resolver.NXDOMAIN:
                _logger.warning(f"Non-existent domain response for lookup for '{domain.name}'.")
            except dns.resolver.NoAnswer:
                _logger.warning(f"No response for apex A record lookup for '{domain.name}'.")
            except dns.resolver.NoNameservers:
                _logger.warning(f"Could not find apex A records for '{domain.name}'.")
            return False

        changes_made = False

        # Check/manage apex record
        if domain.update_apex:
            a_record = domain.name
            if dns_a_record_already_set(a_record):
                _logger.info(f"DNS apex record for {a_record} with {agent.label} as expected.")
            else:
                await agent.create_new_a_rr(domain.name, a_record, hosting_ips)
                _logger.info(f"DNS apex record for {a_record} updated to {hosting_ips}.")
                changes_made = True

        # Check/manage additional 'A' records as specified (typically 'www')
        if len(domain.update_a_records) > 0:
            for prefix in domain.update_a_records.split(","):
                a_record = f"{prefix}.{domain.name}"
                if dns_a_record_already_set(a_record):
                    _logger.info(f"DNS A record for {a_record} with {agent.label} as expected.")
                else:
                    await agent.create_new_a_rr(domain.name, a_record, hosting_ips)
                    _logger.info(f"DNS A record for {a_record} updated to {hosting_ips}.")
                    changes_made = True

        return "OK" if not changes_made else "DNS updates applied."

    async def check_waf_provider_aliases(self, domain, expected_aliases, hosting_ips):
        _logger.info(f"Checking WAF aliases for site {domain.site.label}...")
        waf_agent = self.waf_agents[domain.waf.id]
        await waf_agent.apply_configuration(domain.site.label, domain.name, expected_aliases, hosting_ips)

    async def check_domain_google_site_verification(self, domain):
        if domain.google_site_verification is not None:
            _logger.debug(f"Checking Google Site Verification code for {domain.name}...")
            agent = self.dns_agents[domain.dns.id]
            await agent.set_google_site_verification(domain)

    async def check_domain_contacts(self, domain):
        _logger.debug(f"Checking domain registration contacts for {domain.name}...")
        agent = self.registrar_agents[domain.registrar.id]
        details = await agent.get_contacts(domain)
        print(details)

    async def check_site_ssl_certs(self, site):
        if not site.active:
            return "Site not active."
        try:
            # Find the domains pointing at the site, by WAF
            alias_domains = await Domain.objects.filter(site=site, active=True).all()
            hostnames_by_waf = {}
            for d in alias_domains:
                if d.waf.id not in hostnames_by_waf.keys():
                    hostnames_by_waf[d.waf.id] = []
                if d.update_apex:
                    hostnames_by_waf[d.waf.id].append(d.name)
                if len(d.update_a_records) > 0:
                    for prefix in d.update_a_records.split(","):
                        hostnames_by_waf[d.waf.id].append(f"{prefix}.{d.name}")

            # For each WAFs involved, update it's list of SSL certs to manage
            failed_aliases = []
            for waf_id in hostnames_by_waf.keys():
                aliases = hostnames_by_waf[waf_id]
                waf = await WAFProvider.objects.get(id=waf_id)
                if not waf.active:
                    _logger.info(f"Ignoring inactive WAF {waf.label}.")
                    continue
                agent = self.waf_agents[waf_id]
                success = await agent.deploy_certificate(site.label, site.label, aliases)
                if success:
                    _logger.info(f"Updated SSL configuration to include {len(aliases)} hostnames for {waf.label} for {site.label}...")
                else:
                    failed_aliases.merge(aliases)

            if len(failed_aliases) > 0:
                return f"Failed to update SSL config for {len(failed_aliases)} aliases."
            else:
                return "OK"

        except Exception as e:
            _logger.exception(e)

    async def gather_registered_domains(self):
        registered_domains = []
        for id in self.registrar_agents:
            agent = self.registrar_agents[id]
            _logger.info(f"Gathering registered domains from {agent.label}...")
            registered_domains += await agent.get_registered_domains()
        return registered_domains

    async def gather_hosted_domains(self):
        hosted_domains = []
        for id in self.dns_agents:
            agent = self.dns_agents[id]
            _logger.info(f"Gathering hosted domains from {agent.label}...")
            hosted_domains += await agent.get_hosted_domains()
        return hosted_domains

    async def gather_aliases_for_site(self, site):
        aliases = []
        domainlist = await Domain.objects.filter(site = site, active=True).all()
        for d in domainlist:
            if d.update_apex:
                aliases.append(d.name)
            if len(d.update_a_records) > 0:
                for a in d.update_a_records.split(","):
                    aliases.append(f"{a}.{d.name}")
        if d.name in aliases:
            aliases.remove(d.name)
        return aliases

    async def fetch_hosting_ips_for_domain(self, domain):
        if domain.waf is not None:
            waf_agent = self.waf_agents[domain.waf.id]
            return await waf_agent.fetch_ips_for_site(domain.site)
        else:
            hosting_agent = self.hosting_agents[site.hosting.id]
            return await hosting_agent.fetch_ips_for_site(domain.site)

    async def fetch_aliases_for_site(self, site):
        hosting_agent = self.hosting_agents[site.hosting.id]
        return await hosting_agent.fetch_aliases_for_site(site)

    async def update_aliases_for_site(self, site, aliases):
        hosting_agent = self.hosting_agents[site.hosting.id]
        return await hosting_agent.update_aliases_for_site(site, aliases)

    async def run(self):
        # Create an instance for each agent
        await self.__init_agents()
