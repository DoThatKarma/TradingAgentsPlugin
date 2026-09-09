"""ta_plugins - a lightweight plugin system for TradingAgents.

Public API:
    Plugin                     -- dataclass describing a plugin
    register(plugin)           -- register into the global registry
    get_registry()             -- access the global registry
    apply_plugins()            -- apply all registered plugins to the
                                  tradingagents graph layer (call BEFORE
                                  constructing TradingAgentsGraph)
    reset_patches()            -- restore pristine upstream state
    plugin_scope(plugins)      -- context manager for run-scoped application
    FACTORY_NAMES              -- factories plugins may wrap
    custom_instructions_plugin -- builtin: Portfolio-Manager-only injection
    prompt_prefix_plugin       -- builtin: per-agent instructions for ALL agents

Zero third-party dependencies beyond tradingagents itself. Importing this
package has no side effects: nothing is registered or patched until you
explicitly call :func:`register` / :func:`apply_plugins`.
"""

from .builtin.custom_instructions import custom_instructions_plugin
from .builtin.labels import DEFAULT_MAX_CHARS
from .builtin.prompt_prefix import prompt_prefix_plugin
from .patching import FACTORY_NAMES, apply_plugins, plugin_scope, reset_patches
from .registry import Plugin, PluginRegistry, get_registry, register

__all__ = [
    "DEFAULT_MAX_CHARS",
    "FACTORY_NAMES",
    "Plugin",
    "PluginRegistry",
    "apply_plugins",
    "custom_instructions_plugin",
    "get_registry",
    "plugin_scope",
    "prompt_prefix_plugin",
    "register",
    "reset_patches",
]

__version__ = "0.1.0"
