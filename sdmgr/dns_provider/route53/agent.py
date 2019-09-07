from ..base import DNSProviderAgent
from .. import DomainNotHostedException

import logging
_logger = logging.getLogger(__name__)

import asyncio
import uuid
import boto3


class Route53(DNSProviderAgent):
    _label_ = "Amazon Route53"

    _settings_ = [
        {
            'key': "aws_access_key_id",
            'description': "AWS access key ID",
        },
        {
            'key': "aws_secret_access_key",
            'description': "AWS secret access key",
        },
    ]

    def __init__(self, data):
        _logger.info(f"Loading Route53 DNS provider agent (id: {data.id}): {data.label})")
        DNSProviderAgent.__init__(self, data)

        self.domains = {}
        self.zone_ids_cache = {}

    async def _load_state(self):
        await super(Route53, self)._load_state()
        try:
            self.domains = self.state['domains']
            _logger.info(f"Restored state for {self.label} with {len(self.domains)} domains.")
        except KeyError:
            self.domains = {}
            _logger.info(f"Initialiased state for {self.label}.")

    async def _save_state(self):
        self.state = {
            "domains": self.domains
        }
        await super(Route53, self)._save_state()

    def get_client(self):
        return boto3.client('route53',
            aws_access_key_id = self._config("aws_access_key_id"),
            aws_secret_access_key = self._config("aws_secret_access_key")
        )

    def _get_zone_id_for_domain(self, domainname):
        if domainname in self.zone_ids_cache.keys():
            return self.zone_ids_cache[domainname]
        client = self.get_client()
        zones = client.list_hosted_zones_by_name(DNSName=domainname)
        if not zones or len(zones['HostedZones']) == 0:
            raise DomainNotHostedException(domainname)

        zone_id = zones['HostedZones'][0]['Id'][12:]
        self.zone_ids_cache[domainname] = zone_id
        return zone_id

    async def _wait_for_change_id(self, change_id):
        client = self.get_client()
        while True:
            _logger.debug(f"Polling change id '{change_id}'")
            response = client.get_change(Id=change_id)
            try:
                #status = response["GetChangeResponse"]["ChangeInfo"]["Status"]
                status = response["ChangeInfo"]["Status"]
                _logger.debug(f"Found status for {change_id}: {status}")
                if status == "INSYNC":
                    break
                await asyncio.sleep(5)
            except KeyError:
                _logger.error(f"Unexpected response: {response}")
                break

    async def refresh(self):
        _logger.info(f"Refreshing list of domains managed on {self.label}...")
        domains = {}
        marker = None

        client = self.get_client()
        while True:
            _logger.debug(f"Fetching page of results from Route53...")
            kwargs = {
                "MaxItems": str(100)
            }
            if marker is not None:
                kwargs['Marker'] = marker
            response = client.list_hosted_zones(**kwargs)
            for zone in response['HostedZones']:
                dname = zone['Name'].strip('.')
                domains[dname] = zone
            if not response['IsTruncated']:
                break
            marker = response['NextMarker']

        self.domains = domains
        _logger.info(f"Loaded {len(self.domains)} domains from Route53 API.")
        await self._save_state()

        await self._populate_domains()

    async def get_hosted_domains(self):
        return self.domains.keys()

    async def get_status_for_domain(self, domainname):
        if domainname not in self.domains:
            return {
                'summary': f"No information for '{domainname}'"
            }
        zone_id = self._get_zone_id_for_domain(domainname)
        return {
            'name': domainname,
            'summary': f"OK (R53 Zone: {zone_id})",
            'nameservers': await self.get_ns_records(domainname),
        }

    async def get_ns_records(self, domainname):
        zone_id = self._get_zone_id_for_domain(domainname)
        client = self.get_client()
        response = client.list_resource_record_sets(
            HostedZoneId=zone_id,
            StartRecordType='NS',
            StartRecordName=domainname,
            MaxItems='1'
        )
        rrs = response['ResourceRecordSets']
        values = []
        if len(rrs) > 0:
            if rrs[0]['Type'] == 'NS' and rrs[0]['Name'] == f"{domainname}.":
                values = [x['Value'].strip(".") for x in rrs[0]['ResourceRecords']]
        return values

    async def create_domain(self, domain):
        if domain in self.domains.keys():
            _logger.info(f"Domain {domain} already hosted by {self.label}. No need to create again.")
            return

        client = self.get_client()
        token = uuid.uuid4().__str__().replace("-", "")
        response = client.create_hosted_zone(
            Name=domain,
            CallerReference=token,
            HostedZoneConfig={
                'Comment': 'Created by SDMGR',
                'PrivateZone': False
            }
        )

        await self._wait_for_change_id(response['ChangeInfo']['Id'])

        # Let the domain settle before using it...
        await asyncio.sleep(5)

        # Refresh our list of domains
        await self.refresh()

    async def create_new_a_rr(self, domain, hostname, ip_addrs):
        zone_id = self._get_zone_id_for_domain(domain.name)
        print(zone_id)
        client = self.get_client()
        response = client.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={
                'Comment': f"SDMGR setting {len(ip_addrs)} A record(s)",
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': hostname,
                            'Type': 'A',
                            'TTL': 300,
                            'ResourceRecords': [
                                {
                                    'Value': x
                                } for x in ip_addrs
                            ],
                        }
                    },
                ]
            }
        )
        print(response)
        await self._wait_for_change_id(response['ChangeInfo']['Id'])

    async def get_txt_records(self, domain):
        # Find existing TXT records for the domain
        zone_id = self._get_zone_id_for_domain(domain.name)
        client = self.get_client()
        response = client.list_resource_record_sets(
            HostedZoneId=zone_id,
            StartRecordType='TXT',
            StartRecordName=domain,
            MaxItems='1'
        )
        rrs = response['ResourceRecordSets']
        values = []
        if len(rrs) > 0:
            if rrs[0]['Type'] == 'TXT' and rrs[0]['Name'] == f"{domain}.":
                values = [x['Value'] for x in rrs[0]['ResourceRecords']]
        return values

    async def check_google_site_verification(self, domain):
        # See if we already have it (or another one)
        values = await self.get_txt_records(domain.name)
        already_have_it = False
        value_correct = False
        for value in values:
            if value[0:26] == "\"google-site-verification=" and value[26:-1] == verif:
                already_have_it = True
                existing_gsv = value[26:-1]
                if existing_gsv == verification_code:
                    _logger.debug(f"GSV code present and correct")
                    value_correct = False
                else:
                    _logger.warning(f"Found existing GSV code in TXT record for {domain.name} with value: {existing_gsv}")
        return (already_have_it, value_correct)

    async def set_google_site_verification(self, domain):
        # Otherwise, it needs setting/updating...
        txt_to_be_set = f"\"google-site-verification={domain.google_site_verification}\""
        values = await self.get_txt_records(domain.name)
        for value in values:
            if value == txt_to_be_set:
                _logger.info(f"Google Site Verification code for {domain.name} present and correct.")
                return
            if value[0:26] == "\"google-site-verification=":
                existing_gsv = value[26:-1]
                _logger.warning(f"Found unexpected Google Site Verification TXT record for {domain.name} with value: {existing_gsv}")
        values.append(txt_to_be_set)
        _logger.info(f"Adding TXT record to {domain.name} with GSV {domain.google_site_verification}...")
        zone_id = self._get_zone_id_for_domain(domain.name)
        client = self.get_client()
        response = client.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={
                'Comment': 'SDMGR setting Google Site Verification',
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': f"{domain.name}.",
                            'Type': 'TXT',
                            'TTL': 300,
                            'ResourceRecords': [
                                {
                                    'Value': x
                                } for x in values
                            ],
                        }
                    },
                ]
            }
        )

        await self._wait_for_change_id(response['ChangeInfo']['Id'])
