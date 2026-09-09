"""Offline end-to-end tests: plugins work against REAL upstream code.

No network and no API keys: the LLM is a recording fake chat model, while
the agent node under test is the genuine ``bull_researcher`` factory
resolved through the patched ``tradingagents.graph.setup`` module, and the
state test drives the real ``Propagator.create_initial_state``.
"""

import tradingagents.default_config as dc
import tradingagents.graph.propagation as prop_mod
import tradingagents.graph.setup as ta_setup
from ta_plugins import (
    apply_plugins,
    custom_instructions_plugin,
    get_registry,
    plugin_scope,
    prompt_prefix_plugin,
    reset_patches,
)
from ta_plugins.builtin.labels import UNTRUSTED_FOOTER, UNTRUSTED_HEADER


class _Response:
    """Minimal AIMessage stand-in: only ``.content`` is consumed upstream."""

    def __init__(self, content: str) -> None:
        self.content = content


class RecordingFake:
    """Plain fake chat model that records every prompt it is given.

    Deliberately not a pydantic BaseChatModel: the real agent node only
    needs ``invoke(messages) -> object-with-.content``, and a plain class
    keeps the test free of pydantic field validation.
    """

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.seen_prompts: list = []

    def invoke(self, messages, config=None, **kwargs):
        self.seen_prompts.append(messages)
        return _Response(self._responses.pop(0))

    def bind_tools(self, tools, **kwargs):  # pragma: no cover - not used here
        raise AssertionError("bull node does not bind tools")


def setup_function(function):
    get_registry().clear()
    reset_patches()


def teardown_function(function):
    get_registry().clear()
    reset_patches()


def _bull_state():
    return {
        "company_of_interest": "NVDA",
        "trade_date": "2024-05-10",
        "asset_type": "stock",
        "instrument_context": "",
        "market_report": "Market is strong.",
        "sentiment_report": "Sentiment positive.",
        "news_report": "News calm.",
        "fundamentals_report": "Fundamentals solid.",
        "investment_debate_state": {
            "history": "",
            "bull_history": "",
            "bear_history": "",
            "current_response": "",
            "count": 0,
        },
    }


def test_prompt_prefix_reaches_real_bull_node():
    instructions = "Emphasize NVDA datacenter demand."
    get_registry().register(
        prompt_prefix_plugin(instructions, targets={"create_bull_researcher"})
    )
    apply_plugins()

    llm = RecordingFake(responses=["The bull case stands."])
    node = ta_setup.create_bull_researcher(llm)  # real upstream factory, patched module

    result = node(_bull_state())
    ids = result["investment_debate_state"]
    assert ids["count"] == 1
    assert "Bull Analyst: The bull case stands." in ids["bull_history"]

    joined = "\n".join(
        str(m.content) for m in llm.seen_prompts[0] if hasattr(m, "content")
    )
    assert UNTRUSTED_HEADER in joined
    assert UNTRUSTED_FOOTER in joined
    assert instructions in joined
    assert "Bull Analyst advocating" in joined  # genuine upstream prompt intact


def test_custom_instructions_reach_real_propagator_state():
    with plugin_scope([custom_instructions_plugin("Advisory: weigh cash flow.")]):
        prop = prop_mod.Propagator.__new__(prop_mod.Propagator)
        prop.config = dc.DEFAULT_CONFIG.copy()
        state = prop.create_initial_state("NVDA", "2024-05-10")
        assert UNTRUSTED_HEADER in state["past_context"]
        assert "Advisory: weigh cash flow." in state["past_context"]
