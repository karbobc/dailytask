#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from collections.abc import Sequence
from enum import Enum
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from ..common import config, utils

log = utils.get_logger(name="ntfy", log_level=config.LOG_LEVEL, log_file_path=f"{config.LOG_DIR}/ntfy.log")


class NtfyPriority(Enum):
    MIN_PRIORITY = 1
    LOW_PRIORITY = 2
    DEFAULT_PRIORITY = 3
    HIGH_PRIORITY = 4
    MAX_PRIORITY = 5


class NtfyAttachment:
    filename: str
    url: str | None
    local_path: str | None

    def __init__(self, filename: str, url: str | None = None, local_path: str | None = None) -> None:
        assert url is not None or local_path is not None
        self.filename = filename
        self.url = url
        self.local_path = local_path


class NtfyClient:
    session: httpx.AsyncClient

    def __init__(self, base_url: str, username: str | None = None, password: str = None) -> None:
        self.session = httpx.AsyncClient(
            base_url=base_url,
            auth=httpx.BasicAuth(username, password) if username and password else None,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(httpx.TimeoutException),
    )
    async def send(
        self,
        topic: str,
        message: str,
        title: str | None = None,
        priority: NtfyPriority | None = None,
        tags: Sequence[str] | None = None,
        click: str | None = None,
        icons: str | None = None,
        markdown: bool = False,
        delay: str | None = None,
        email: str | None = None,
        attachment: NtfyAttachment | None = None,
    ) -> dict[str, Any]:
        data = {
            "topic": topic,
            "message": message,
            **({"title": title} if title else {}),
            **({"priority": priority.value} if priority else {}),
            **({"tags": [tags] if isinstance(tags, str) else list(tags)} if tags else {}),
            **({"click": click} if click else {}),
            **({"icons": icons} if icons else {}),
            **({"markdown": markdown} if markdown else {}),
            **({"delay": delay} if delay else {}),
            **({"email": email} if email else {}),
            **({"filename": attachment.filename} if attachment else {}),
            **({"attach": attachment.url} if attachment and attachment.url else {}),
        }
        # TODO support attach local file
        response = await self.session.put(url="/", json=data)
        result = response.json()
        if result.get("error") is not None:
            log.error("ntfy send error, result: %s", result)
            return result
        log.info("ntfy send success, result: %s", result)
        return result
