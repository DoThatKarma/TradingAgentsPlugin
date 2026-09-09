import pytest
from langchain_core.messages import HumanMessage, SystemMessage

import tradingagents.graph.setup as ta_setup
from ta_plugins import (
    apply_plugins,
    get_registry,
    prompt_prefix_plugin,
    reset_patches,
)
from ta_plugins.builtin.custom_instructions import custom_instructions_plugin
from ta_plugins.builtin.labels import (
    UNTRUSTED_FOOTER,
    UNTRUSTED_HEADER,
    instruction_block,
    validate_instructions,
)


def setup_function(function):
    get_registry().clear()
    reset_patches()


def teardown_function(function):
    get_registry().clear()
    reset_patches()


class DummyLLM:
    def __init__(self):
        self.name = "dummy"

    def invoke(self, messages, *args, **kwargs):
        return ("inner", list(messages))

    def bind_tools(self, tools, **kwargs):
        return DummyBound()

    def with_structured_output(self, schema, **kwargs):
        return DummyBound()


class DummyBound:
    def invoke(self, messages, *args, **kwargs):
        return ("bound", list(messages))


def test_labels_header_footer_and_truncation():
    block = instruction_block("abc", 4000)
    assert block.startswith(UNTRUSTED_HEADER)
    assert block.endswith(UNTRUSTED_FOOTER)
    long_block = instruction_block("x" * 5000, 4000)
    assert "truncated by ta_plugins" in long_block


def test_validate_instructions_type_and_empty():
    with pytest.raises(TypeError):
        validate_instructions(b"bytes")
    with pytest.raises(ValueError):
        validate_instructions("   ")


def test_prompt_prefix_prepends_to_invoke_and_bind_tools():
    from ta_plugins.builtin.prompt_prefix import _PrefixLLM

    block = instruction_block("Focus on AI datacenter demand.", 4000)
    llm = _PrefixLLM(DummyLLM(), block)
    assert llm.name == "dummy"  # attribute forwarding

    _tag, msgs = llm.invoke([HumanMessage(content="hi")])
    assert isinstance(msgs[0], SystemMessage)
    assert UNTRUSTED_HEADER in msgs[0].content
    assert "Focus on AI datacenter demand." in msgs[0].content
    assert msgs[1].content == "hi"

    _tag2, bound_msgs = llm.bind_tools([]).invoke([HumanMessage(content="yo")])
    assert UNTRUSTED_HEADER in bound_msgs[0].content


def test_prompt_prefix_wraps_llm_passed_into_real_factory():
    class ProbeLLM(DummyLLM):
        pass

    get_registry().register(
        prompt_prefix_plugin("be extra careful", targets={"create_market_analyst"})
    )
    apply_plugins()
    # The real upstream factory must run fine with the wrapped LLM (it just
    # closes over it); this proves the wrapper threads the LLM through.
    node = ta_setup.create_market_analyst(ProbeLLM())
    assert callable(node)


def test_prompt_prefix_only_targets_selected_factories():
    orig_trader = ta_setup.create_trader
    get_registry().register(
        prompt_prefix_plugin("be careful", targets={"create_market_analyst"})
    )
    apply_plugins()
    assert ta_setup.create_market_analyst is not None
    assert ta_setup.create_trader is orig_trader


def test_prompt_prefix_unknown_target_rejected():
    with pytest.raises(ValueError):
        prompt_prefix_plugin("x", targets={"create_nope"})


def test_prompt_prefix_empty_targets_rejected():
    with pytest.raises(ValueError):
        prompt_prefix_plugin("x", targets=set())


def test_custom_instructions_injects_labeled_block_into_past_context():
    import tradingagents.default_config as dc
    import tradingagents.graph.propagation as prop_mod

    get_registry().register(custom_instructions_plugin("Prioritize cash flow."))
    apply_plugins()
    prop = prop_mod.Propagator.__new__(prop_mod.Propagator)
    prop.config = dc.DEFAULT_CONFIG.copy()
    state = prop.create_initial_state("NVDA", "2024-05-10")
    assert UNTRUSTED_HEADER in state["past_context"]
    assert "Prioritize cash flow." in state["past_context"]


def test_custom_instructions_rejects_non_string():
    with pytest.raises(TypeError):
        custom_instructions_plugin(123)


def test_prompt_prefix_composes_in_prompt_llm_chains():
    from langchain_core.prompts import ChatPromptTemplate

    from ta_plugins.builtin.prompt_prefix import _PrefixLLM

    block = instruction_block("Be precise.", 4000)
    prompt = ChatPromptTemplate.from_messages([("human", "{question}")])

    seq = prompt | _PrefixLLM(DummyLLM(), block)
    _tag, msgs = seq.invoke({"question": "hi"})
    assert isinstance(msgs[0], SystemMessage)
    assert UNTRUSTED_HEADER in msgs[0].content
    assert msgs[-1].content == "hi"

    seq2 = prompt | _PrefixLLM(DummyLLM(), block).bind_tools([])
    _tag2, msgs2 = seq2.invoke({"question": "yo"})
    assert UNTRUSTED_HEADER in msgs2[0].content
