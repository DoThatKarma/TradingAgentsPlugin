"""Plugin model and registry."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

FactoryWrapper = Callable[[Callable], Callable]
StateInjector = Callable[[dict], dict]

_NAME_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,63}")


@dataclass
class Plugin:
    """A TradingAgents plugin.

    factory_wrappers:
        Maps a factory name from :data:`ta_plugins.FACTORY_NAMES` (e.g.
        "create_market_analyst") to a wrapper. The wrapper receives the
        currently installed factory (the upstream original for the first
        wrapper) and must return a factory with the same signature.
        Multiple plugins wrapping the same factory are chained in
        registration order: the last registered plugin ends up outermost.

    state_injectors:
        Called with the initial-state dict before a run starts; may mutate
        it in place (return None) or return a replacement dict. Injector
        exceptions propagate and abort the run by design (fail-fast).
    """

    name: str
    version: str = "0.0.0"
    description: str = ""
    factory_wrappers: dict[str, FactoryWrapper] = field(default_factory=dict)
    state_injectors: list[StateInjector] = field(default_factory=list)


class PluginRegistry:
    """Explicit-registration registry. No auto-discovery by design."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> Plugin:
        if not isinstance(plugin, Plugin):
            raise TypeError("register() expects a Plugin instance")
        if not _NAME_PATTERN.fullmatch(plugin.name):
            raise ValueError(
                f"invalid plugin name {plugin.name!r}: must match {_NAME_PATTERN.pattern!r}"
            )
        if plugin.name in self._plugins:
            raise ValueError(f"plugin already registered: {plugin.name!r}")
        self._plugins[plugin.name] = plugin
        return plugin

    def get(self, name: str) -> Plugin | None:
        return self._plugins.get(name)

    def all(self) -> list[Plugin]:
        return list(self._plugins.values())

    def clear(self) -> None:
        self._plugins.clear()


_global_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    """Return the process-global registry."""
    return _global_registry


def register(plugin: Plugin) -> Plugin:
    """Register *plugin* in the global registry and return it."""
    return _global_registry.register(plugin)
