import os
import asyncio
import aiodns
import orm
import socket
import signal
import datetime

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


class ManagerStatusCheck:
    _check_id: str
    startTime: datetime.datetime
    endTime: datetime.datetime = None
    success: bool = False
    output: str = None

    def __init__(self, _cls_type, _cls_id, _check_id):
        self._check_id = f"{_cls_type}:{_cls_id}:{_check_id}"
        self.startTime = datetime.datetime.now()

    async def success(self, output = "OK"):
        self.endTime = datetime.datetime.now()
        self.success = True
        self.output = output
        await self._finish()

    async def error(self, output):
        self.endTime = datetime.datetime.now()
        self.success = False
        self.output = output
        await self._finish()

    async def _finish(self):
        # If no last status for this check, create it
        try:
            last_status = await StatusCheck.objects.get(_check_id = self._check_id)
        except orm.exceptions.NoMatch:
            last_status = await StatusCheck.objects.create(
                _check_id = self._check_id,
                startTime = self.startTime,
                endTime = self.endTime,
                success = self.success,
                output = str(self.output)
            )

        # If status has changed, log an audit entry
        hash1 = (str(self.success) + self.output)
        hash2 = (str(last_status.success) + last_status.output)
        if hash1 != hash2:
            self.audit(last_status)

        # Write new status to database
        await last_status.update(
                startTime = self.startTime,
                endTime = self.endTime,
                success = self.success,
                output = self.output
            )

    # TODO: Ensure this is pushed to ElasticSearch and/or Discord somehow
    def audit(self, last_status):
        _logger.info(f"Status for check '{self._check_id}' now '{self.output}'.")


class Manager:
    def __init__(self):
        self.registrar_agents = {}
        self.dns_agents = {}
        self.hosting_agents = {}
        self.waf_agents = {}

        # TODO: Connect to Google to fetch/verify the GSV codes via API?

    async def __init_agents(self):
        def import_agent(agent_module_name):
            agent_module = importlib.import_module(agent_module_name)
            agent_class = getattr(agent_module, "Agent")
            return agent_class(agentdata)

        coros = []

        _logger.debug("Initialising Registrar agents...")
        agents = await Registrar.objects.filter(active=True).all()
        for agentdata in agents:
            agent = import_agent(agentdata.agent_module)
            coros.append(agent.start())
            self.registrar_agents[agent.id] = agent

        _logger.debug("Initialising DNS provider agents...")
        agents = await DNSProvider.objects.filter(active=True).all()
        for agentdata in agents:
            agent = import_agent(agentdata.agent_module)
            coros.append(agent.start())
            self.dns_agents[agent.id] = agent

        _logger.debug("Initialising site hosting agents...")
        agents = await Hosting.objects.filter(active=True).all()
        for agentdata in agents:
            agent = import_agent(agentdata.agent_module)
            coros.append(agent.start())
            self.hosting_agents[agent.id] = agent

        _logger.debug("Initialising WAF provider agents...")
        agents = await WAFProvider.objects.filter(active=True).all()
        for agentdata in agents:
            agent = import_agent(agentdata.agent_module)
            coros.append(agent.start())
            self.waf_agents[agent.id] = agent

        _logger.info(f"Starting {len(coros)} agents...")
        results = await asyncio.gather(*coros)
        _logger.info("Started agents.")

    # TODO: Finish testing/documenting etc
    async def metrics(self):
        """
        Return an array of metrics for presentation (i.e. to Prometheus)
        """

        metrics = {}

        # Count of known domains (in our state db)...
        metrics["total_domains"] = len(await Domain.objects.all())

        # Count of hosted/registered domains (on Marcaria, Namecheap, IONOS)...
        metrics["registrar_registered_domains"] = len(await self.gather_registered_domains())

        # Count of domains hosted via DNS (on Route53, CloudFlare etc)...
        metrics["dns_hosted_domains"] = len(await self.gather_hosted_domains())

        # TODO: Statuscheck metrics breakdown

        # Summary count of active agents
        metrics["agent_counts"] = {
            "registrar": len(self.registrar_agents),
            "dns": len(self.dns_agents),
            "hosting": len(self.hosting_agents),
            "waf": len(self.waf_agents)
        }

        return metrics

    async def _fetch_dns_agent(self, domain):
        try:
            return (self.dns_agents[domain.dns.id], None)
        except AttributeError:
            return (None, f"DNS provider not configured.")
        except KeyError:
            return (None, f"DNS provider '{domain.dns}' agent not loaded.")

    # TODO: Finish testing/documenting.
    async def check_all_active_domains(self):
        """
        Check all active domains in a certain order. Intended to be run on a schedule.
        """
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
        """
        Triggers the various checks for the given domain.
        """

        _logger.info(f"Checking domain '{domain.name}'...")

        tasks = []

        tasks.append(asyncio.create_task(self.check_domain_ns_records(domain)))
        tasks.append(asyncio.create_task(self.check_domain_a_records(domain)))
        # [TODO] Other checks...

        for task in tasks:
            try:
                await task
            except Exception as e:
                _logger.exception(e)

    async def apply_domain(self, domain):
        """
        Triggers the domain checks for the given domain.
        """

        tasks = []

        #tasks.append(asyncio.create_task(self.apply_domain_ns_records(domain)))
        tasks.append(asyncio.create_task(self.apply_domain_a_records(domain)))
        # [TODO] Other checks...

        for task in tasks:
            try:
                await task
            except Exception as e:
                _logger.exception(e)

    async def check_domain_ns_records(self, domain):
        status = ManagerStatusCheck("domain", domain.name, "ns_records")
        (dns_agent, error) = await self._fetch_dns_agent(domain)
        if error is not None:
            return await status.error(error)

        def resolve(hostname):
            return socket.gethostbyname(hostname)

        # Fetch the records the DNS provider says they should be set to
        try:
            _logger.info(f"Retrieving intended NS records for {domain.name} from {dns_agent.label}...")
            agent_ns = await dns_agent.get_ns_records(domain.name)
            if len(agent_ns) < 1:
                return await status.error(f"DNS provider for domain '{domain.name}' has no NS records.")
            agent_ns_resolved = [resolve(x) for x in agent_ns]

        except Exception as e:
            _logger.exception(e)
            return await status.error(f"Exception occurred while looking up NS records for domain '{domain.name}': {str(e)}")

        # What do public nameservers tell us the NS are currently set to?
        dns_ns = await fetch_records_from_dns(domain.name, 'NS')
        dns_ns_resolved = [resolve(x) for x in dns_ns]

        # If they don't match, action will be required.
        if len(dns_ns) <= 0 or set(agent_ns_resolved) != set(agent_ns_resolved):
            agent_ns_list = ",".join(agent_ns)
            return await status.error(f"NS records set incorrectly")

        # Otherwise, things look hunky-dorey NS record wise.
        return await status.success()

    async def check_domain_a_records(self, domain):
        status = ManagerStatusCheck("domain", domain.name, "a_records")
        (dns_agent, error) = await self._fetch_dns_agent(domain)
        if error is not None:
            return await status.error(error)

        hosting_ips = await self.fetch_hosting_ips_for_domain(domain)
        if len(hosting_ips) < 1:
            return await status.error(f"No hosting IPs to set for '{domain.name}'.")

        async def dns_a_record_already_set(a_record):
            dns_a = await fetch_records_from_dns(a_record, 'A')
            return len(dns_a) > 0 and set(dns_a) == set(hosting_ips)

        # Check/manage apex record
        if domain.update_apex:
            a_record = domain.name
            if await dns_a_record_already_set(a_record):
                _logger.info(f"DNS apex record for '{domain.name}' with {dns_agent.label} resolves to expected hosting IPs.")
            else:
                return status.error(f"DNS apex record for '{domain.name}' does not resolve to expected hosting IPs.")

        # Check/manage additional 'A' records as specified (typically 'www')
        if len(domain.update_a_records) > 0:
            for prefix in domain.update_a_records.split(","):
                a_record = f"{prefix}.{domain.name}"
                if await dns_a_record_already_set(a_record):
                    _logger.info(f"DNS A record for '{a_record}' with {dns_agent.label} resolves to expected hosting IPs.")
                else:
                    return await status.error(f"DNS A record for '{a_record}' does not resolve to expected hosting IPs.")

        # Otherwise, things look hunky-dorey A record wise.
        return status.success()

    async def apply_domain_a_records(self, domain):
        (dns_agent, error) = await self._fetch_dns_agent(domain)
        if error is not None:
            return error

        hosting_ips = await self.fetch_hosting_ips_for_domain(domain)
        if len(hosting_ips) < 1:
            return f"No hosting IPs found."

        async def dns_a_record_already_set(a_record):
            dns_a = await fetch_records_from_dns(a_record, 'A')
            return len(dns_a) > 0 and set(dns_a) == set(hosting_ips)

        # Check/manage apex record
        if False: #domain.update_apex:
            a_record = domain.name
            _logger.info(f"Updating DNS apex record '{a_record}' with {dns_agent.label}...")
            await dns_agent.create_new_a_rr(domain, a_record, hosting_ips)

        # Check/manage additional 'A' records as specified (typically 'www')
        if len(domain.update_a_records) > 0:
            for prefix in domain.update_a_records.split(","):
                a_record = f"{prefix}.{domain.name}"
                _logger.info(f"Updating DNS A record '{a_record}' with {dns_agent.label}...")
                await dns_agent.create_new_a_rr(domain, a_record, hosting_ips)

    async def check_domain_google_site_verification(self, domain):
        if domain.google_site_verification is not None:
            _logger.debug(f"Checking Google Site Verification code for {domain.name}...")
            agent = self.dns_agents[domain.dns.id]
            await agent.set_google_site_verification(domain)

    # TODO: Complete...
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

    async def create_missing_dns_zone(self, domain, agent):
        _logger.notice(f"Creating missing DNS zone for '{domain.name}' with {agent.label}...")
        await agent.create_domain(domain.name)

    async def update_ns_records_with_registrar(self, domain, agent_ns):
        registrar_agent = self.registrar_agents[domain.registrar.id]
        _logger.notice(f"Requesting update of NS records for '{domain.name}' via {registrar_agent.label}...")
        await registrar_agent.set_ns_records(domain, agent_ns)

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
        try:
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

        except Exception as e:
            _logger.exception(e)
