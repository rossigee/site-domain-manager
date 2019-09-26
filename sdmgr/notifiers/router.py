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


class NotifierModel(BaseModel):
    agent_module: str
    label: str


@router.get("/notifiers", tags=["notifiers"])
async def list_notifiers(user = Depends(get_current_user)):
    return JSONResponse({
        "notifiers": [await notifier.serialize() for notifier in await Notifier.objects.all()]
    })


@router.post("/notifiers", tags=["notifiers"])
async def create_notifier(notifier: NotifierModel, user = Depends(get_current_user)):
    try:
        data = notifier.dict()
        instance = await Notifier.objects.create(
            label = data['label'],
            agent_module = data['agent_module'],
            updated_time = datetime.datetime.now(),
            state = {},
        )
        content = await instance.serialize()
        return JSONResponse(status_code=HTTP_201_CREATED, content=content)
    except pymysql.err.IntegrityError as mie:
        return JSONResponse(status_code=422, content={
            "detail": f"Notifier already exists with label '{data['label']}''."
        })
    except Exception as e:
        _logger.exception(e)


@router.get("/notifiers/{id:int}", tags=["notifiers"])
async def get_notifier(id: int, user = Depends(get_current_user)):
    notifier = await Notifier.objects.get(id = id)
    r = await notifier.serialize(full = True)
    try:
        agent = m.notifier_agents[id]
        r['refresh_method'] = await agent.get_refresh_method()
        status = await agent.get_status()
        r['domain_count_total'] = status['domain_count_total']
        r['domain_count_active'] = status['domain_count_active']
    except NotImplementedError:
        pass
    except KeyError:
        _logger.error(f"No notifier agent for id '{id}'")
        pass
    return JSONResponse(r)
