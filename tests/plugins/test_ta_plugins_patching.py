import subprocess
import sys
from pathlib import Path

import pytest

import tradingagents.default_config as dc
import tradingagents.graph.propagation as prop_mod
import tradingagents.graph.setup as ta_setup
from ta_plugins import (
    FACTORY_NAMES,
    Plugin,
    apply_plugins,
    get_registry,
    plugin_scope,
    reset_patches,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ORIG_CIS = prop_mod.Propagator.create_initial_state
ORIG_FACTORIES = {name: getattr(ta_setup, name) for name in FACTORY_NAMES}


def setup_function(function):
    get_registry().clear()
    reset_patches()


def teardown_function(function):
    get_registry().clear()
    reset_patches()


def _bare_propagator():
    prop = prop_mod.Propagator.__new__(prop_mod.Propagator)
    prop.config = dc.DEFAULT_CONFIG.copy()
    return prop


def test_factory_wrapper_intercepts_module_namespace():
    get_registry().register(
        Plugin(
            name="wrap-test",
            factory_wrappers={
                "create_market_analyst": lambda o: (lambda *a, **k: "wrapped")
            },
        )
    )
    apply_plugins()
    assert ta_setup.create_market_analyst(object()) == "wrapped"


def test_wrapper_only_touches_target_factories():
    get_registry().register(
        Plugin(
            name="wrap-test",
            factory_wrappers={
                "create_market_analyst": lambda o: (lambda *a, **k: "wrapped")
            },
        )
    )
    apply_plugins()
    assert ta_setup.create_market_analyst(object()) == "wrapped"
    assert ta_setup.create_trader is ORIG_FACTORIES["create_trader"]
    assert (
        ta_setup.create_portfolio_manager
        is ORIG_FACTORIES["create_portfolio_manager"]
    )


def test_reset_patches_restores_originals():
    get_registry().register(
        Plugin(
            name="wrap-test",
            factory_wrappers={
                "create_market_analyst": lambda o: (lambda *a, **k: "wrapped")
            },
        )
    )
    apply_plugins()
    assert ta_setup.create_market_analyst is not ORIG_FACTORIES["create_market_analyst"]
    reset_patches()
    assert ta_setup.create_market_analyst is ORIG_FACTORIES["create_market_analyst"]


def test_unknown_factory_raises_valueerror():
    get_registry().register(
        Plugin(name="bad", factory_wrappers={"create_nonexistent": lambda o: o})
    )
    with pytest.raises(ValueError):
        apply_plugins()


def test_failed_apply_leaves_module_pristine():
    get_registry().register(  # valid plugin first
        Plugin(
            name="good",
            factory_wrappers={
                "create_market_analyst": lambda o: (lambda *a, **k: "wrapped")
            },
        )
    )
    get_registry().register(
        Plugin(name="bad", factory_wrappers={"create_nonexistent": lambda o: o})
    )
    with pytest.raises(ValueError):
        apply_plugins()
    assert ta_setup.create_market_analyst is ORIG_FACTORIES["create_market_analyst"]
    assert prop_mod.Propagator.create_initial_state is ORIG_CIS


def test_no_double_wrap_on_repeated_apply_with_changed_registry():
    # Tag/inner factories record composition without executing real
    # upstream factory bodies.
    get_registry().register(
        Plugin(
            name="p1",
            factory_wrappers={
                "create_market_analyst": lambda o: (
                    lambda *a, **k: ("P1", o)
                )
            },
        )
    )
    apply_plugins()
    get_registry().register(
        Plugin(
            name="p2",
            factory_wrappers={
                "create_market_analyst": lambda o: (
                    lambda *a, **k: ("P2", o)
                )
            },
        )
    )
    apply_plugins()
    tag, inner = ta_setup.create_market_analyst()
    assert tag == "P2"
    tag2, inner2 = inner()
    assert tag2 == "P1"
    assert inner2 is ORIG_FACTORIES["create_market_analyst"]


def test_two_plugins_chain_in_registration_order():
    get_registry().register(
        Plugin(
            name="first",
            factory_wrappers={"create_trader": lambda o: lambda *a, **k: ("A", o)},
        )
    )
    get_registry().register(
        Plugin(
            name="second",
            factory_wrappers={"create_trader": lambda o: lambda *a, **k: ("B", o)},
        )
    )
    apply_plugins()
    # last registered plugin ends up outermost: B(A(orig))
    tag, inner = ta_setup.create_trader()
    assert tag == "B"
    tag2, inner2 = inner()
    assert tag2 == "A"
    assert inner2 is ORIG_FACTORIES["create_trader"]


def test_apply_with_empty_registry_is_noop():
    apply_plugins()
    for name, orig in ORIG_FACTORIES.items():
        assert getattr(ta_setup, name) is orig
    assert prop_mod.Propagator.create_initial_state is ORIG_CIS


def test_state_injector_reaches_initial_state_via_public_path():
    def inject(state):
        state = dict(state)
        state["past_context"] = "USER INSTRUCTIONS"
        return state

    get_registry().register(Plugin(name="inject-test", state_injectors=[inject]))
    apply_plugins()
    state = _bare_propagator().create_initial_state("NVDA", "2024-05-10")
    assert state["company_of_interest"] == "NVDA"
    assert state["past_context"] == "USER INSTRUCTIONS"


def test_injector_replacement_dict_is_applied():
    get_registry().register(
        Plugin(
            name="replace-test",
            state_injectors=[
                lambda s: {"company_of_interest": "TSLA", "trade_date": "2024-01-02"}
            ],
        )
    )
    apply_plugins()
    state = _bare_propagator().create_initial_state("NVDA", "2024-05-10")
    assert state["company_of_interest"] == "TSLA"


def test_injector_returning_non_dict_raises_typeerror():
    get_registry().register(
        Plugin(name="bad-inject", state_injectors=[lambda s: "not-a-dict"])
    )
    apply_plugins()
    with pytest.raises(TypeError):
        _bare_propagator().create_initial_state("NVDA", "2024-05-10")


def test_plugin_scope_installs_and_cleans_up():
    with plugin_scope(
        [
            Plugin(
                name="scoped",
                factory_wrappers={
                    "create_market_analyst": lambda o: (
                        lambda *a, **k: "scoped-wrapped"
                    )
                },
            )
        ]
    ) as reg:
        assert reg.get("scoped") is not None
        assert ta_setup.create_market_analyst(object()) == "scoped-wrapped"
    assert ta_setup.create_market_analyst is ORIG_FACTORIES["create_market_analyst"]
    assert get_registry().all() == []
    assert prop_mod.Propagator.create_initial_state is ORIG_CIS


def test_factory_names_match_upstream_setup_module():
    for name in FACTORY_NAMES:
        assert hasattr(ta_setup, name), f"upstream drift: {name} missing"


def test_import_has_no_side_effects():
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(REPO_ROOT)}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import ta_plugins; assert ta_plugins.get_registry().all() == []",
        ],
        capture_output=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr.decode()
