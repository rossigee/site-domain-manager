from ..base import RegistrarAgent

import logging
_logger = logging.getLogger(__name__)

import json
import orm


class IONOS(RegistrarAgent):
    _label_ = "IONOS (formerly 1&1)"

    def __init__(self, data, manager):
        _logger.info(f"Loading IONOS registrar agent (id: {data.id}): {data.label})")
        RegistrarAgent.__init__(self, data, manager)

        self.domains = {}
        self.registrar = data

    async def _load_state(self):
        await super(IONOS, self)._load_state()
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
        await super(IONOS, self)._save_state()

    async def get_refresh_method(self):
        return "jsonfile"

    async def update_from_jsonfile(self, content):
        _logger.debug(f"Updating IONOS data from JSON file.")

        jsonfile = content.decode("utf8")
        data = json.loads(jsonfile)

        self.domains = {}
        for d in data['domainList']:
            self.domains[d['name']] = {
                'name': d['name'],
                'status': d['state'],
                'expiry_date': d['expirationDate'],
                #'auto_renew': d['autoRenew'] == "ON"
            }

        _logger.info(f"Updated IONOS registrar with {len(self.domains)} domains from JSON file.")

        # Record this in the 'state' field in the db
        await self._save_state()

        # Ensure domain records are present for all domains listed in this file
        await self._populate_domains()

        # Return count of domains for confirmation message
        return {
            "count": len(self.domains)
        }

    async def get_status(self):
        active_domains = (x['name'] for x in self.domains.values() if x['status'] == "ACTIVE")
        return {
            'domain_count_total': len(self.domains),
            'domain_count_active': len(list(active_domains))
        }

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

    async def get_registered_domains(self):
        domains = []
        for domainname in self.domains.keys():
            domain = self.domains[domainname]
            if domain['status'] == "ACTIVE":
                domains.append(domainname)
        return domains
