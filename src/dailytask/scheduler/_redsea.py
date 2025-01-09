#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import asyncio
import random
import traceback

from ..api import redsea
from ..common import config, utils
from ..notification import NtfyPriority, ntfy

log = utils.get_logger(
    name="scheduler-redsea",
    log_level=config.LOG_LEVEL,
    log_file_path=f"{config.LOG_DIR}/redsea.log",
)


async def lazy() -> None:
    log.info("touching fish start...")
    try:
        touch_fish_data = await redsea.touch_fish()
        current_state = touch_fish_data.get("msg")
        data = await redsea.touch_fish_state()
        data = data.get("kqCountSimple", {})
        touch_fish_start_time = data.get("sbDkTime") or data.get("sbDkTime2") or data.get("sbDkTime3")
        touch_fish_start_state = (
            data.get("sbStatusName") or data.get("sbStatusName2") or data.get("sbStatusName3") or "正常"
        )
        touch_fish_start_state_emoji = "✅" if touch_fish_start_state in ["正常", "休息"] else "❌"
        touch_fish_end_time = data.get("xbDkTime") or data.get("xbDkTime2") or data.get("xbDkTime3")
        touch_fish_end_state = (
            data.get("xbStatusName") or data.get("xbStatusName2") or data.get("xbStatusName3") or "正常"
        )
        touch_fish_end_state_emoji = "✅" if touch_fish_end_state in ["正常", "休息"] else "❌"
        message = f"💤：{touch_fish_start_time} {touch_fish_start_state} {touch_fish_start_state_emoji}"
        if touch_fish_end_time:
            message += f"\n🎉：{touch_fish_end_time} {touch_fish_end_state} {touch_fish_end_state_emoji}"
        await ntfy.send(topic="daily", title=f"⏰{current_state}", message=message)
    except Exception:
        log.error("touching fish error!!!", exc_info=True)
        await ntfy.send(
            topic="error",
            message=f"打卡异常\n{traceback.format_exc()}",
            priority=NtfyPriority.MAX_PRIORITY,
        )
    finally:
        log.info("touching fish end...")


async def lazy_in_workday() -> None:
    if not utils.is_workday(config.WORKDAY_BASE_URL):
        log.info("holiday holiday holiday!!!")
        return
    await lazy()


async def lazy_with_random_delay(min_sec: int = 1, max_sec: int = 300) -> None:
    delay_sec = random.randint(min_sec, max_sec)
    log.info(f"touching fish start in {delay_sec} seconds")
    await asyncio.sleep(delay_sec)
    await lazy()


async def lazy_with_random_delay_in_workday(min_sec: int = 1, max_sec: int = 300) -> None:
    if not utils.is_workday(config.WORKDAY_BASE_URL):
        log.info("holiday holiday holiday!!!")
        return
    await lazy_with_random_delay(min_sec, max_sec)
