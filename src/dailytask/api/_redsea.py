#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import json
import random
from datetime import datetime
from typing import Any, TypedDict
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from ..common import config, utils

log = utils.get_logger(
    name="api-redsea",
    log_level=config.LOG_LEVEL,
    log_file_path=f"{config.LOG_DIR}/redsea.log",
)


class UnauthorizedError(RuntimeError):
    def __init__(self) -> None:
        message = "Unauthorized"
        super().__init__(message)


class User(TypedDict):
    user_id: str
    user_name: str
    staff_id: str


class RedSea:
    base_url: str
    app_secret: str
    login_id: str
    agent_id: str
    longitude: list[str]
    latitude: list[str]
    address: str
    hostname: str
    user: User
    session: httpx.AsyncClient

    def __init__(
        self,
        base_url: str,
        user_agent: str,
        app_secret: str,
        login_id: str,
        agent_id: str,
        longitude: list[str],
        latitude: list[str],
        address: str,
    ) -> None:
        self.base_url = base_url
        self.app_secret = app_secret
        self.login_id = login_id
        self.agent_id = agent_id
        self.longitude = longitude
        self.latitude = latitude
        self.address = address
        self.hostname = urlparse(base_url).hostname
        self.session = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(24))
        self.session.event_hooks.update(
            {
                "request": [self._request_interceptor],
                "response": [self._response_interceptor],
            }
        )
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Host": self.hostname,
                "Origin": f"https://{self.hostname}",
            }
        )

    async def _request_interceptor(self, request: httpx.Request) -> None:
        if not hasattr(self, "user"):
            self._init()
            raise UnauthorizedError

        await request.aread()
        log.info(
            "request interceptor: %s %s, payload: %s, headers: %s",
            request.method,
            request.url,
            request.content.decode(),
            request.headers,
        )

    async def _response_interceptor(self, response: httpx.Response) -> None:
        # redirect, unauthorized
        if response.status_code == httpx.codes.FOUND and response.headers.get("Location") == "/RedseaPlatform/index":
            self._login()
            raise UnauthorizedError

        # read the response
        await response.aread()
        request = response.request
        log.info(
            "response interceptor: %s %s %s %s payload: %s, headers: %s, result: %s",
            request.method,
            request.url,
            response.http_version,
            response.status_code,
            request.content.decode(),
            response.headers,
            response.text[: 1 << 10],
        )
        try:
            result = response.json()
            if result.get("state") == "Nosession":
                self._login()
                raise UnauthorizedError
        except json.JSONDecodeError:
            pass

    def _init(self) -> None:
        self._login()
        data = self._fetch_user_info()
        self.user = {
            "user_id": data["userId"],
            "user_name": data["userName"],
            "staff_id": data["staffId"],
        }

    def _create_token(self) -> str:
        login_id_type = "EXTERNALUSE"
        timestamp = int(datetime.now().timestamp() * 1_000)
        url = f"{self.base_url}/RedseaPlatform/vwork/third/api/sso.mob"
        params = {
            "method": "createtoken",
            "loginId": self.login_id,
            "loginIdType": login_id_type,
            "timestamp": timestamp,
            "sign": utils.get_md5_str("&".join([self.app_secret, self.login_id, str(timestamp)])),
        }
        response = httpx.get(url=url, params=params)
        result = response.json()
        if result["state"] == "1":
            return result["result"]
        raise RuntimeError(result["meg"])

    def _login(self) -> None:
        url = f"{self.base_url}/RedseaPlatform/vwork/third/api/sso.mob"
        params = {
            "method": "oauthLogin",
            "client": "app",
            "action": "login",
            "token": self._create_token(),
        }
        response = httpx.get(url=url, params=params, follow_redirects=True)
        result = response.json()
        if result["state"] == "1":
            self.session.cookies.update(response.cookies)
            return
        raise RuntimeError(result["tipMsg"])

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((UnauthorizedError, httpx.TimeoutException)),
    )
    def _fetch_user_info(self) -> dict[str, Any]:
        url = f"{self.base_url}/RedseaPlatform/PtUsers.mc"
        params = {
            "method": "getCurUserInfo",
        }
        response = httpx.post(url=url, params=params, cookies=self.session.cookies)
        if not response.text:
            self._login()
            raise UnauthorizedError
        result = response.json()
        return result

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((UnauthorizedError, httpx.TimeoutException)),
    )
    async def touch_fish(self) -> dict[str, Any]:
        url = "/RedseaPlatform/kqCommonDaka.mc"
        headers = {
            "Referer": f"https://{self.hostname}/RedseaPlatform/jsp/kqUni/punchCard/punchCard.jsp?agentId"
                       f"={self.agent_id}=&isQywx=1",
        }
        params = {
            "method": "daka",
        }
        longitude = random.choice(self.longitude)
        latitude = random.choice(self.latitude)
        data = {
            "longitude": longitude,
            "latitude": latitude,
            "address": self.address,
            "actualAddress": f"{longitude},{latitude}",
            "agentId": self.agent_id,
            "imei": "",
            "ssid": "",
            "faceUrl": "",
            "isLeave": "false",
            "clientType": "1",
            "mockGpsProbability": "",
        }
        response = await self.session.post(url=url, headers=headers, params=params, data=data)
        result = response.json()
        if result["state"] == "1":
            return result["result"]
        raise RuntimeError(result["meg"])

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((UnauthorizedError, httpx.TimeoutException)),
    )
    async def touch_fish_state(self) -> dict[str, Any]:
        url = "/RedseaPlatform/dingDingKqInteface.mc"
        headers = {
            "Referer": f"https://{self.hostname}/RedseaPlatform/jsp/kqUni/punchCard/punchCard.jsp?agentId"
                       f"={self.agent_id}=&isQywx=1",
        }
        params = {
            "method": "getDayTeam",
            "userId": self.user["user_id"],
        }
        response = await self.session.post(url=url, headers=headers, params=params)
        result = response.json()
        if result["state"] == "1":
            return result["result"]
        raise RuntimeError(result["meg"])
