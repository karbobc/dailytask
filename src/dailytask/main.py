#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import argparse
import asyncio

import uvicorn

from .app import app
from .common import config
from .scheduler import redsea_scheduler, yunyu_scheduler


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yunyu", action="store_true", help="")
    parser.add_argument("--redsea", action="store_true", help="")
    parser.add_argument("--server", action="store_true", help="")
    parser.add_argument("--debug", action="store_true", help="")
    args = parser.parse_args()
    if args.yunyu:
        await yunyu_scheduler.fetch_daily_bills()
        return
    if args.redsea:
        if args.debug:
            await redsea_scheduler.lazy()
            return
        await redsea_scheduler.lazy_with_random_delay_in_workday()
    if args.server:
        host = "127.0.0.1" if args.debug else "0.0.0.0"
        port = 17777 if args.debug else 7777
        uvicorn_config = uvicorn.Config(app, host=host, port=port, log_level=config.LOG_LEVEL, reload=args.debug)
        server = uvicorn.Server(uvicorn_config)
        await server.serve()


def run() -> None:
    asyncio.run(main())
