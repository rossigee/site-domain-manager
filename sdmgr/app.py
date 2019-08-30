from fastapi import Depends, FastAPI, File, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from starlette.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

import uvicorn

from sdmgr import settings, manager
from sdmgr.db import *
from sdmgr.oauth2 import *

import os
import sys
import datetime
import signal
import asyncio

import logging
_logger = logging.getLogger(__name__)


m: manager.Manager = None

app = FastAPI(
    title="Site Domain Manager",
    description="Automating management of sites and domains.",
    version="0.0.1",
    openapi_prefix=os.getenv("OPENAPI_PREFIX", ""),
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/token", tags=["auth"], include_in_schema=False)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if "pytest" in sys.modules:
        from sdmgr.auth.test import auth
    else:
        from sdmgr.auth.ldap import auth
    await auth(form_data.username, form_data.password)

    _logger.info(f"Providing access token for {form_data.username}.")
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": form_data.username
        }, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/sites", tags=["sites"])
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


@app.get("/sites/{id:int}", tags=["sites"])
async def get_site(id: int, user = Depends(get_current_user)):
    site = await Site.objects.get(id=id)
    _logger.info(f"User '{user.username}' fetching site '{site.label}'.")
    return JSONResponse({
        "site": await site.serialize()
    })

#@app.post("/sites", tags=["sites"])
#async def add_site(site, user = Depends(get_current_user)):
#    _logger.info(f"User '{user.username}' adding new site '{site.label}'.")
#    await Site.objects.create(site)
#    return JSONResponse(dict(site))

#@app.put("/sites/{id:int}", tags=["sites"])
#async def update_site(site, user = Depends(get_current_user)):
#    _logger.info(f"User '{user.username}' updating site '{site.label}'.")
#    await Site.objects.update(site)
#    return JSONResponse(dict(site))

@app.get("/sites/{id:int}/check/ssl", tags=["sites"])
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

@app.get("/domains", tags=["domains"])
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

@app.get("/domains/{id:int}", tags=["domains"])
async def get_domain(id: int, user = Depends(get_current_user)):
    domain = await Domain.objects.get(id=id)
    _logger.info(f"User '{user.username}' fetching domain '{domain.name}'.")
    return JSONResponse({
        "domain": await domain.serialize()
    })

@app.post("/domains", tags=["domains"])
async def add_domain(domain, user = Depends(get_current_user)):
    _logger.info(f"User '{user.username}' adding new domain '{domain.name}'.")
    await Domain.objects.create(domain)
    return JSONResponse(await domain.serialize())

@app.put("/domains/{id:int}", tags=["domains"])
async def update_domain(id: int, domain, user = Depends(get_current_user)):
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

@app.get("/domains/{id:int}/check/ns", tags=["domains"])
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

@app.get("/domains/{id:int}/lookup/ns", tags=["domains"])
async def lookup_domain_ns(id: int, user = Depends(get_current_user)):
    """
    Return the results on an NS lookup to obtain the nameservers in use by the global DNS system. This allows the caller to compare Used to compare with the current status as of the domain's name servers, including their main NS records.
    """
    agent = m.dns_agents[id]
    status = await agent.get_status_for_domain(domainname)
    return JSONResponse({
        "status": status
    })

@app.get("/domains/{id:int}/check/a", tags=["domains"])
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

@app.get("/domains/{id:int}/check/gsv", tags=["domains"], summary="Check Domain Google Site Verification record")
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

@app.get("/domains/{id:int}/check/waf", tags=["domains"])
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

@app.get("/dns_providers", tags=["dns"])
async def list_dns_providers(user = Depends(get_current_user)):
    dns_providers = await DNSProvider.objects.all()
    return JSONResponse({
        "dns_providers": [await dns_provider.serialize() for dns_provider in dns_providers]
    })

@app.get("/dns_providers/{id:int}", tags=["dns"])
async def get_dns_provider(id: int, user = Depends(get_current_user)):
    dns_provider = await DNSProvider.objects.get(id = id)
    return JSONResponse(await dns_provider.serialize(full = True))

@app.get("/dns_providers/{id:int}/refresh", tags=["dns"])
async def refresh_dns_provider(id: int, user = Depends(get_current_user)):
    """
    Trigger a refresh of the domain data hosted by this agent. Used to force a fresh copy of the domains list to be fetched from the API.
    """
    agent = m.dns_agents[id]
    status = await agent.refresh()
    return JSONResponse({
        "status": status
    })

@app.get("/dns_providers/{id:int}/domains/{domainname}/status", tags=["dns"])
async def get_dns_provider_status_for_domain(id: int, domainname, user = Depends(get_current_user)):
    """
    Fetch the status of a domain from the nameservice provider. Used to show the current status of the domain's name servers, including their main NS records.
    """
    agent = m.dns_agents[id]
    status = await agent.get_status_for_domain(domainname)
    return JSONResponse({
        "status": status
    })

@app.get("/registrars", tags=["registrars"])
async def list_registrars(user = Depends(get_current_user)):
    return JSONResponse({
        "registrars": [await registrar.serialize() for registrar in await Registrar.objects.all()]
    })


@app.get("/registrars/{id:int}", tags=["registrars"])
async def get_registrar(id: int, user = Depends(get_current_user)):
    registrar = await Registrar.objects.get(id = id)
    r = await registrar.serialize(full = True)
    try:
        agent = m.registrar_agents[id]
        r['refresh_method'] = await agent.get_refresh_method()
        status = await agent.get_status()
        r['domain_count_total'] = status['domain_count_total']
        r['domain_count_active'] = status['domain_count_active']
    except NotImplementedError:
        pass
    except KeyError:
        _logger.error(f"No registrar agent for id '{id}'")
        pass
    return JSONResponse(r)

@app.post("/registrars/{id:int}/csvfile", tags=["registrars"])
async def update_registrar_by_csv_file(id: int, csvfile: bytes = File(...), user = Depends(get_current_user)):
    """
    Upload fresh CSV file downloaded from registrar. Intended for use with the Marcaria module and any other modules for registrars that allow a CSV file of their domains to be downloaded.
    """
    agent = m.registrar_agents[id]
    try:
        res = await agent.update_from_csvfile(csvfile)
        return JSONResponse({
            "status":"ok",
            "records_read": res['count']
        }, status_code=201)
    except Exception as e:
        return JSONResponse({
            "status":"error",
            "error": e.__str__()
        }, status_code=400)

@app.post("/registrars/{id:int}/jsonfile", tags=["registrars"])
async def update_registrar_by_json_file(id: int, jsonfile: bytes = File(...), user = Depends(get_current_user)):
    """
    Upload fresh JSON file downloaded from registrar. Intended for use with the IONOS module and any other modules for registrars that allow a JSON file of their domains to be downloaded.
    """
    agent = m.registrar_agents[id]
    try:
        res = await agent.update_from_jsonfile(jsonfile)
        return JSONResponse({
            "status":"ok",
            "records_read": res['count']
        }, status_code=201)
    except Exception as e:
        return JSONResponse({
            "status":"error",
            "error": e.__str__()
        }, status_code=400)

@app.get("/registrars/{id:int}/refresh", tags=["registrars"])
async def refresh_registrar_provider(id: int, user = Depends(get_current_user)):
    """
    Fetch a fresh copy of the information about the registrar for this agent. Used to force a fresh copy of the details to be fetched from the API.
    """
    agent = m.registrar_agents[id]
    try:
        res = await agent.refresh()
        return JSONResponse({
            "status":"ok",
            "records_read": res['count']
        }, status_code=201)
    except Exception as e:
        return JSONResponse({
            "status":"error",
            "error": e.__str__()
        }, status_code=400)

@app.get("/registrars/{id:int}/domains/{domainname}/status", tags=["registrars"])
async def get_registrar_status_for_domain(id: int, domainname, user = Depends(get_current_user)):
    """
    Fetch the status of a domain from the registrar. Used to show the current status and expiry date of a given domain with the registrar. This can fetch the data directly from the registrar's API, or use cached data from a recent CSV download, depending on the registrar's capabilities.
    """
    agent = m.registrar_agents[id]
    status = await agent.get_status_for_domain(domainname)
    return JSONResponse({
        "status": status
    })

@app.get("/hosting/{id:int}/refresh", tags=["hosting"])
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

@app.get("/waf/{id:int}/refresh", tags=["waf"])
async def refresh_waf_provider(id: int, user = Depends(get_current_user)):
    """
    Fetch a fresh copy of the information about the WAF managed by this agent. Used to force a fresh copy of the details to be fetched from the API.
    """
    agent = m.waf_agents[id]
    status = await agent.refresh()
    return JSONResponse({
        "status": status
    })

@app.get("/reconcile")
async def reconcile(user = Depends(get_current_user)):
    """
    Trigger a full reconciliation process. Status events will be logged to the standard log streams for now, but should eventually be routed to a log management system for indexing/searching/monitoring/alerting etc.
    """
    status = await m.reconcile()
    return JSONResponse({
        "status": status
    })


@app.on_event("startup")
async def startup():
    _logger.debug("Setting up signal handlers on main event loop...")
    loop = asyncio.get_event_loop()
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(signal=s)))
    loop.set_exception_handler(handle_exception)

    _logger.debug("Connecting to database...")
    await database.connect()

    _logger.debug("Instantiating manager...")
    global m
    m = manager.Manager()
    await m.run()

@app.on_event("shutdown")
async def shutdown(signal = None):
    if signal:
        _logger.info(f"Received signal: {signal}")

    _logger.info("Disconnecting from database...")
    await database.disconnect()

    _logger.info("Stopping main loop...")
    loop = asyncio.get_event_loop()
    loop.stop()

    _logger.info("Cancelling remaining tasks...")
    for task in asyncio.Task.all_tasks():
        task.cancel()

def handle_exception(loop, context):
    msg = context.get("exception", context["message"])
    logging.error(f"Caught exception in main thread: {msg}")

def main():
    uvicorn.run(app, host='0.0.0.0', port=8000)

if __name__ == '__main__':
    main()
