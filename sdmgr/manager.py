import os
import asyncio
import aiodns
import orm
import socket
import signal

import importlib

from sdmgr.db import *

import logging
_logger = logging.getLogger(__name__)


async def fetch_records_from_dns(domain, type):
    resolver = aiodns.DNSResolver()
    try:
        rr = await resolver.query(domain, type)
        return [x.host for x in rr]
    except aiodns.error.DNSError as e:
        _logger.error(f"DNS error looking up domain {domain}: {e.__str__()}")
    except Exception as e:
        _logger.exception(e)
    return []

def handle_exception(loop, context):
    msg = context.get("exception", context["message"])
    logging.error(f"Caught exceptionin monitoring thread: {msg}")


class Manager:
    def __init__(self):
        self.registrar_agents = {}
        self.dns_agents = {}
        self.hosting_agents = {}
        self.waf_agents = {}

        # TODO: Connect to Google to fetch/verify the GSV codes via API?

    async def __init_agents(self):
        def import_agent(agent_module_name):
            try:
                agent_module = importlib.import_module(agent_module_name)
                agent_class = getattr(agent_module, "Agent")
                return agent_class(agentdata)
            except Exception as e:
                _logger.exception(e)
                return None

        try:
            coros = []

            _logger.debug("Initialising Registrar agents...")
            agents = await Registrar.objects.filter(active=True).all()
            for agentdata in agents:
                agent = import_agent(agentdata.agent_module)
                if agent != None:
                    coros.append(agent.start())
                    self.registrar_agents[agent.id] = agent

            _logger.debug("Initialising DNS provider agents...")
            agents = await DNSProvider.objects.filter(active=True).all()
            for agentdata in agents:
                agent = import_agent(agentdata.agent_module)
                if agent != None:
                    coros.append(agent.start())
                    self.dns_agents[agent.id] = agent

            _logger.debug("Initialising site hosting agents...")
            agents = await Hosting.objects.filter(active=True).all()
            for agentdata in agents:
                agent = import_agent(agentdata.agent_module)
                if agent != None:
                    coros.append(agent.start())
                    self.hosting_agents[agent.id] = agent

            _logger.debug("Initialising WAF provider agents...")
            agents = await WAFProvider.objects.filter(active=True).all()
            for agentdata in agents:
                agent = import_agent(agentdata.agent_module)
                if agent != None:
                    coros.append(agent.start())
                    self.waf_agents[agent.id] = agent

            _logger.debug("Starting agents...")
            for coro in coros:
                await coro
            _logger.debug("Started agents.")

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
            domains = [x.name for x in await Domain.objects.all()]
            _logger.info(f"Total known domains: {len(domains)}")

            # Get metrics for 'registered but not hosted' (i.e. holding domains)
            #domains_to_create = []

            # Get metrics for 'hosted but not registered' (i.e. expired/misconfig)

            # For all registered and hosted domains...

        except Exception as e:
            _logger.exception(e)


    async def check_all_active_domains(self):
        _logger.info(f"Checking all active domains...")

        try:
            # Get list of known domains (in our state db)...
            domains = await Domain.objects.filter(active=True).all()
            _logger.info(f"Checking {len(domains)} active domains.")
            for domain in domains:
                asyncio.create_task(self.check_domain(domain))

        except Exception as e:
            _logger.exception(e)


    async def check_domain(self, domain):
        try:
            await domain.load()
            _logger.info(f"Checking domain '{domain.name}'...")
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
            asyncio.create_task(self.check_domain_ns_records(domain))

            # Check the site hosting details for the domain
            asyncio.create_task(self.check_domain_a_records(domain))

            # Check the WAF details
            #await self.check_domain_waf(domain)

            # Check the site hosting details for the domain
            #await self.check_site_ssl_certs(domain.site)

            # Check that the Google Site Verification code is in place
            #await self.check_domain_google_site_verification(domain)

            return "OK"
        except Exception as e:
            _logger.exception(e)


    async def check_domain_ns_records(self, domain):
        if domain.dns is None:
            _logger.warning(f"No DNS configured for domain '{domain.name}'.")
            return f"No DNS configured for domain '{domain.name}'."

        try:
            agent = self.dns_agents[domain.dns.id]
            _logger.debug(f"Checking DNS NS records for {domain.name} with {agent.label}...")
        except KeyError:
            _logger.warning(f"No DNS provider assigned for '{domain.name}'.")
            return f"No DNS provider assigned for '{domain.name}'."

        def resolve(hostname):
            return socket.gethostbyname(hostname)

        # Create domain via DNS provider if necessary
        try:
            r53_ns = await agent.get_ns_records(domain.name)
            if len(r53_ns) < 4:
                _logger.warning("Unexpected number of NS entries.")
            if len(r53_ns) < 1:
                _logger.notice(f"Creating missing DNS zone for '{domain.name}' with {agent.label}...")
                await agent.create_domain(domain.name)
                r53_ns = await agent.get_ns_records(domain.name)
            r53_ns_resolved = [resolve(x) for x in r53_ns]

        except Exception as e:
            _logger.exception(e)
            return str(e)

        # What do public nameservers tell us?
        dns_ns = []
        dns_ns_resolved = []
        dns_ns = await fetch_records_from_dns(domain.name, 'NS')
        dns_ns_resolved = [resolve(x) for x in dns_ns]

        # If they match, job done.
        if len(dns_ns) > 0 and set(r53_ns_resolved) == set(dns_ns_resolved):
            _logger.info(f"DNS NS records for {domain.name} with {agent.label} as expected.")
            return "OK"

        # Otherwise, something needs to be done about it
        _logger.warning(f"NS records for '{domain.name}' not configured correctly.")

        # Ensure NS records are set with registrar
        registrar_agent = self.registrar_agents[domain.registrar.id]
        await registrar_agent.set_ns_records(domain, r53_ns)
        _logger.warning(f"Update of NS records for '{domain.name}' requested via {registrar_agent.label}.")
        return f"Request to update NS records sent via {registrar_agent.label}."

    async def check_domain_a_records(self, domain):
        try:
            if domain.dns is None:
                _logger.error(f"No DNS configured for domain '{domain.name}'.")
                return f"No DNS configured for domain '{domain.name}'."

            try:
                agent = self.dns_agents[domain.dns.id]
                _logger.debug(f"Checking DNS A records for {domain.name} with {agent.label}...")
            except KeyError:
                _logger.error(f"No DNS provider assigned for '{domain.name}'.")
                return f"No DNS provider assigned for '{domain.name}'."

            hosting_ips = await self.fetch_hosting_ips_for_domain(domain)
            if len(hosting_ips) < 1:
                _logger.info(f"No hosting IPs to set for '{domain.name}'.")
                return f"No hosting IPs to set for '{domain.name}'."

            async def dns_a_record_already_set(a_record):
                dns_a = await fetch_records_from_dns(a_record, 'A')
                return len(dns_a) > 0 and set(dns_a) == set(hosting_ips)

            changes_made = False

            # Check/manage apex record
            if domain.update_apex:
                a_record = domain.name
                if await dns_a_record_already_set(a_record):
                    _logger.info(f"DNS apex record for {a_record} with {agent.label} as expected.")
                else:
                    await agent.create_new_a_rr(domain.name, a_record, hosting_ips)
                    _logger.info(f"DNS apex record for {a_record} updated to {hosting_ips}.")
                    changes_made = True

            # Check/manage additional 'A' records as specified (typically 'www')
            if len(domain.update_a_records) > 0:
                for prefix in domain.update_a_records.split(","):
                    a_record = f"{prefix}.{domain.name}"
                    if await dns_a_record_already_set(a_record):
                        _logger.info(f"DNS A record for {a_record} with {agent.label} as expected.")
                    else:
                        await agent.create_new_a_rr(domain.name, a_record, hosting_ips)
                        _logger.info(f"DNS A record for {a_record} updated to {hosting_ips}.")
                        changes_made = True

            return "OK" if not changes_made else "DNS updates applied."
        except Exception as e:
            _logger.exception(e)

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

    async def check_domain_waf(self, domain):
        _logger.debug(f"Checking domain WAF for {domain.name}...")
        waf = self.waf_agents[domain.waf.id]

        # Obtain the IP(s) the WAF should be pointing from site hosting
        site = await Site.objects.get(id = domain.site.id)
        hosting_agent = self.hosting_agents[site.hosting.id]
        _logger.debug(f"Looking up IPs for '{site.label}' site from host '{hosting_agent.label}'...")
        hosting_ips = await hosting_agent.fetch_ips_for_site(site)
        _logger.info(f"Found IPs for '{site.label}': {hosting_ips}")

        # Obtain the hostnames the WAF *is* listening/filtering/proxying
        # HTTP requests for
        _logger.debug(f"Looking up current aliases for '{site.label}' site...")
        current_aliases = await self.get_current_aliases_for_site(site)
        _logger.info(f"Found {len(current_aliases)} current aliases for '{site.label}'.")

        # Obtain the hostnames the WAF should be listening/filtering/proxying
        # HTTP requests for
        _logger.debug(f"Looking up expected aliases for '{site.label}' site...")
        expected_aliases = await self.get_expected_aliases_for_site(site)
        _logger.info(f"Found {len(expected_aliases)} expected aliases for '{site.label}'.")

        # Update hosting config if lists differ
        if len(current_aliases) != len(expected_aliases):
            await self.update_aliases_for_site(site, expected_aliases)

        # Check the WAF provider has correct details for the domain
        _logger.info(f"Checking WAF aliases for site {site.label}...")
        status = await waf.apply_configuration(site.label, domain.name, expected_aliases, hosting_ips)
        return status

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

    async def get_expected_aliases_for_site(self, site):
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
        if domain.site.id is None:
            return []
        if domain.waf.id is not None:
            waf_agent = self.waf_agents[domain.waf.id]
            return await waf_agent.fetch_ips_for_site(domain.site)
        else:
            hosting_agent = self.hosting_agents[domain.site.hosting.id]
            return await hosting_agent.fetch_ips_for_site(domain.site)

    async def get_current_aliases_for_site(self, site):
        hosting_agent = self.hosting_agents[site.hosting.id]
        return await hosting_agent.fetch_aliases_for_site(site)

    async def update_aliases_for_site(self, site, aliases):
        hosting_agent = self.hosting_agents[site.hosting.id]
        return await hosting_agent.update_aliases_for_site(site, aliases)

    async def run(self):
        # Create an instance for each agent
        await self.__init_agents()

        # Prepare the main manager loop
        async def monitoring_loop(frequency):
            _logger.info("Starting monitoring event loop, to run every {frequency} secs.")
            try:
                while True:
                    asyncio.create_task(self.check_all_active_domains())
                    await asyncio.sleep(frequency)
            except Exception as e:
                _logger.exception(e)

        frequency = int(os.getenv("MANAGER_LOOP_SECS", "0"))
        if frequency > 0:
            asyncio.create_task(monitoring_loop(frequency))
