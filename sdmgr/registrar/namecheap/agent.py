from ..base import RegistrarAgent

import logging
_logger = logging.getLogger(__name__)

import os
import orm
import aiohttp
from xml.etree import ElementTree


class Namecheap(RegistrarAgent):
    def __init__(self, data):
        RegistrarAgent.__init__(self, data)
        _logger.info(f"Loading Namecheap registrar agent (id: {self.id}): {self.label}")

        #self.api_url = "https://api.sandbox.namecheap.com/xml.response"
        self.api_url = "https://api.namecheap.com/xml.response"
        self.api_user = os.getenv("NAMECHEAP_API_USER")
        self.api_token = os.getenv("NAMECHEAP_API_TOKEN")
        self.client_ip = os.getenv("NAMECHEAP_CLIENT_IP")

        self.domains = {}
        self.registrar = data

    async def _load_state(self):
        await super(Namecheap, self)._load_state()
        try:
            self.domains = self.state['domains']
            _logger.info(f"Restored state for {self.label} with {len(self.domains)} domains.")
        except:
            self.domains = {}
            _logger.info(f"Initialised state for {self.label}.")

    async def _save_state(self):
        self.state = {
            "domains": self.domains
        }
        await super(Namecheap, self)._save_state()

    async def start(self):
        try:
            _logger.debug(f"Starting Namecheap registrar agent (id: {self.id}).")
            await self._load_state()

            #await self.refresh_domains()

        except Exception as e:
            _logger.exception(e)

    def _get_url_prefix(self):
        return f"{self.api_url}/xml.response?ApiUser={self.api_user}&ApiKey={self.api_token}&UserName={api_user}&ClientIp={self.client_ip}"

    async def get_refresh_method(self):
        return "api"

    async def refresh(self):
        _logger.info(f"Refreshing list of domains managed on {self.label}...")
        domains = {}
        page_num = 0
        page_count = 1
        page_size = 100

        async def get_page(page_num):
            async with aiohttp.ClientSession() as session:
                url = self._get_url_prefix()
                url = f"{url}&Command=namecheap.domains.getList&PageSize={page_size}&Page={page_num}"
                async with session.get(url) as response:
                    if response.status != 200:
                        _logger.error(f"Unexpected response from Namecheap API: {response.status}")
                        return
                    xmlstring = await response.text()
            return xmlstring

        while page_num < page_count:
            page_num += 1
            xmlstring = await get_page(page_num)
            try:
                root = ElementTree.fromstring(xmlstring)
                for d in root.findall('.//{http://api.namecheap.com/xml.response}Domain'):
                    dname = d.attrib['Name']
                    domains[dname] = d.attrib
                total_items = int(root.findall('.//{http://api.namecheap.com/xml.response}TotalItems')[0].text)
                page_count = int((total_items - 1) / page_size) + 1
            except Exception as e:
                _logger.exception(e)
                return

        self.domains = domains

        _logger.info(f"Updated Namecheap registrar with {len(self.domains)} domains from their API.")

        # Record this in the 'state' field in the db
        await self._save_state()

        # Ensure domain records are present for all domains listed in this file
        await self._populate_domains()

        # Return count of domains for confirmation message
        return {
            "count": len(self.domains)
        }

    async def get_registered_domains(self):
        return self.domains.keys()

    async def get_status_for_domain(self, domainname):
        if domainname not in self.domains:
            return {
                'summary': f"No information for '{domainname}'"
            }
        domain = self.domains[domainname]
        return {
            'name': domainname,
            'summary': domain['status'],
            'expiry_date': domain['expiry_date'],
            'auto_renew': domain['auto_renew'],
        }

    async def set_ns_records(self, domain, nameservers):
        _logger.info(f"Updating the NS records on {self.label} for {domain.name}.")

        # Namecheap should really determine the SLD and TLD themselves at their
        # end, but hey ho, here we go.

        dnshosts = ",".join(nameservers)
        parts = domain.name.split(".")
        sld = parts[0]
        tld = ".".join(parts[1:])

        async with aiohttp.ClientSession() as session:
            url = self._get_url_prefix()
            url = f"{url}&Command=namecheap.domains.dns.setCustom&SLD={sld}&TLD={tld}&Nameservers={dnshosts}"
            async with session.get(url) as response:
                if response.status != 200:
                    _logger.error(f"Unexpected response from Namecheap API: {response.status}")
                    return
                xmlstring = await response.text()

        try:
            total_items = int(root.findall('.//{http://api.namecheap.com/xml.response}TotalItems')[0].text)
        except Exception as e:
            _logger.exception(e)
            return

    async def get_contacts(self, domain):
        _logger.info(f"Fetching domain registration contacts for {domain.name}.")

        async with aiohttp.ClientSession() as session:
            url = self._get_url_prefix()
            url = f"{url}&Command=namecheap.domains.getContacts&DomainName={domain.name}"
            async with session.get(url) as response:
                if response.status != 200:
                    _logger.error(f"Unexpected response from Namecheap API: {response.status}")
                    return
                xmlstring = await response.text()

        print(xmlstring)
        try:
            total_items = int(root.findall('.//{http://api.namecheap.com/xml.response}TotalItems')[0].text)
        except Exception as e:
            _logger.exception(e)
            return

    async def set_contacts(self, domain, contacts):
        _logger.info(f"Setting domain registration and billing contacts for {domain.name}.")

        from fixtures import NAMECHEAP_DOMAIN_CONTACTS as c
        from fixtures import NAMECHEAP_BILLING_CONTACT as b

        async with aiohttp.ClientSession() as session:
            url = self._get_url_prefix()
            url = f"{url}&Command=namecheap.domains.setContacts&DomainName={domain.name}"
            url = f"{url}&RegistrantOrganizationName={c.registrant.organisation}"
            url = f"{url}&RegistrantFirstName={c.registrant.firstname}"
            url = f"{url}&RegistrantLastName={c.registrant.lastname}"
            url = f"{url}&RegistrantAddress1={c.registrant.address1}"
            url = f"{url}&RegistrantAddress2={c.registrant.address2}"
            url = f"{url}&RegistrantCity={c.registrant.city}"
            url = f"{url}&RegistrantStateProvince={c.registrant.province}"
            url = f"{url}&RegistrantPostalCode={c.registrant.postalcode}"
            url = f"{url}&RegistrantCountry={c.registrant.country}"
            url = f"{url}&RegistrantPhone={c.registrant.phone}"
            url = f"{url}&RegistrantEmailAddress={c.registrant.email}"
            url = f"{url}&TechOrganizationName={c.tech.organisation}"
            url = f"{url}&TechFirstName={c.tech.firstname}"
            url = f"{url}&TechLastName={c.tech.lastname}"
            url = f"{url}&TechAddress1={c.tech.address1}"
            url = f"{url}&TechAddress2={c.tech.address2}"
            url = f"{url}&TechCity={c.tech.city}"
            url = f"{url}&TechStateProvince={c.tech.province}"
            url = f"{url}&TechPostalCode={c.tech.postalcode}"
            url = f"{url}&TechCountry={c.tech.country}"
            url = f"{url}&TechPhone={c.tech.phone}"
            url = f"{url}&TechEmailAddress={c.tech.email}"
            url = f"{url}&AdminOrganizationName={c.admin.organisation}"
            url = f"{url}&AdminFirstName={c.admin.firstname}"
            url = f"{url}&AdminLastName={c.admin.lastname}"
            url = f"{url}&AdminAddress1={c.admin.address1}"
            url = f"{url}&AdminAddress2={c.admin.address2}"
            url = f"{url}&AdminCity={c.admin.city}"
            url = f"{url}&AdminStateProvince={c.admin.province}"
            url = f"{url}&AdminPostalCode={c.admin.postalcode}"
            url = f"{url}&AdminCountry={c.admin.country}"
            url = f"{url}&AdminPhone={c.admin.phone}"
            url = f"{url}&AdminEmailAddress={c.admin.email}"
            url = f"{url}&AuxBillingOrganizationName={b.organisation}"
            url = f"{url}&AuxBillingFirstName={b.firstname}"
            url = f"{url}&AuxBillingLastName={b.lastname}"
            url = f"{url}&AuxBillingAddress1={b.address1}"
            url = f"{url}&AuxBillingAddress2={b.address2}"
            url = f"{url}&AuxBillingCity={b.city}"
            url = f"{url}&AuxBillingStateProvince={b.province}"
            url = f"{url}&AuxBillingPostalCode={b.postalcode}"
            url = f"{url}&AuxBillingCountry={b.country}"
            url = f"{url}&AuxBillingPhone={b.phone}"
            url = f"{url}&AuxBillingEmailAddress={b.email}"

            # See also 'extended attributes' for specific domains:
            # https://www.namecheap.com/support/api/extended-attributes.aspx

            async with session.get(url) as response:
                if response.status != 200:
                    _logger.error(f"Unexpected response from Namecheap API: {response.status}")
                    return
                xmlstring = await response.text()

        print(xmlstring)
        try:
            total_items = int(root.findall('.//{http://api.namecheap.com/xml.response}TotalItems')[0].text)
        except Exception as e:
            _logger.exception(e)
            return
