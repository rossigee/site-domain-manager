from fastapi import APIRouter, Depends, File
from starlette.responses import JSONResponse, Response

from sdmgr.oauth2 import *
from sdmgr.db import *
from sdmgr.manager import m

import logging
_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dns_providers", tags=["dns"])
async def list_dns_providers(user = Depends(get_current_user)):
    dns_providers = await DNSProvider.objects.all()
    return JSONResponse({
        "dns_providers": [await dns_provider.serialize() for dns_provider in dns_providers]
    })

@router.get("/dns_providers/{id:int}", tags=["dns"])
async def get_dns_provider(id: int, user = Depends(get_current_user)):
    dns_provider = await DNSProvider.objects.get(id = id)
    return JSONResponse(await dns_provider.serialize(full = True))

@router.get("/dns_providers/{id:int}/refresh", tags=["dns"])
async def refresh_dns_provider(id: int, user = Depends(get_current_user)):
    """
    Trigger a refresh of the domain data hosted by this agent. Used to force a fresh copy of the domains list to be fetched from the API.
    """
    agent = m.dns_agents[id]
    status = await agent.refresh()
    return JSONResponse({
        "status": status
    })

@router.get("/dns_providers/{id:int}/domains/{domainname}/status", tags=["dns"])
async def get_dns_provider_status_for_domain(id: int, domainname, user = Depends(get_current_user)):
    """
    Fetch the status of a domain from the nameservice provider. Used to show the current status of the domain's name servers, including their main NS records.
    """
    agent = m.dns_agents[id]
    status = await agent.get_status_for_domain(domainname)
    return JSONResponse({
        "status": status
    })
