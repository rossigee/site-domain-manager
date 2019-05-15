from ..base import RegistrarAgent

import logging
_logger = logging.getLogger(__name__)

import csv
import orm


class Marcaria(RegistrarAgent):
    def __init__(self, data):
        RegistrarAgent.__init__(self, data)
        _logger.info(f"Loading Marcaria registrar agent (id: {self.id}): {self.label}")

        self.domains = {}
        self.registrar = data

    async def _load_state(self):
        await super(Marcaria, self)._load_state()
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
        await super(Marcaria, self)._save_state()

    async def start(self):
        try:
            _logger.debug(f"Starting Marcaria registrar agent (id: {self.id}).")
            await self._load_state()

        except Exception as e:
            _logger.exception(e)

    async def update_from_csvfile(self, f):
        _logger.debug(f"Updating Marcaria data from CSV file.")

        try:
            content = await f.read()
            csvfile = csv.reader(content.decode("utf8").replace("\n", "").split("\r"))
            self.domains = {}
            header_row = None
            for row in csvfile:
                if not len(row):
                    continue
                if header_row is None:
                    header_row = row
                    continue
                if row[1] != "Registered":
                    continue
                self.domains[row[0]] = {
                    'name': row[0],
                    'expiry_date': row[4], # TODO: Parse date
                    'auto_renew': row[8] == "ON"
                }

            _logger.info(f"Loaded {len(self.domains)} domains from CSV file.")

        except Exception as e:
            _logger.exception(e)
            return

        await self._save_state()

        await self._populate_domains()

    async def get_registered_domains(self):
        return self.domains.keys()

    async def set_ns_records(self, domain, nameservers):
        # TODO: Send notification to someone (i.e. via email/Discord). Don't
        # just dump this in a log file no-one checks!
        _logger.info(f"IMPORTANT! Please update the NS records on {self.label} for {domain.name} to:")
        for i in nameservers:
            _logger.info(f"{domain.name} NS {i}")
