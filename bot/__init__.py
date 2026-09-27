"""Bot package root for high-speed Wzgram + Multi-Session Media Pool architecture."""

import importlib.util
import os
from typing import Any


def __getattr__(name: str) -> Any:
    if name == "Bot":
        bot_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bot.py"))
        spec = importlib.util.spec_from_file_location("_root_bot_module", bot_py)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.Bot
    raise AttributeError(f"module 'bot' has no attribute {name!r}")
