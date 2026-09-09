"""Runtime patching layer.

Applies registered plugins to the tradingagents graph layer WITHOUT editing
any upstream file:

1. Agent factory wrapping: tradingagents.graph.setup resolves its 12 agent
   factories from module globals at call time, so replacing those globals
   before TradingAgentsGraph is constructed redirects every factory call.
2. State injection: Propagator.create_initial_state is wrapped exactly once;
   every registered state injector runs on the initial-state dict.

Important: apply_plugins() must be called BEFORE constructing
TradingAgentsGraph (the graph bakes factories in at construction time).
"""

from __future__ import annotations

from typing import Callable, Dict, List

import tradingagents.graph.propagation as _propagation
import tradingagents.graph.setup as _setup

from .registry import PluginRegistry, get_registry

_PATCHED_FLAG = "_ta_plugins_applied"
_ORIGINALS_ATTR = "_ta_plugins_original_factory_map"
_ORIG_INIT_STATE = "_ta_plugins_orig_create_initial_state"

_FACTORY_NAMES = (
    "create_market_analyst",
    "create_sentiment_analyst",
    "create_news_analyst",
    "create_fundamentals_analyst",
    "create_bull_researcher",
    "create_bear_researcher",
    "create_research_manager",
    "create_trader",
    "create_aggressive_debator",
    "create_conservative_debator",
    "create_neutral_debator",
    "create_portfolio_manager",
    "create_msg_delete",
)

_active_state_injectors: List[Callable[[dict], dict]] = []
_propagator_wrapped = False


def apply_plugins(registry: PluginRegistry | None = None) -> None:
    """Apply all registered plugins to the tradingagents graph layer.

    Safe to call multiple times: later calls refresh the active plugin set
    starting from pristine upstream factories (no double wrapping).
    """
    global _propagator_wrapped
    reg = registry or get_registry()

    if not getattr(_setup, _PATCHED_FLAG, False):
        setattr(
            _setup,
            _ORIGINALS_ATTR,
            {
                name: getattr(_setup, name)
                for name in _FACTORY_NAMES
                if hasattr(_setup, name)
            },
        )
        setattr(_setup, _PATCHED_FLAG, True)

    originals: Dict[str, Callable] = getattr(_setup, _ORIGINALS_ATTR)

    # Reset to pristine first, then layer wrappers in registration order.
    for name, orig in originals.items():
        setattr(_setup, name, orig)
    for plugin in reg.all():
        for fname, wrapper in plugin.factory_wrappers.items():
            if fname not in originals:
                raise KeyError(
                    f"plugin {plugin.name!r} wraps unknown factory {fname!r}"
                )
            current = getattr(_setup, fname)
            setattr(_setup, fname, wrapper(current))

    injectors: List[Callable[[dict], dict]] = []
    for plugin in reg.all():
        injectors.extend(plugin.state_injectors)
    _active_state_injectors[:] = injectors

    if not _propagator_wrapped and injectors:
        cls = _propagation.Propagator
        setattr(cls, _ORIG_INIT_STATE, cls.create_initial_state)

        def _patched_create_initial_state(self, *args, **kwargs):
            state = getattr(type(self), _ORIG_INIT_STATE)(self, *args, **kwargs)
            for inj in list(_active_state_injectors):
                result = inj(state)
                if result is not None:
                    state = result
            return state

        cls.create_initial_state = _patched_create_initial_state
        _propagator_wrapped = True


def reset_patches() -> None:
    """Restore pristine upstream module state (used by tests)."""
    global _propagator_wrapped
    if getattr(_setup, _PATCHED_FLAG, False):
        for name, orig in getattr(_setup, _ORIGINALS_ATTR).items():
            setattr(_setup, name, orig)
        setattr(_setup, _PATCHED_FLAG, False)
    cls = _propagation.Propagator
    orig = getattr(cls, _ORIG_INIT_STATE, None)
    if orig is not None:
        cls.create_initial_state = orig
        delattr(cls, _ORIG_INIT_STATE)
    _propagator_wrapped = False
    _active_state_injectors.clear()
