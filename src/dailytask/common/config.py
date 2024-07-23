#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import logging

from . import utils

# yunyu
YUNYU_BASE_URL = utils.get_required_env("YUNYU_BASE_URL")
YUNYU_ACCOUNT = utils.get_required_env("YUNYU_ACCOUNT")
YUNYU_PASSWORD = utils.get_required_env("YUNYU_PASSWORD")
YUNYU_CRON = utils.get_required_env_list("YUNYU_CRON")

# red sea
REDSEA_BASE_URL = utils.get_required_env("REDSEA_BASE_URL")
REDSEA_USER_AGENT = utils.get_required_env("REDSEA_USER_AGENT")
REDSEA_APP_SECRET = utils.get_required_env("REDSEA_APP_SECRET")
REDSEA_LOGIN_ID = utils.get_required_env("REDSEA_LOGIN_ID")
REDSEA_AGENT_ID = utils.get_required_env("REDSEA_AGENT_ID")
REDSEA_LAZY_LONGITUDE = utils.get_required_env_list("REDSEA_LAZY_LONGITUDE")
REDSEA_LAZY_LATITUDE = utils.get_required_env_list("REDSEA_LAZY_LATITUDE")
REDSEA_LAZY_ADDRESS = utils.get_required_env("REDSEA_LAZY_ADDRESS")
REDSEA_CRON = utils.get_required_env_list("REDSEA_CRON")

# ntfy
NTFY_BASE_URL = utils.get_required_env("NTFY_BASE_URL")
NTFY_USERNAME = utils.get_required_env("NTFY_USERNAME")
NTFY_PASSWORD = utils.get_required_env("NTFY_PASSWORD")

# workday
WORKDAY_BASE_URL = utils.get_required_env("WORKDAY_BASE_URL")

# server
API_TOKEN = utils.get_env("API_TOKEN") or utils.generate_random_str(32)

# basic config
LOG_DIR = utils.get_env("LOG_DIR", "log")
CACHE_DIR = utils.get_env("CACHE_DIR", "cache")
LOG_LEVEL = utils.get_env("LOG_LEVEL", logging.INFO)
