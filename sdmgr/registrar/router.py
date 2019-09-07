from fastapi import APIRouter, Depends, File
from starlette.responses import JSONResponse, Response
from starlette.status import HTTP_201_CREATED
import pymysql

from sdmgr.oauth2 import *
from sdmgr.db import *
from sdmgr.manager import m

from pydantic import BaseModel

import datetime

import logging
_logger = logging.getLogger(__name__)

router = APIRouter()


class RegistrarModel(BaseModel):
    agent_module: str
    label: str


@router.get("/registrars", tags=["registrars"])
async def list_registrars(user = Depends(get_current_user)):
    return JSONResponse({
        "registrars": [await registrar.serialize() for registrar in await Registrar.objects.all()]
    })


@router.post("/registrars", tags=["registrars"])
async def create_registrar(registrar: RegistrarModel, user = Depends(get_current_user)):
    try:
        data = registrar.dict()
        instance = await Registrar.objects.create(
            label = data['label'],
            agent_module = data['agent_module'],
            updated_time = datetime.datetime.now(),
            state = {},
        )
        content = await instance.serialize()
        return JSONResponse(status_code=HTTP_201_CREATED, content=content)
    except pymysql.err.IntegrityError as mie:
        return JSONResponse(status_code=422, content={
            "detail": f"Registrar already exists with label '{data['label']}''."
        })
    except Exception as e:
        _logger.exception(e)


@router.get("/registrars/{id:int}", tags=["registrars"])
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

@router.post("/registrars/{id:int}/csvfile", tags=["registrars"])
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

@router.post("/registrars/{id:int}/jsonfile", tags=["registrars"])
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

@router.get("/registrars/{id:int}/refresh", tags=["registrars"])
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

@router.get("/registrars/{id:int}/domains/{domainname}/status", tags=["registrars"])
async def get_registrar_status_for_domain(id: int, domainname, user = Depends(get_current_user)):
    """
    Fetch the status of a domain from the registrar. Used to show the current status and expiry date of a given domain with the registrar. This can fetch the data directly from the registrar's API, or use cached data from a recent CSV download, depending on the registrar's capabilities.
    """
    agent = m.registrar_agents[id]
    status = await agent.get_status_for_domain(domainname)
    return JSONResponse({
        "status": status
    })
