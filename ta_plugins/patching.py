"""Runtime patching layer.

Applies registered plugins to the tradingagents graph layer WITHOUT editing
any upstream file:

1. Agent factory wrapping: tradingagents.graph.setup resolves its agent
   factories from module globals at call time, so replacing those globals
   before TradingAgentsGraph is constructed redirects every factory call.
2. State injection: Propagator.create_initial_state is wrapped once so
   registered injectors run on every fresh initial state.

Contract (important for servers):
- Call :func:`apply_plugins` BEFORE constructing TradingAgentsGraph; the
  graph bakes factories in at construction time.
- Patching state is process-global and NOT safe to mutate while graphs are
  being constructed concurrently. Apply once at startup (or between runs
  under :func:`plugin_scope`); run analyses in worker processes for
  isolation. A re-entrant lock guards apply/reset against races.
- Application is atomic: either all wrappers install or the module is left
  pristine. A missing expected factory raises (upstream-drift alarm).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager

import tradingagents.graph.propagation as _propagation
import tradingagents.graph.setup as _setup

from .registry import Plugin, PluginRegistry, get_registry

logger = logging.getLogger("ta_plugins")

_PATCHED_FLAG = "_ta_plugins_applied"
_ORIGINALS_ATTR = "_ta_plugins_original_factory_map"
_ORIG_INIT_STATE = "_ta_plugins_orig_create_initial_state"

FACTORY_NAMES: tuple[str, ...] = (
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

_apply_lock = threading.RLock()
_active_state_injectors: list[tuple[str, Callable[[dict], dict]]] = []
_propagator_wrapped = False


def _patched_create_initial_state(self, *args, **kwargs):
    state = getattr(type(self), _ORIG_INIT_STATE)(self, *args, **kwargs)
    for plugin_name, inj in list(_active_state_injectors):
        result = inj(state)
        if result is None:
            continue
        if not isinstance(result, dict):
            raise TypeError(
                f"state injector of plugin {plugin_name!r} must return a dict or None, "
                f"got {type(result).__name__}"
            )
        missing = {"company_of_interest", "trade_date"} - result.keys()
        if missing:
            logger.warning(
                "state injector of plugin %r returned a replacement dict missing keys %s",
                plugin_name,
                sorted(missing),
            )
        state = result
    return state


def _ensure_originals() -> dict[str, Callable]:
    if getattr(_setup, _PATCHED_FLAG, False):
        return getattr(_setup, _ORIGINALS_ATTR)
    missing = [name for name in FACTORY_NAMES if not hasattr(_setup, name)]
    if missing:
        raise ValueError(
            f"upstream drift: expected factories missing from tradingagents.graph.setup: "
            f"{missing}. The installed tradingagents version may be incompatible."
        )
    snapshot = {name: getattr(_setup, name) for name in FACTORY_NAMES}
    setattr(_setup, _ORIGINALS_ATTR, snapshot)
    setattr(_setup, _PATCHED_FLAG, True)
    return snapshot


def apply_plugins(registry: PluginRegistry | None = None) -> None:
    """Apply all registered plugins to the tradingagents graph layer.

    Safe to call multiple times: the module is first reset to pristine
    upstream factories, so each apply converges to exactly one wrapper
    layer per plugin (no double wrapping). Atomic: wrappers either all
    install or the module is left pristine.
    """
    global _propagator_wrapped
    reg = get_registry() if registry is None else registry
    with _apply_lock:
        originals = _ensure_originals()

        # Phase 1: reset to pristine, then build the complete wrapper map.
        for name, orig in originals.items():
            setattr(_setup, name, orig)

        new_map: dict[str, Callable] = {}
        for plugin in reg.all():
            for fname, wrapper in plugin.factory_wrappers.items():
                if fname not in originals:
                    raise ValueError(
                        f"plugin {plugin.name!r} wraps unknown factory {fname!r}"
                    )
                current = new_map.get(fname, originals[fname])
                new_map[fname] = wrapper(current)

        # Phase 2: commit everything at once.
        for fname, wrapped in new_map.items():
            setattr(_setup, fname, wrapped)

        injectors = [
            (plugin.name, inj) for plugin in reg.all() for inj in plugin.state_injectors
        ]
        _active_state_injectors[:] = injectors

        if injectors and not _propagator_wrapped:
            cls = _propagation.Propagator
            setattr(cls, _ORIG_INIT_STATE, cls.create_initial_state)
            cls.create_initial_state = _patched_create_initial_state
            _propagator_wrapped = True

        if reg.all():
            logger.info("ta_plugins applied: %s", [p.name for p in reg.all()])


def reset_patches() -> None:
    """Restore pristine upstream state (used between runs and by tests)."""
    global _propagator_wrapped
    with _apply_lock:
        if getattr(_setup, _PATCHED_FLAG, False):
            for name, orig in getattr(_setup, _ORIGINALS_ATTR).items():
                setattr(_setup, name, orig)
            delattr(_setup, _ORIGINALS_ATTR)
            setattr(_setup, _PATCHED_FLAG, False)
        cls = _propagation.Propagator
        orig = getattr(cls, _ORIG_INIT_STATE, None)
        if orig is not None:
            cls.create_initial_state = orig
            delattr(cls, _ORIG_INIT_STATE)
        _propagator_wrapped = False
        _active_state_injectors.clear()


@contextmanager
def plugin_scope(plugins: Iterable[Plugin]) -> Iterator[PluginRegistry]:
    """Run-scoped plugin application.

    Registers *plugins*, applies them, yields the registry, then restores
    pristine upstream state and clears the registry. Use this for per-run
    instruction sets; never mutate the global registry while runs overlap.
    """
    reg = get_registry()
    with _apply_lock:
        reg.clear()
        try:
            for plugin in plugins:
                reg.register(plugin)
            apply_plugins()
            yield reg
        finally:
            reset_patches()
            reg.clear()
