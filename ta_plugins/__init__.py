"""ta_plugins — a lightweight plugin system for TradingAgents.

Public API:
    Plugin            -- dataclass describing a plugin
    register(plugin)  -- register a plugin in the global registry
    get_registry()    -- access the global registry
    apply_plugins()   -- apply all registered plugins to the tradingagents
                         graph layer. Call BEFORE creating TradingAgentsGraph.
    reset_patches()   -- restore pristine upstream state (mainly for tests)

Zero third-party dependencies beyond tradingagents itself.
"""

from .registry import Plugin, PluginRegistry, get_registry, register
from .patching import apply_plugins, reset_patches

__all__ = [
    "Plugin",
    "PluginRegistry",
    "get_registry",
    "register",
    "apply_plugins",
    "reset_patches",
]

__version__ = "0.1.0"
