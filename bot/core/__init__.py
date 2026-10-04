"""Core RAM cache and memory management modules."""

from bot.core.cache import (
    LRUTTLCache,
    SmartRAMWorkspace,
    cache_manager,
    ram_workspace,
    release_memory,
)

from bot.core.fast_crypto import (
    FastCryptoEngine,
    MultiSessionMediaPool,
    compute_dynamic_pool_size,
    configure_wzgram_environment,
)

__all__ = [
    "release_memory",
    "LRUTTLCache",
    "SmartRAMWorkspace",
    "cache_manager",
    "ram_workspace",
    "FastCryptoEngine",
    "MultiSessionMediaPool",
    "compute_dynamic_pool_size",
    "configure_wzgram_environment",
]

