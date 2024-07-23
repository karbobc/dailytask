#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from dailytask.common import config

from ._redsea import RedSea
from ._yunyu import YunYu

yunyu = YunYu(config.YUNYU_BASE_URL, config.YUNYU_ACCOUNT, config.YUNYU_PASSWORD)
redsea = RedSea(
    config.REDSEA_BASE_URL,
    config.REDSEA_USER_AGENT,
    config.REDSEA_APP_SECRET,
    config.REDSEA_LOGIN_ID,
    config.REDSEA_AGENT_ID,
    config.REDSEA_LAZY_LONGITUDE,
    config.REDSEA_LAZY_LATITUDE,
    config.REDSEA_LAZY_ADDRESS,
)

__all__ = [
    "yunyu",
    "redsea",
]
