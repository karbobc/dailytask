#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import threading
from typing import Any, TypedDict, TypeVar

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from ..common import config, utils

log = utils.get_logger(
    name="api-yunyu",
    log_level=config.LOG_LEVEL,
    log_file_path=f"{config.LOG_DIR}/yunyu.log",
)
T = TypeVar("T", dict[str, Any], list[Any], str)


class R(TypedDict):
    code: int
    success: bool
    msg: str
    data: T


class UnauthorizedError(RuntimeError):
    def __init__(self) -> None:
        message = "Unauthorized"
        super().__init__(message)


class YunYu:
    base_url: str
    account: str
    password: str
    refresh_token: str = ""
    access_token: str = ""
    lock: threading.RLock
    session: httpx.AsyncClient

    def __init__(self, base_url: str, account: str, password: str) -> None:
        self.base_url = base_url
        self.account = account
        self.password = password
        self.session = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(24))
        self.session.event_hooks.update(
            {
                "request": [self._request_interceptor],
                "response": [self._response_interceptor],
            }
        )
        self.lock = threading.RLock()
        self._get_refresh_token_from_file()
        self._get_access_token_from_file()

    def _get_refresh_token_from_file(self) -> None:
        """
        Fetch refresh token from file.
        """
        refresh_token_path = f"{config.CACHE_DIR}/refresh_token"
        with self.lock:
            if os.path.exists(refresh_token_path) is False:
                return
            with open(refresh_token_path) as fp:
                self.refresh_token = fp.read()

    def _get_access_token_from_file(self) -> None:
        """
        Fetch access token from file.
        """
        access_token_path = f"{config.CACHE_DIR}/access_token"
        with self.lock:
            if os.path.exists(access_token_path) is False:
                return
            with open(access_token_path) as fp:
                self.access_token = fp.read()

    def _save_refresh_token_to_file(self) -> None:
        """
        Persistent refresh token.
        """
        refresh_token_path = f"{config.CACHE_DIR}/refresh_token"
        with self.lock:
            if os.path.exists(config.CACHE_DIR) is False:
                os.mkdir(config.CACHE_DIR, mode=0x700)
            with open(refresh_token_path, "w+") as fp:
                fp.write(self.refresh_token)

    def _save_access_token_to_file(self) -> None:
        """
        Persistent access token.
        """
        access_token_path = f"{config.CACHE_DIR}/access_token"
        with self.lock:
            if os.path.exists(config.CACHE_DIR) is False:
                os.mkdir(config.CACHE_DIR, mode=0x700)
            with open(access_token_path, "w+") as fp:
                fp.write(self.access_token)

    async def _request_interceptor(self, request: httpx.Request) -> None:
        request.headers.update({"Cookie": f"SESSION={self.access_token}"})
        log.info(
            "request interceptor: %s %s, payload: %s, headers: %s",
            request.method,
            request.url,
            request.content.decode(),
            request.headers,
        )

    async def _response_interceptor(self, response: httpx.Response) -> None:
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
        result: R = response.json()
        if result["code"] == -5:
            self._refresh_access_token()
            raise UnauthorizedError

    def _apply_token(self) -> None:
        """
        Fetch infinite refresh token by access token.
        """
        url = f"{self.base_url}/user/login/applyToken"
        cookies = {
            "SESSION": self.access_token,
        }
        response = httpx.post(url=url, cookies=cookies)
        result: R = response.json()
        if result["success"] is False:
            log.error("failed to apply token, param: %s, result: %s", cookies, result)
            return
        with self.lock:
            self.refresh_token = result["data"]
        self._save_refresh_token_to_file()
        log.info("apply token success, refresh_token: %s", self.refresh_token)

    def _login(self) -> None:
        """
        Login, and then fetch refresh token and access token.
        """
        url = f"{self.base_url}/user/login"
        data = {
            "account": self.account,
            "password": self.password,
        }
        response = httpx.post(url=url, json=data)
        result: R = response.json()
        if result["success"] is False:
            log.error("failed to login, param: %s, result: %s", data, result)
            return
        with self.lock:
            self.access_token = result["data"].get("accessToken")
        self._save_access_token_to_file()
        log.info("login success, access_token: %s", self.access_token)
        self._apply_token()

    def _refresh_access_token(self) -> None:
        """
        Fetch access token by refresh token.
        """
        url = f"{self.base_url}/user/login/loginByToken"
        data = {
            "token": self.refresh_token,
        }
        response = httpx.post(url=url, json=data)
        result: R = response.json()
        if result["code"] != 0:
            log.error("failed to refresh token: param: %s, result: %s", data, result)
            self._login()
            return
        with self.lock:
            self.access_token = result["data"].get("accessToken")
        self._save_access_token_to_file()
        log.info("refresh token success, access_token: %s", self.access_token)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((UnauthorizedError, httpx.TimeoutException)),
    )
    async def fetch_prepay_energy_bills(self, page: int = 1) -> dict[str, Any]:
        url = "/smart/prepayEnergyList/page"
        data = {
            "pageNo": page,
        }
        response = await self.session.post(url=url, json=data)
        result: R = response.json()
        if result["success"]:
            return result["data"]
        raise RuntimeError(result["msg"])

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((UnauthorizedError, httpx.TimeoutException)),
    )
    async def fetch_prepay_balance(self) -> float | str:
        url = "/user/prepayBalance"
        response = await self.session.get(url=url)
        result: R = response.json()
        if result["success"]:
            return result["data"]["balance"]
        raise RuntimeError(result["msg"])
