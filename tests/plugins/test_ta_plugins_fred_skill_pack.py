"""Tests for the fred_skill_pack builtin plugin."""

import re

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

import tradingagents.graph.setup as ta_setup
from ta_plugins import (
    DEFAULT_MAX_CHARS,
    apply_plugins,
    fred_skill_pack_plugin,
    get_registry,
    reset_patches,
)
from ta_plugins.builtin.fred_skill_pack import FRED_SERIES, PACK_TEXT
from ta_plugins.builtin.labels import (
    UNTRUSTED_FOOTER,
    UNTRUSTED_HEADER,
    instruction_block,
)


def setup_function(function):
    get_registry().clear()
    reset_patches()


def teardown_function(function):
    get_registry().clear()
    reset_patches()


class DummyLLM:
    def invoke(self, messages, *args, **kwargs):
        return ("inner", list(messages))

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        return self


def _plugin_block(plugin):
    """Run the plugin's wrapper pipeline over a recording dummy LLM."""
    wrapper = next(iter(plugin.factory_wrappers.values()))
    probe = wrapper(lambda llm: llm)(DummyLLM())
    _tag, msgs = probe.invoke([HumanMessage(content="analyze demographics")])
    return msgs


def test_registry_finds_fred_skill_pack():
    plugin = fred_skill_pack_plugin()
    get_registry().register(plugin)
    found = get_registry().get("fred_skill_pack")
    assert found is plugin
    assert found.name == "fred_skill_pack"
    assert found.version
    assert found.description


def test_prefix_contains_at_least_five_verified_ids_and_api_key_note():
    plugin = fred_skill_pack_plugin()
    msgs = _plugin_block(plugin)
    block = msgs[0].content
    id_count = sum(1 for sid in FRED_SERIES if sid in block)
    assert id_count >= 5
    assert id_count == len(FRED_SERIES)  # dict and pack text stay in sync
    assert "FRED_API_KEY" in block
    assert "fred.stlouisfed.org/docs/api/api_key.html" in block


def test_all_series_ids_look_like_fred_ids():
    for sid in FRED_SERIES:
        assert re.fullmatch(r"[A-Z][A-Z0-9]{3,20}", sid), sid
        assert FRED_SERIES[sid].strip()  # every ID has a meaning


def test_labeling_present_on_prefix():
    plugin = fred_skill_pack_plugin()
    msgs = _plugin_block(plugin)
    assert isinstance(msgs[0], SystemMessage)
    assert UNTRUSTED_HEADER in msgs[0].content
    assert UNTRUSTED_FOOTER in msgs[0].content
    assert msgs[1].content == "analyze demographics"


def test_cap_respected_without_truncation():
    assert len(PACK_TEXT) <= DEFAULT_MAX_CHARS
    block = instruction_block(PACK_TEXT, DEFAULT_MAX_CHARS)
    assert "truncated by ta_plugins" not in block
    # An explicitly smaller cap still truncates gracefully.
    assert "truncated by ta_plugins" in instruction_block(PACK_TEXT, 500)


def test_honest_caveats_present():
    lowered = PACK_TEXT.lower()
    assert "75 and over" in lowered
    assert "85 and over" in lowered
    assert "macro context" in lowered
    assert "hypothesis" in lowered


def test_default_targets_only_news_analyst():
    plugin = fred_skill_pack_plugin()
    assert set(plugin.factory_wrappers) == {"create_news_analyst"}


def test_custom_targets_accepted():
    plugin = fred_skill_pack_plugin(
        targets={"create_news_analyst", "create_market_analyst"}
    )
    assert set(plugin.factory_wrappers) == {
        "create_news_analyst",
        "create_market_analyst",
    }


def test_unknown_target_rejected():
    with pytest.raises(ValueError):
        fred_skill_pack_plugin(targets={"create_nope"})


def test_empty_targets_rejected():
    with pytest.raises(ValueError):
        fred_skill_pack_plugin(targets=set())


def test_wraps_llm_passed_into_real_news_analyst_factory():
    class ProbeLLM(DummyLLM):
        pass

    get_registry().register(fred_skill_pack_plugin())
    apply_plugins()
    node = ta_setup.create_news_analyst(ProbeLLM())
    assert callable(node)


def test_only_targets_selected_factories():
    orig_trader = ta_setup.create_trader
    get_registry().register(fred_skill_pack_plugin())
    apply_plugins()
    assert ta_setup.create_news_analyst is not None
    assert ta_setup.create_trader is orig_trader
