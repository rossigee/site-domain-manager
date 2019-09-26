from fastapi import Depends, FastAPI, File, HTTPException
from starlette.responses import JSONResponse, Response
from starlette.middleware.cors import CORSMiddleware

import uvicorn

from sdmgr import settings, manager
from sdmgr.db import *
from sdmgr.oauth2 import *
from sdmgr.agent import *

import signal
import asyncio

import logging
_logger = logging.getLogger(__name__)


m: manager.Manager = manager.m

from sdmgr.auth.router import router as auth_router
from sdmgr.registrar.router import router as registrar_router
from sdmgr.dns_provider.router import router as dns_router
from sdmgr.hosting.router import router as hosting_router
from sdmgr.waf.router import router as waf_router
from sdmgr.notifiers.router import router as notifiers_router
from sdmgr.sites.router import router as sites_router
from sdmgr.domains.router import router as domains_router


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


@app.get("/reconcile")
async def reconcile(user = Depends(get_current_user)):
    """
    Trigger a full reconciliation process. Status events will be logged to the standard log streams for now, but should eventually be routed to a log management system for indexing/searching/monitoring/alerting etc.
    """
    status = await m.reconcile()
    return JSONResponse({
        "status": status
    })


@app.get("/agents")
async def agents(user = Depends(get_current_user)):
    """
    Returns the list of available agent modules, and their settings. Allows
    the UI to request a list of available agents that can be configured, and
    the configuration settings that each agent depends on.
    """
    return JSONResponse(await fetch_available_agents_and_settings())


@app.get("/metrics")
async def metrics():
    """
    Present statistics metrics to Prometheus for gathering/reporting.
    """
    metrics = await m.metrics()
    output = ""

    def format_metric_header(id, description, type):
        text = f"# HELP sdmgr_{id} {description}\n"
        text += f"# TYPE sdmgr_{id} {type}\n"
        return text

    def format_metric(id, description, type, val):
        text = format_metric_header(id, description, type)
        text += f"sdmgr_{id} {val}\n\n"
        return text

    for id in metrics:
        val = metrics[id]

        if id == "total_domains":
            output += format_metric(id, "Count of domains in state database", "gauge", val)
        elif id == "registrar_registered_domains":
            output += format_metric(id, "Count of domains successfully registered with registrars", "gauge", val)
        elif id == "dns_hosted_domains":
            output += format_metric(id, "Count of domains successfully hosted by DNS providers", "gauge", val)

        elif id == "agent_counts":
            output += format_metric_header(id, f"Number of active service provider agents", "gauge")
            for type in val:
                fullid = f"sdmgr_agent_count" + '{type="' + type + '"}'
                output += f"{fullid} {val[type]}\n"
            output += "\n"

    return Response(content=output, media_type="text/plain")


app.include_router(auth_router)
app.include_router(registrar_router)
app.include_router(dns_router)
app.include_router(waf_router)
app.include_router(hosting_router)
app.include_router(notifiers_router)
app.include_router(sites_router)
app.include_router(domains_router)


@app.on_event("startup")
async def startup():
    _logger.debug("Setting up signal handlers on main event loop...")
    loop = asyncio.get_event_loop()
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(signal=s)))
    loop.set_exception_handler(handle_exception)

    _logger.debug("Loading modules...")
    await load_and_register_agents()

    _logger.debug("Connecting to database...")
    await database.connect()

    _logger.debug("Running manager...")
    await m.run()

@app.on_event("shutdown")
async def shutdown(signal = None):
    if signal:
        _logger.info(f"Received signal: {signal}")

    _logger.info("Disconnecting from database...")
    await database.disconnect()

    _logger.info("Cancelling remaining tasks...")
    for task in asyncio.Task.all_tasks():
        task.cancel()

    _logger.info("Stopping main loop...")
    loop = asyncio.get_event_loop()
    loop.stop()

    _logger.debug("Removing signal handlers on main event loop...")
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.remove_signal_handler(s)

def handle_exception(loop, context):
    msg = context.get("exception", context["message"])
    logging.error(f"Caught exception in main thread: {msg}")
    print(context)

def main():
    # TODO: Arguments to change host/post?
    uvicorn.run(app, host='0.0.0.0', port=8000)

if __name__ == '__main__':
    main()
