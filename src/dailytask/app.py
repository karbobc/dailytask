#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from apscheduler import AsyncScheduler, Schedule
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from fastapi import Body, FastAPI, Path, Request, Response, status
from fastapi.exceptions import (
    RequestValidationError,
    StarletteHTTPException,
)
from pydantic import BaseModel
from starlette.types import ASGIApp, Receive, Scope, Send

from .common import config, utils
from .scheduler import redsea_scheduler, yunyu_scheduler

async_scheduler = AsyncScheduler()
log = utils.get_logger("uvicorn")
DATETIME_FORMATTER = "%Y-%m-%d %H:%M:%S"


class ApiResult(BaseModel):
    code: str = str(status.HTTP_200_OK)
    success: bool = True
    message: str = "OK"
    data: Any | None = None

    @staticmethod
    def ok(data: Any | None = None) -> Response:
        result = ApiResult(data=data)
        return Response(
            content=result.model_dump_json(exclude_none=True),
            status_code=status.HTTP_200_OK,
        )

    @staticmethod
    def e(status_code: int, message: str):
        result = ApiResult(
            code=str(status_code),
            success=False,
            message=message,
        )
        return Response(
            content=result.model_dump_json(exclude_none=True),
            status_code=status_code,
        )


class DateTask(BaseModel):
    id: str
    run_time: str


class CronTask(BaseModel):
    id: str
    cron: str
    next_run_time: str
    last_run_time: str | None
    running: bool


class SchedulerMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        scheduler: AsyncScheduler,
    ) -> None:
        self.app = app
        self.scheduler = scheduler

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            async with self.scheduler:
                await self.scheduler.start_in_background()
                await self.app(scope, receive, send)
        else:
            await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("API_TOKEN: %s", config.API_TOKEN)
    tasks = []
    for cron in config.YUNYU_CRON:
        tasks.append(
            async_scheduler.add_schedule(
                yunyu_scheduler.fetch_daily_bills,
                trigger=CronTrigger.from_crontab(cron),
            )
        )
        log.info("starting yunyu cron: %s", cron)
    for cron in config.REDSEA_CRON:
        tasks.append(
            async_scheduler.add_schedule(
                redsea_scheduler.lazy_with_random_delay_in_workday,
                trigger=CronTrigger.from_crontab(cron),
            )
        )
        log.info("starting redsea cron: %s", cron)
    await asyncio.gather(*tasks)
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SchedulerMiddleware, scheduler=async_scheduler)


@app.middleware("http")
async def interceptor(request: Request, call_next) -> Response:
    token = request.headers.get("Authorization")
    if token == config.API_TOKEN:
        return await call_next(request)
    return ApiResult.e(status.HTTP_401_UNAUTHORIZED, "Unauthorized")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, e: Exception) -> Response:
    return ApiResult.e(status.HTTP_500_INTERNAL_SERVER_ERROR, f"internal server error: {repr(e)}")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, e: StarletteHTTPException) -> Response:
    return ApiResult.e(e.status_code, e.detail)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, e: RequestValidationError) -> Response:
    return ApiResult.e(status.HTTP_400_BAD_REQUEST, f"incorrect request parameter: {e.errors()}")


@app.get("/api/task/cron")
async def get_cron_task() -> Response:
    schedulers = await async_scheduler.get_schedules()
    filtered_schedulers: list[Schedule] = list(filter(lambda x: isinstance(x.trigger, CronTrigger), schedulers))
    data = []
    for scheduler in filtered_schedulers:
        trigger: CronTrigger = scheduler.trigger
        data.append(
            CronTask(
                id=scheduler.id,
                cron=" ".join([trigger.minute, trigger.hour, trigger.day, trigger.month, trigger.day_of_week]),
                next_run_time=scheduler.next_fire_time.strftime(DATETIME_FORMATTER),
                last_run_time=scheduler.last_fire_time.strftime(DATETIME_FORMATTER)
                if scheduler.last_fire_time
                else None,
                running=not scheduler.paused,
            )
        )
    return ApiResult.ok(data=data)


@app.put("/api/task/cron/pause/{id}")
async def pause_cron_task(task_id: str = Path(alias="id")) -> Response:
    await async_scheduler.pause_schedule(task_id)
    return ApiResult.ok()


@app.put("/api/task/cron/resume/{id}")
async def resume_cron_task(task_id: str = Path(alias="id")) -> Response:
    await async_scheduler.unpause_schedule(task_id)
    return ApiResult.ok()


@app.get("/api/task/date")
async def get_date_task() -> Response:
    schedulers = await async_scheduler.get_schedules()
    filtered_schedulers: list[Schedule] = list(filter(lambda x: isinstance(x.trigger, DateTrigger), schedulers))
    data = []
    for scheduler in filtered_schedulers:
        trigger: DateTrigger = scheduler.trigger
        data.append(DateTask(id=scheduler.id, run_time=trigger.run_time.strftime(DATETIME_FORMATTER)))
    return ApiResult.ok(data=data)


@app.post("/api/task/date")
async def new_date_task(run_time: datetime = Body(embed=True)) -> Response:
    task_id = await async_scheduler.add_schedule(redsea_scheduler.lazy, trigger=DateTrigger(run_time))
    data = {"id": task_id, "run_time": run_time.strftime(DATETIME_FORMATTER)}
    return ApiResult.ok(data=data)


@app.delete("/api/task/date/{id}")
async def delete_date_task(task_id: str = Path(alias="id")) -> Response:
    await async_scheduler.remove_schedule(task_id)
    return ApiResult.ok()


@app.delete("/api/task/date")
async def delete_all_date_task() -> Response:
    schedulers = await async_scheduler.get_schedules()
    for item in schedulers:
        await async_scheduler.remove_schedule(item.id)
    return ApiResult.ok()
