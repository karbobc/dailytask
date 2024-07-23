#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from dailytask.common import config

from ._ntfy import NtfyAttachment, NtfyClient, NtfyPriority

ntfy = NtfyClient(config.NTFY_BASE_URL, config.NTFY_USERNAME, config.NTFY_PASSWORD)

__all__ = [
    "ntfy",
    "NtfyClient",
    "NtfyPriority",
    "NtfyAttachment",
]
