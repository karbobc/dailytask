#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import hashlib
import logging
import os
import secrets
import string
import sys
from logging.handlers import RotatingFileHandler
from typing import TypeVar

import httpx

_T = TypeVar("_T")


def get_env(key: str, default: _T = "") -> _T | str:
    """
    Get an environment variable, return empty str if it doesn't exist.
    The optional second argument can specify an alternate default.
    """
    return os.getenv(key) or default


def get_env_list(key: str, default: list[_T] | None = None) -> list[_T] | list[str]:
    """
    Get an environment variable, which split by comma, return None if it doesn't exist.
    The optional second argument can specify an alternate default.
    """
    value = get_env(key)
    if not value:
        return default or []
    return value.split(",")


def get_required_env(key: str) -> str:
    """
    Get an environment variable, which must exist, otherwise sys.exit(1) will be called.
    """
    value = get_env(key)
    if not value:
        print(f"`{key}` must be set!!!")
        sys.exit(1)
    return value


def get_required_env_list(key: str) -> list[str]:
    """
    Get an environment variable, which must exist and split by comma,
    otherwise sys.exit(1) will be called.
    """
    value = get_env_list(key)
    if not value:
        print(f"`{key}` must be set!!!")
        sys.exit(1)
    return value


def get_md5_str(data: str) -> str:
    """
    Get MD5 digest str.
    """
    md5 = hashlib.md5()
    md5.update(data.encode())
    return md5.hexdigest()


def generate_random_str(length: int) -> str:
    """
    Generate securer random str.
    """
    characters = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(characters) for _ in range(length))


def is_workday(base_url: str) -> bool:
    """
    Determine whether the today is a workday.
    """
    url = f"{base_url}/workday/today"
    response = httpx.get(url=url, timeout=httpx.Timeout(24))
    result = response.json()
    assert result["success"] is True
    return result["data"]["isWorkday"]


def get_logger(name: str, log_level: int = logging.INFO, log_file_path: str = None) -> logging.Logger:
    logger = logging.getLogger(name)
    # There is already a handler, return directly to prevent adding duplicate handlers,
    # it will cause duplicate log output
    if logger.handlers:
        return logger
    logger.setLevel(log_level)
    # Console handler output formatter
    formatter = (
        "%(asctime)s.%(msecs)d 【%(name)s】 %(levelname)s %(process)d --- [%(threadName)s-%(thread)d] "
        "<%(pathname)s-line:%(lineno)d>: %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(fmt=formatter, datefmt=date_format))
    logger.addHandler(console_handler)
    # Close handler
    console_handler.close()

    # No need to create a file handler
    if log_file_path is None:
        return logger

    # Create directory first if it doesn't exist
    if not os.path.exists(os.path.dirname(log_file_path)):
        os.mkdir(os.path.dirname(log_file_path), mode=0x700)
    # File handler settings
    file_handler = RotatingFileHandler(
        filename=log_file_path,
        mode="a+",
        maxBytes=64 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    # File handler output formatter
    file_handler.setFormatter(logging.Formatter(fmt=formatter, datefmt=date_format))
    logger.addHandler(file_handler)
    # Close handler
    file_handler.close()
    return logger
