#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Any

from apscheduler import AsyncScheduler, ScheduleLookupError
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

# simple database
db: list["Task"] = []
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


class TaskType(Enum):
    YUNYU = "yunyu"
    REDSEA = "redsea"


class DateTask(BaseModel):
    id: str
    run_time: str
    task_type: TaskType


class CronTask(BaseModel):
    id: str
    cron: str
    next_run_time: str
    last_run_time: str | None
    running: bool
    task_type: TaskType


class Task(BaseModel):
    id: str
    type: TaskType


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
    for cron in config.YUNYU_CRON:
        task_id = await async_scheduler.add_schedule(
            yunyu_scheduler.fetch_daily_bills,
            trigger=CronTrigger.from_crontab(cron),
        )
        db.append(Task(id=task_id, type=TaskType.YUNYU))
        log.info("starting yunyu cron: %s", cron)
    for cron in config.REDSEA_CRON:
        task_id = await async_scheduler.add_schedule(
            redsea_scheduler.lazy_with_random_delay_in_workday,
            trigger=CronTrigger.from_crontab(cron),
        )
        db.append(Task(id=task_id, type=TaskType.REDSEA))
        log.info("starting redsea cron: %s", cron)
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
    data = []
    global db
    for task in db[:]:
        try:
            schedule = await async_scheduler.get_schedule(task.id)
        except ScheduleLookupError:
            db.remove(task)
            continue
        if not isinstance(schedule.trigger, CronTrigger):
            continue
        trigger: CronTrigger = schedule.trigger
        data.append(
            CronTask(
                id=task.id,
                cron=" ".join([trigger.minute, trigger.hour, trigger.day, trigger.month, trigger.day_of_week]),
                next_run_time=schedule.next_fire_time.strftime(DATETIME_FORMATTER),
                last_run_time=schedule.last_fire_time.strftime(DATETIME_FORMATTER) if schedule.last_fire_time else None,
                running=not schedule.paused,
                task_type=task.type,
            )
        )
    return ApiResult.ok(data=data)


@app.patch("/api/task/cron/pause/{id}")
async def pause_cron_task(task_id: str = Path(alias="id")) -> Response:
    await async_scheduler.pause_schedule(task_id)
    return ApiResult.ok()


@app.patch("/api/task/cron/resume/{id}")
async def resume_cron_task(task_id: str = Path(alias="id")) -> Response:
    await async_scheduler.unpause_schedule(task_id)
    return ApiResult.ok()


@app.get("/api/task/date")
async def get_date_task() -> Response:
    data = []
    global db
    for task in db[:]:
        try:
            schedule = await async_scheduler.get_schedule(task.id)
        except ScheduleLookupError:
            db.remove(task)
            continue
        if not isinstance(schedule.trigger, DateTrigger):
            continue
        trigger: DateTrigger = schedule.trigger
        data.append(
            DateTask(
                id=task.id,
                run_time=trigger.run_time.strftime(DATETIME_FORMATTER),
                task_type=task.type,
            )
        )
    return ApiResult.ok(data=data)


@app.post("/api/task")
async def new_task(
    run_time: datetime | None = Body(default=None, embed=True), task_type: TaskType = Body(embed=True)
) -> Response:
    func: Callable | None
    match task_type:
        case TaskType.YUNYU:
            func = yunyu_scheduler.fetch_daily_bills
        case TaskType.REDSEA:
            func = redsea_scheduler.lazy
        case _:
            func = None
    if func is None:
        return ApiResult.e(status.HTTP_400_BAD_REQUEST, "Unsupported task type")
    task_id = str(
        await (
            async_scheduler.add_schedule(func, trigger=DateTrigger(run_time))
            if run_time
            else async_scheduler.add_job(func)
        )
    )
    # update task into db
    global db
    db.append(Task(id=task_id, type=task_type))
    data = {
        "id": task_id,
        **({"run_time": run_time.strftime(DATETIME_FORMATTER)} if run_time else {}),
        "task_type": task_type,
    }
    return ApiResult.ok(data=data)


@app.delete("/api/task/date/{id}")
async def delete_date_task(task_id: str = Path(alias="id")) -> Response:
    await async_scheduler.remove_schedule(task_id)
    return ApiResult.ok()


@app.delete("/api/task/date")
async def delete_all_date_task() -> Response:
    for task in db:
        try:
            schedule = await async_scheduler.get_schedule(task.id)
        except ScheduleLookupError:
            continue
        if not isinstance(schedule.trigger, DateTrigger):
            continue
        await async_scheduler.remove_schedule(task.id)
    return ApiResult.ok()
