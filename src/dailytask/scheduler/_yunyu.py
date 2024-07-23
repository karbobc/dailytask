#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import traceback
from datetime import datetime
from typing import Any

from ..api import yunyu
from ..common import config, utils
from ..notification import NtfyPriority, ntfy

log = utils.get_logger(
    name="scheduler-yunyu",
    log_level=config.LOG_LEVEL,
    log_file_path=f"{config.LOG_DIR}/yunyu.log",
)


async def fetch_daily_bills() -> None:
    log.info("fetch daily bills start...")
    try:
        data = await yunyu.fetch_prepay_energy_bills()
        balance = await yunyu.fetch_prepay_balance()
        data: dict[str, Any] = data["content"][0]
        message = (
            f"结算时间: {datetime.fromtimestamp(int(data["consumeDate"]) / 1000).strftime("%Y-%m-%d %H:%M:%S")}\n"
            f"用电量: {data["avgUsing"]}度\n"
            f"单价: {data["unitPrice"]} × {data["rate"]}\n"
            f"小计: {data["fee"]}\n"
            f"余额: {balance}"
        )
        await ntfy.send(topic="daily", title="电费账单", message=message)
    except Exception:
        log.error("fetch daily bills error!!!", exc_info=True)
        await ntfy.send(
            topic="error",
            message=f"获取电费账单异常\n{traceback.format_exc()}",
            priority=NtfyPriority.MAX_PRIORITY,
        )
    log.info("fetch daily bills end...")
