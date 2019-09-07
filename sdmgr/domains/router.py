from fastapi import APIRouter, Depends, File
from starlette.responses import JSONResponse, Response

from sdmgr.oauth2 import *
from sdmgr.db import *
from sdmgr.manager import m

import logging
_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/domains", tags=["domains"])
async def list_domains(name = None, user = Depends(get_current_user)):
    if name:
        _logger.info(f"User '{user.username}' searching domains for: {name}")
        domains = await Domain.objects.filter(name__icontains=name).all()
    else:
        _logger.info(f"User '{user.username}' listing domains.")
        domains = await Domain.objects.all()
    return JSONResponse({
        "domains": [await domain.serialize() for domain in domains]
    })

@router.get("/domains/{id:int}", tags=["domains"])
async def get_domain(id: int, user = Depends(get_current_user)):
    domain = await Domain.objects.get(id=id)
    _logger.info(f"User '{user.username}' fetching domain '{domain.name}'.")
    return JSONResponse({
        "domain": await domain.serialize()
    })

@router.get("/domains/{id:int}/checks", tags=["domains"])
async def get_domain_checks(id: int, user = Depends(get_current_user)):
    """
    Fetch latest checks for domain.
    """
    domain = await Domain.objects.get(id=id)
    _logger.info(f"User '{user.username}' fetching domain checks for '{domain.name}'.")
    # A '__startswith' filter would be better...
    checks = StatusCheck.objects.filter(_check_id__contains=f"domain:{domain.name}:")
    return JSONResponse({
        "checks": [await check.serialize() for check in await checks.all()]
    })

@router.get("/domains/{id:int}/check", tags=["domains"])
async def check_domain(id: int, user = Depends(get_current_user)):
    """
    Restart checks for domain.
    """
    domain = await Domain.objects.get(id=id)
    _logger.info(f"User '{user.username}' restarting domain checks for '{domain.name}'.")
    # TODO make request asyncronous...
    await m.check_domain(domain)
    checks = StatusCheck.objects.filter(_check_id__contains=f"domain:{domain.name}:")
    return JSONResponse({
        "checks": [await check.serialize() for check in await checks.all()]
    })

@router.get("/domains/{id:int}/apply", tags=["domains"])
async def apply_domain(id: int, user = Depends(get_current_user)):
    """
    Apply necessary changes for domain.
    """
    domain = await Domain.objects.get(id=id)
    _logger.info(f"User '{user.username}' applying domain configuration for '{domain.name}'.")
    await m.apply_domain(domain)
    # TODO make request asyncronous...
    await m.check_domain(domain)
    checks = StatusCheck.objects.filter(_check_id__contains=f"domain:{domain.name}:")
    return JSONResponse({
        "checks": [await check.serialize() for check in await checks.all()]
    })

# NOTE: New domains should be created by importing fresh data to a registrar agent
#@router.post("/domains", tags=["domains"])
#async def add_domain(domain, user = Depends(get_current_user)):
#    _logger.info(f"User '{user.username}' adding new domain '{domain.name}'.")
#    await Domain.objects.create(domain)
#    return JSONResponse(await domain.serialize())

@router.put("/domains/{id:int}", tags=["domains"])
async def update_domain(id: int, domain, user = Depends(get_current_user)):
    """
    Update editable attributes of a domain.
    """
    _logger.info(f"User '{user.username}' updating domain '{domain.name}'.")
    domain = await Domain.objects.get(id = id)

    update_kwargs = {}
    notices = []
    actions = []
    if domain.google_site_verification != newdomain.google_site_verification:
        update_kwargs['google_site_verification'] = newdomain.google_site_verification
        notices.append("User '{request.user.name}' updated GSV to {newdomain.google_site_verification} for domain {domain.name}.")
        actions.append("Updated GSV to {newdomain.google_site_verification}")
    if domain.active != newdomain.active:
        update_kwargs['active'] = newdomain.active
        notices.append("User '{request.user.name}' updated active flag to {newdomain.active} for domain {domain.name}.")
        actions.append("Updated active flag to {newdomain.active}")

    if len(actions) > 0:
        try:
            await domain.update(**update_kwargs)
            for notice in notices:
                _logger.info(notice)
        except Exception as e:
            _logger.exception(e)

    return JSONResponse({
        "status": "ok",
        "actions": actions
    })

@router.get("/domains/{id:int}/check/ns", tags=["domains"])
async def check_domain_ns(id: int, user = Depends(get_current_user)):
    """
    Check the DNS NS records for this domain.
    """
    domain = await Domain.objects.get(id = id)
    status = await m.check_domain_ns_records(domain)
    return JSONResponse({
        "domain": {
            "id": id,
            "name": domain.name
        },
        "status": status
    })

@router.get("/domains/{id:int}/lookup/ns", tags=["domains"])
async def lookup_domain_ns(id: int, user = Depends(get_current_user)):
    """
    Return the results on an NS lookup to obtain the nameservers in use by the global DNS system. This allows the caller to compare Used to compare with the current status as of the domain's name servers, including their main NS records.
    """
    agent = m.dns_agents[id]
    status = await agent.get_status_for_domain(domainname)
    return JSONResponse({
        "status": status
    })

@router.get("/domains/{id:int}/check/a", tags=["domains"])
async def check_domain_a(id: int, user = Depends(get_current_user)):
    """
    Check the DNS A records for this domain.
    """
    domain = await Domain.objects.get(id = id)
    status = await m.check_domain_a_records(domain)
    return JSONResponse({
        "domain": {
            "id": id,
            "name": domain.name
        },
        "status": status
    })

@router.get("/domains/{id:int}/check/gsv", tags=["domains"], summary="Check Domain Google Site Verification record")
async def check_domain_gsv(id: int, user = Depends(get_current_user)):
    """
    Check that the DNS TXT records for this domain contains the correct Google Site Verification token.
    - **id**: domain id
    """
    domain = await Domain.objects.get(id = id)
    status = await m.check_domain_google_site_verification(domain)
    return JSONResponse({
        "domain": {
            "id": id,
            "name": domain.name
        },
        "status": status
    })

@router.get("/domains/{id:int}/check/waf", tags=["domains"])
async def check_domain_waf(id: int, user = Depends(get_current_user)):
    """
    Check the WAF setup for this domain.
    """
    domain = await Domain.objects.get(id = id)
    status = await m.check_domain_waf(domain)
    return JSONResponse({
        "domain": {
            "id": id,
            "name": domain.name
        },
        "status": status
    })
