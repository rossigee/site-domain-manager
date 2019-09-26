from fastapi import APIRouter, Depends, File
from starlette.responses import JSONResponse, Response

from sdmgr.oauth2 import *
from sdmgr.db import *
from sdmgr.manager import m

import logging
_logger = logging.getLogger(__name__)

router = APIRouter()


from pydantic import BaseModel

class DomainUpdateForm(BaseModel):
    name: str
    registrar: int
    dns: int
    site: int
    waf: int
    #update_apex: bool
    #update_a_records: str
    google_site_verification: str
    active: bool


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

# NOTE: New domains should be created by importing fresh data to a registrar agent
#@router.post("/domains", tags=["domains"])
#async def add_domain(domain, user = Depends(get_current_user)):
#    _logger.info(f"User '{user.username}' adding new domain '{domain.name}'.")
#    await Domain.objects.create(domain)
#    return JSONResponse(await domain.serialize())

@router.post("/domains/{id:int}", tags=["domains"])
async def update_domain(id: int, domain_in: DomainUpdateForm, user = Depends(get_current_user)):
    """
    Update editable attributes of a domain.
    """
    domain = await Domain.objects.get(id=id)
    _logger.info(f"User '{user.username}' updating domain '{domain.name}'.")

    update_kwargs = {}
    notices = []
    actions = []
    if domain.registrar.id != domain_in.registrar:
        update_kwargs['registrar'] = await Registrar.objects.get(id = domain_in.registrar)
        notices.append(f"User '{user.username}' updated registrar provider to {update_kwargs['registrar'].label} for domain {domain.name}.")
        actions.append(f"Updated registrar provider to {update_kwargs['registrar'].label}")
    if domain.dns.id != domain_in.dns:
        update_kwargs['dns'] = await DNSProvider.objects.get(id = domain_in.dns)
        notices.append(f"User '{user.username}' updated DNS provider to {update_kwargs['dns'].label} for domain {domain.name}.")
        actions.append(f"Updated DNS provider to {update_kwargs['dns'].label}")
    if domain.site.id != domain_in.site:
        update_kwargs['site'] = await Site.objects.get(id = domain_in.site)
        notices.append(f"User '{user.username}' updated site to {update_kwargs['site'].label} for domain {domain.name}.")
        actions.append(f"Updated site to {update_kwargs['site'].label}")
    if domain.waf.id != domain_in.waf:
        update_kwargs['waf'] = await WAFProvider.objects.get(id = domain_in.waf)
        notices.append(f"User '{user.username}' updated WAF provider to {update_kwargs['waf'].label} for domain {domain.name}.")
        actions.append(f"Updated WAF provider to {update_kwargs['waf'].label}")
    if domain.google_site_verification != domain_in.google_site_verification:
        update_kwargs['google_site_verification'] = domain_in.google_site_verification
        notices.append(f"User '{user.username}' updated GSV to {domain_in.google_site_verification} for domain {domain.name}.")
        actions.append(f"Updated GSV to {domain_in.google_site_verification}")
    if domain.active != domain_in.active:
        update_kwargs['active'] = domain_in.active
        notices.append(f"User '{user.username}' updated active flag to {domain_in.active} for domain {domain.name}.")
        actions.append(f"Updated active flag to {domain_in.active}")

    if len(actions) > 0:
        try:
            await domain.update(**update_kwargs)
            for notice in notices:
                _logger.info(notice)
        except Exception as e:
            _logger.exception(e)

    return JSONResponse({
        "status": "ok",
        "actions": actions,
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
    # (https://github.com/encode/orm/issues/49)
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
    # TODO make request asynchronous...
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
    # TODO make request asynchronous...
    status = await m.check_domain(domain)
    checks = StatusCheck.objects.filter(_check_id__contains=f"domain:{domain.name}:")
    return JSONResponse({
        "status": status.serialize(),
        "checks": [await check.serialize() for check in await checks.all()]
    })

@router.get("/domains/{id:int}/check/ns", tags=["domains"])
async def check_domain_ns(id: int, user = Depends(get_current_user)):
    """
    Check the DNS NS records for this domain.
    """
    domain = await Domain.objects.get(id = id)
    _logger.info(f"User '{user.username}' checking NS records for '{domain.name}'.")
    # TODO make request asynchronous...
    status = await m.check_domain_ns_records(domain)
    checks = StatusCheck.objects.filter(_check_id__contains=f"domain:{domain.name}:")
    return JSONResponse({
        "status": await status.serialize(),
        "checks": [await check.serialize() for check in await checks.all()]
    })

@router.get("/domains/{id:int}/check/a", tags=["domains"])
async def check_domain_a(id: int, user = Depends(get_current_user)):
    """
    Check the DNS A records for this domain.
    """
    domain = await Domain.objects.get(id = id)
    _logger.info(f"User '{user.username}' checking A records for '{domain.name}'.")
    # TODO make request asynchronous...
    status = await m.check_domain_a_records(domain)
    checks = StatusCheck.objects.filter(_check_id__contains=f"domain:{domain.name}:")
    return JSONResponse({
        "status": await status.serialize(),
        "checks": [await check.serialize() for check in await checks.all()]
    })

@router.get("/domains/{id:int}/check/gsv", tags=["domains"], summary="Check Domain Google Site Verification record")
async def check_domain_gsv(id: int, user = Depends(get_current_user)):
    """
    Check that the DNS TXT records for this domain contains the correct Google Site Verification token.
    - **id**: domain id
    """
    domain = await Domain.objects.get(id = id)
    _logger.info(f"User '{user.username}' checking Google Site Verification TXT records for '{domain.name}'.")
    # TODO make request asynchronous...
    status = await m.check_domain_google_site_verification(domain)
    checks = StatusCheck.objects.filter(_check_id__contains=f"domain:{domain.name}:")
    return JSONResponse({
        "status": await status.serialize(),
        "checks": [await check.serialize() for check in await checks.all()]
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
