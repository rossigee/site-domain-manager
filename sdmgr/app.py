from starlette.applications import Starlette
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.schemas import SchemaGenerator
from starlette.responses import JSONResponse
import uvicorn

from sdmgr import settings, manager
from sdmgr.db import *
from sdmgr.basicauth import BasicAuthBackend, UnauthenticatedResponse

import logging
_logger = logging.getLogger(__name__)


schemas = SchemaGenerator({
    "openapi": "3.0.0",
    "info": {
        "title": "Sites and Domains Manager API",
        "version": "0.0.1",
        "description": "Background daemon process and REST API for managing web sites, domain registrations, DNS entries, WAFs and SSL certificates.",
        "contact": {
            "name": "Ross Golder",
            "email": "ross@golder.org"
        }
    }
})

app = Starlette(debug=True)
app.add_middleware(AuthenticationMiddleware, backend=BasicAuthBackend())
app.debug = settings.DEBUG

m = None # Manager

@app.route("/sites", methods=["GET"])
async def list_sites(request):
    """
    summary: List sites.
    responses:
      200:
        description: A list of sites.
        examples:
          [{"id": 1, "label": "Our Main Site"}]
    """
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    return JSONResponse({
        "sites": [await site.serialize() for site in await Site.objects.all()]
    })

@app.route("/sites", methods=["POST"])
async def add_site(request):
    """
    summary: Add a new site.
    responses:
      201:
        description: A site.
        examples:
          {"id": 1, "label": "Our Main Site", "active": True}
    """
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    data = await request.json()
    site, errors = Site.validate_or_error(data)
    if errors:
        return JSONResponse(dict(errors), status_code=400)
    await Site.objects.create(site)
    return JSONResponse(dict(site))

@app.route("/sites", methods=["PUT"])
async def add_site(request):
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    data = await request.json()
    site, errors = Site.validate_or_error(data)
    if errors:
        return JSONResponse(dict(errors), status_code=400)
    await Site.objects.create(site)
    return JSONResponse(dict(site))

@app.route("/sites/{id:int}/check/ssl", methods=["GET"])
async def check_site_ssl(request):
    """
    summary: Check the SSL configuration for this site.
    responses:
      200:
        description: Check triggered
        examples:
          {"status": "ok"}
    """
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    id = request.path_params['id']
    site = await Site.objects.get(id = id)
    status = await m.check_site_ssl_certs(site)
    return JSONResponse({
        "site": {
            "id": id,
            "label": site.label
        },
        "status":status
    })

@app.route("/domains", methods=["GET"])
async def list_domains(request):
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    return JSONResponse({"domains": [await domain.serialize() for domain in await Domain.objects.all()]})

@app.route("/domains", methods=["POST"])
async def add_domain(request):
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    data = await request.json()
    if 'registrar' in data.keys():
        registrar_id = data['registrar'];
        data['registrar'] = await Registrar.objects.get(id=registrar_id)
    domain, errors = Domain.validate_or_error(data)
    if errors:
        return JSONResponse(dict(errors), status_code=400)

    await Domain.objects.create(**data)
    return JSONResponse(await domain.serialize())

@app.route("/domains/{id:int}", methods=["PUT"])
async def update_domain(request):
    """
    summary: Update a domain.
    responses:
      200:
        description: A list of update actions taken.
        examples:
          {"status": "ok", "actions": ["Updated a field to this value"]}
    """
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    id = request.path_params['id']
    data = await request.json()
    newdomain, errors = Domain.validate_or_error(data)
    if errors:
        return JSONResponse(dict(errors), status_code=400)
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

@app.route("/domains/{id:int}/check/ns", methods=["GET"])
async def check_domain_ns(request):
    """
    summary: Check the NS records for this domain.
    responses:
      200:
        description: Check triggered
        examples:
          {"status": "ok"}
    """
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    id = request.path_params['id']
    domain = await Domain.objects.get(id = id)
    status = await m.check_domain_ns_records(domain)
    return JSONResponse({
        "domain": {
            "id": id,
            "name": domain.name
        },
        "status":status
    })

@app.route("/domains/{id:int}/check/a", methods=["GET"])
async def check_domain_a(request):
    """
    summary: Check the A records for this domain.
    responses:
      200:
        description: Check triggered
        examples:
          {"status": "ok"}
    """
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    id = request.path_params['id']
    domain = await Domain.objects.get(id = id)
    status = await m.check_domain_a_records(domain)
    return JSONResponse({
        "domain": {
            "id": id,
            "name": domain.name
        },
        "status":status
    })

@app.route("/domains/{id:int}/check/gsv", methods=["GET"])
async def check_domain_gsv(request):
    """
    summary: Check the GSV TXT record for this domain.
    responses:
      200:
        description: Check triggered
        examples:
          {"status": "ok"}
    """
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    id = request.path_params['id']
    domain = await Domain.objects.get(id = id)
    status = await m.check_domain_google_site_verification(domain)
    return JSONResponse({
        "domain": {
            "id": id,
            "name": domain.name
        },
        "status":status
    })

@app.route("/dns_providers", methods=["GET"])
async def list_dns_providers(request):
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    return JSONResponse({"dns_providers": [await dns_provider.serialize() for dns_provider in await DNSProvider.objects.all()]})

@app.route("/dns_providers/{id:int}", methods=["GET"])
async def get_dns_provider(request):
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    id = request.path_params['id']
    dns_provider = await DNSProvider.objects.get(id = id)
    return JSONResponse(await dns_provider.serialize(full = True))

@app.route("/dns_providers/{id:int}/refresh", methods=["GET"])
async def refresh_dns_provider(request):
    """
    summary: Trigger a refresh of the domain data hosted by this agent.
    description: Used to force a fresh copy of the domains list to be fetched from the API.
    responses:
      200:
        description:
        examples:
          {"status": "ok"}
    """
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    id = request.path_params['id']
    agent = m.dns_agents[id]
    status = await agent.refresh()
    return JSONResponse({"status":status})

@app.route("/registrars", methods=["GET"])
async def list_registrars(request):
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    return JSONResponse({"registrars": [await registrar.serialize() for registrar in await Registrar.objects.all()]})

@app.route("/registrars/{id:int}/csvfile", methods=["POST"])
async def update_marcaria_by_csv_file(request):
    """
    summary: Upload fresh CSV file downloaded from registrar.
    description: Intended for use with the Marcaria module.
    responses:
      201:
        description: CSV file accepted.
        examples:
          {"status": "ok"}
    """
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    id = request.path_params['id']
    form = await request.form()

    agent = m.registrar_agents[id]
    await agent.update_from_csvfile(form["csvfile"])

    return JSONResponse({"status":"ok"}, status_code=201)

@app.route("/hosting/{id:int}/refresh", methods=["GET"])
async def refresh_hosting_provider(request):
    """
    summary: Fetch a fresh copy of the information about the sites hosted by this agent.
    description: Used to force a fresh copy of the sites to be fetched from the API.
    responses:
      200:
        description:
        examples:
          {"status": "ok"}
    """
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    id = request.path_params['id']
    agent = m.hosting_agents[id]
    status = await agent.refresh()
    return JSONResponse({"status":status})

@app.route("/waf/{id:int}/refresh", methods=["GET"])
async def refresh_hosting_provider(request):
    """
    summary: Fetch a fresh copy of the information about the WAF managed by this agent.
    description: Used to force a fresh copy of the details to be fetched from the API.
    responses:
      200:
        description:
        examples:
          {"status": "ok"}
    """
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    id = request.path_params['id']
    agent = m.waf_agents[id]
    status = await agent.refresh()
    return JSONResponse({"status":status})

@app.route("/registrar/{id:int}/refresh", methods=["GET"])
async def refresh_hosting_provider(request):
    """
    summary: Fetch a fresh copy of the information about the registrar for this agent.
    description: Used to force a fresh copy of the details to be fetched from the API.
    responses:
      200:
        description:
        examples:
          {"status": "ok"}
    """
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    id = request.path_params['id']
    agent = m.registrar_agents[id]
    status = await agent.refresh()
    return JSONResponse({"status":status})

@app.route("/reconcile", methods=["GET"])
async def reconcile(request):
    """
    summary: Trigger a full reconciliation process.
    description: Reports OK, then runs in the background. Status events will be logged to the standard log streams for now, but should eventually be routed to a log management system for indexing/searching/monitoring/alerting etc.
    responses:
      200:
        description: CSV file accepted.
        examples:
          {"status": "ok"}
    """
    if not request.user.is_authenticated:
        return UnauthenticatedResponse()
    await m.reconcile()
    return JSONResponse({"status":"ok"})

@app.route("/schema", methods=["GET"], include_in_schema=False)
def openapi_schema(request):
    return schemas.OpenAPIResponse(request=request)

@app.on_event("startup")
async def startup():
    _logger.debug("Connecting to database...")
    await database.connect()

    _logger.debug("Instantiating manager...")
    global m
    m = manager.Manager()
    #_logger.info("Adding test task to manager task queue...")
    #await m.taskq.put({
    #    "task": 1,
    #    "notes": "Testing"
    #})

    _logger.info("Running manager...")
    await m.run()

@app.on_event("shutdown")
async def shutdown():
    _logger.info("Disconnecting from database...")
    await database.disconnect()


def main():
    uvicorn.run(app, host='0.0.0.0', port=8000)

if __name__ == "__main__":
    main()
