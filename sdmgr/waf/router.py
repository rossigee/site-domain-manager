from fastapi import APIRouter, Depends, File
from starlette.responses import JSONResponse, Response

from sdmgr.oauth2 import *
from sdmgr.db import *
from sdmgr.manager import m

import logging
_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/waf/{id:int}/refresh", tags=["waf"])
async def refresh_waf_provider(id: int, user = Depends(get_current_user)):
    """
    Fetch a fresh copy of the information about the WAF managed by this agent. Used to force a fresh copy of the details to be fetched from the API.
    """
    agent = m.waf_agents[id]
    status = await agent.refresh()
    return JSONResponse({
        "status": status
    })
