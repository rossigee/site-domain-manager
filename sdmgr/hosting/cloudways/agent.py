from ..base import HostingAgent
from ...db import Site, Hosting

import logging
_logger = logging.getLogger(__name__)

import datetime
import os
import json
import aiohttp
import socket
import orm

BASE_URL = "https://api.cloudways.com/api/v1/"

class Cloudways(HostingAgent):
    def __init__(self, data):
        HostingAgent.__init__(self, data)
        _logger.info(f"Initialising Cloudways hosting provider agent (id: {self.id}): {self.label}")

        self.api_email = os.environ['CLOUDWAYS_API_EMAIL']
        self.api_key = os.environ['CLOUDWAYS_API_KEY']
        self.letsencrypt_email = os.environ['LETSENCRYPT_EMAIL']

        self.headers = None
        self.token_expires = None
        self.servers = []

    async def _load_state(self):
        await super(Cloudways, self)._load_state()
        try:
            self.servers = self.state['servers']
            _logger.info(f"Restored state for {self.label} with {len(self.servers)} servers.")
        except:
            self.servers = {}
            _logger.info(f"Initialised state for {self.label}.")

    async def _save_state(self):
        self.state = {
            "servers": self.servers
        }
        await super(Cloudways, self)._save_state()

    async def start(self):
        try:
            _logger.info(f"Starting Cloudways hosting provider agent (id: {self.id}).")
            await self._load_state()

            # TODO: Acquire credentials
            # (have it use envvars for now)

            #await self._populate_sites()

        except Exception as e:
            _logger.exception(e)

    def _has_token_expired(self):
        return self.token_expires is None or self.token_expires < datetime.datetime.now()

    async def _auth(self):
        if self.headers is not None and not self._has_token_expired():
            return

        url = BASE_URL + "oauth/access_token"
        payload = {
            "email": self.api_email,
            "api_key": self.api_key
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as response:
                if response.status != 200:
                    _logger.error(f"Unexpected response from Cloudways API: {response.status}")
                    return
                data = await response.json()

        access_token = data['access_token']
        self.headers = {
            'Authorization': f"Bearer {access_token}",
            'Accept': 'application/json'
        }
        self.token_expires = datetime.datetime.now() + datetime.timedelta(hours = 1)

    async def fetch_ips_for_site(self, site):
        for server in self.servers:
            for app in server['apps']:
                if app['label'] != site.label:
                    continue
                return [server['public_ip']]

        raise Exception(f"Unknown site {site.label}")

    async def fetch_aliases_for_site(self, site):
        for server in self.servers:
            for app in server['apps']:
                if app['label'] != site.label:
                    continue
                return app['aliases']

        raise Exception(f"Unknown site {site.label}")

    async def update_aliases_for_site(self, site, aliases):
        await self._auth()

        server_id = None
        app_id = None
        for server in self.servers:
            for app in server['apps']:
                if app['label'] == site.label:
                    server_id = server['id']
                    app_id = app['id']
        if app_id is None:
            _logger.error(f"Unknown site {site.label}")
            return None

        _logger.info(f"Setting {len(aliases)} aliases for site {site.label} on Cloudways.")
        url = BASE_URL + "app/manage/aliases"
        payload = {
            'server_id': server_id,
            'app_id': app_id,
            'aliases[]': aliases
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, data=payload) as response:
                if response.status == 200:
                    _logger.debug("Set aliases successfully.")
                    return
                elif response.status == 422:
                    data = await response.json()
                    _logger.warning(data['aliases']['message'])
                    return
                else:
                    print(await response.text())
                    _logger.error(f"Unexpected response from Cloudways API: {response.status}")
                    return
                #data = await response.json()

        await self.refresh()

    async def set_letsencrypt_domains_for_site(self, hostname, aliases):
        await self._auth()

        server_id = None
        app_id = None
        for server in self.servers:
            for app in server['apps']:
                if app['label'] == hostname:
                    server_id = server['id']
                    app_id = app['id']
        if app_id is None:
            _logger.error("Unknown site {hostname}")
            return None

        _logger.info("Requesting new SSL certificate for {hostname} on Cloudways")
        url = BASE_URL + "security/lets_encrypt_install"
        payload = {
            'server_id': server_id,
            'app_id': app_id,
            'LETSENCRYPT_EMAIL': self.letsencrypt_email,
            'wild_card': False,
            'ssl_domains': aliases
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, data=payload) as response:
                if response.status == 200:
                    _logger.info("Set SSL certificates successfully.")
                    return
                elif response.status == 422:
                    data = await response.json()
                    _logger.warning(data['aliases']['message'])
                    return
                else:
                    _logger.error(f"Unexpected response from Cloudways API: {response.status}")
                    return

    async def refresh(self):
        await self._auth()

        # Fetch list of servers
        _logger.info(f"Fetching server list from {self.label}...")
        url = BASE_URL + "server"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    _logger.error(f"Unexpected response from Cloudways API: {response.status}")
                    return
                data = await response.json()

        self.servers = data['servers']
        _logger.info(f"Found {len(self.servers)} servers on {self.label}")

        await self._save_state()

        await self._populate_sites()

    async def _populate_sites(self):
        for server in self.servers:
            for app in server['apps']:
                try:
                    site = await Site.objects.get(label=app['label'])
                    _logger.debug(f"Found site {site.label}.")
                except orm.exceptions.NoMatch:
                    hosting = await Hosting.objects.get(id=self.id)
                    site = await Site.objects.create(
                        label = app['label'],
                        hosting = hosting
                    )
                    _logger.info(f"Created site {site.label}...")
