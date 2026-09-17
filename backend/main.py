import asyncio
import sys

if sys.platform == "win32":
	asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from backend.api import app

__all__ = ["app"]
