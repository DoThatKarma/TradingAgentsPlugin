import pytest

import tradingagents.graph.propagation as prop_mod
import tradingagents.graph.setup as ta_setup

from ta_plugins import Plugin, apply_plugins, get_registry, reset_patches


def setup_function(function):
    get_registry().clear()
    reset_patches()


def teardown_function(function):
    get_registry().clear()
    reset_patches()


def test_factory_wrapper_intercepts_module_namespace():
    def wrapper(original):
        def factory(*args, **kwargs):
            return "wrapped"

        return factory

    get_registry().register(
        Plugin(name="wrap-test", factory_wrappers={"create_market_analyst": wrapper})
    )
    apply_plugins()
    assert ta_setup.create_market_analyst(object()) == "wrapped"


def test_wrapper_only_touches_target_factories():
    orig_trader = ta_setup.create_trader
    orig_pm = ta_setup.create_portfolio_manager

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
    assert ta_setup.create_trader is orig_trader
    assert ta_setup.create_portfolio_manager is orig_pm


def test_reset_patches_restores_originals():
    orig = ta_setup.create_market_analyst
    get_registry().register(
        Plugin(
            name="wrap-test",
            factory_wrappers={
                "create_market_analyst": lambda o: (lambda *a, **k: "wrapped")
            },
        )
    )
    apply_plugins()
    assert ta_setup.create_market_analyst is not orig
    reset_patches()
    assert ta_setup.create_market_analyst is orig


def test_unknown_factory_rejected():
    get_registry().register(
        Plugin(name="bad", factory_wrappers={"create_nonexistent": lambda o: o})
    )
    with pytest.raises(KeyError):
        apply_plugins()


def test_state_injector_reaches_initial_state():
    def inject(state):
        state = dict(state)
        state["past_context"] = "USER INSTRUCTIONS"
        return state

    get_registry().register(Plugin(name="inject-test", state_injectors=[inject]))
    apply_plugins()

    cls = prop_mod.Propagator
    real_orig = cls._ta_plugins_orig_create_initial_state
    cls._ta_plugins_orig_create_initial_state = (
        lambda self, *args, **kwargs: {"company_of_interest": "NVDA"}
    )
    try:
        prop = cls.__new__(cls)
        out = prop.create_initial_state("NVDA", "2024-05-10")
        assert out["company_of_interest"] == "NVDA"
        assert out["past_context"] == "USER INSTRUCTIONS"
    finally:
        cls._ta_plugins_orig_create_initial_state = real_orig


def test_builtin_custom_instructions_plugin():
    from ta_plugins.builtin.custom_instructions import custom_instructions_plugin

    get_registry().register(custom_instructions_plugin("Focus on AI datacenter demand."))
    apply_plugins()

    cls = prop_mod.Propagator
    real_orig = cls._ta_plugins_orig_create_initial_state
    cls._ta_plugins_orig_create_initial_state = lambda self, *a, **k: {}
    try:
        prop = cls.__new__(cls)
        out = prop.create_initial_state("NVDA", "2024-05-10")
        assert "Focus on AI datacenter demand." in out["past_context"]
    finally:
        cls._ta_plugins_orig_create_initial_state = real_orig
