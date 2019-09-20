from fastapi import APIRouter, Depends, File
from starlette.responses import JSONResponse, Response

from sdmgr.oauth2 import *
from sdmgr.db import *
from sdmgr.manager import m

import logging
_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/hosting", tags=["hosting"])
async def list_hosting_providers(user = Depends(get_current_user)):
    hosting_providers = await Hosting.objects.all()
    return JSONResponse({
        "hosting_providers": [await hosting_provider.serialize() for hosting_provider in hosting_providers]
    })


@router.get("/hosting/{id:int}/refresh", tags=["hosting"])
async def refresh_hosting_provider(id: int, user = Depends(get_current_user)):
    """
    Fetch a fresh copy of the information about the sites hosted by this agent.
    Used to force a fresh copy of the sites to be fetched from the API.
    """
    agent = m.hosting_agents[id]
    status = await agent.refresh()
    return JSONResponse({
        "status": status
    })
