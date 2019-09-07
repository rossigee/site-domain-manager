from fastapi import APIRouter, Depends, File
from starlette.responses import JSONResponse, Response

from sdmgr.oauth2 import *
from sdmgr.db import *
from sdmgr.manager import m

import logging
_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/sites", tags=["sites"])
async def list_sites(label = None, user = Depends(get_current_user)):
    if label:
        _logger.info(f"User '{user.username}' searching sites for: {label}")
        sites = await Site.objects.filter(label__icontains=label).all()
    else:
        _logger.info(f"User '{user.username}' listing all sites.")
        sites = await Site.objects.all()
    return JSONResponse({
        "sites": [await site.serialize() for site in sites]
    })


@router.get("/sites/{id:int}", tags=["sites"])
async def get_site(id: int, user = Depends(get_current_user)):
    site = await Site.objects.get(id=id)
    _logger.info(f"User '{user.username}' fetching site '{site.label}'.")
    return JSONResponse({
        "site": await site.serialize()
    })

#@router.post("/sites", tags=["sites"])
#async def add_site(site, user = Depends(get_current_user)):
#    _logger.info(f"User '{user.username}' adding new site '{site.label}'.")
#    await Site.objects.create(site)
#    return JSONResponse(dict(site))

#@router.put("/sites/{id:int}", tags=["sites"])
#async def update_site(site, user = Depends(get_current_user)):
#    _logger.info(f"User '{user.username}' updating site '{site.label}'.")
#    await Site.objects.update(site)
#    return JSONResponse(dict(site))

@router.get("/sites/{id:int}/check/ssl", tags=["sites"])
async def check_site_ssl(id: int, user = Depends(get_current_user)):
    """
    Check the SSL configuration for this site.
    """
    site = await Site.objects.get(id = id)
    _logger.info(f"User '{user.username}' checking SSL for site '{site.label}'.")
    status = await m.check_site_ssl_certs(site)

    return JSONResponse({
        "site": {
            "id": id,
            "label": site.label
        },
        "status": status
    })
