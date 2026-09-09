"""Plugin model and registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List

FactoryWrapper = Callable[[Callable], Callable]
StateInjector = Callable[[dict], dict]


@dataclass
class Plugin:
    """A TradingAgents plugin.

    factory_wrappers:
        Maps a factory name used in tradingagents.graph.setup (e.g.
        "create_market_analyst") to a wrapper. The wrapper receives the
        factory currently installed (the upstream original for the first
        wrapper) and must return a factory with the same signature.
        Multiple plugins wrapping the same factory are chained in
        registration order.

    state_injectors:
        Called with the initial-state dict before a run starts; may mutate
        it in place or return a replacement dict.
    """

    name: str
    version: str = "0.0.0"
    factory_wrappers: Dict[str, FactoryWrapper] = field(default_factory=dict)
    state_injectors: List[StateInjector] = field(default_factory=list)


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: Dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        if not isinstance(plugin, Plugin):
            raise TypeError("register() expects a Plugin instance")
        if not plugin.name:
            raise ValueError("plugin must have a non-empty name")
        if plugin.name in self._plugins:
            raise ValueError(f"plugin already registered: {plugin.name!r}")
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> Plugin | None:
        return self._plugins.get(name)

    def all(self) -> List[Plugin]:
        return list(self._plugins.values())

    def clear(self) -> None:
        self._plugins.clear()


_global_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    return _global_registry


def register(plugin: Plugin) -> Plugin:
    """Register *plugin* in the global registry and return it."""
    _global_registry.register(plugin)
    return plugin
