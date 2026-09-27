"""Core high-speed networking, hardware crypto, and RAM cache modules."""

from bot.core.fast_crypto import (
    FastCryptoEngine,
    MultiSessionMediaPool,
    configure_wzgram_environment,
    install_fast_event_loop,
    release_memory,
)
from bot.core.cache import (
    LRUTTLCache,
    SmartRAMWorkspace,
    cache_manager,
    ram_workspace,
)

__all__ = [
    "FastCryptoEngine",
    "MultiSessionMediaPool",
    "configure_wzgram_environment",
    "install_fast_event_loop",
    "release_memory",
    "LRUTTLCache",
    "SmartRAMWorkspace",
    "cache_manager",
    "ram_workspace",
]
