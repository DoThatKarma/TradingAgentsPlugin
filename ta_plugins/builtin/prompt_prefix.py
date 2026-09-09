"""Built-in plugin: prepend user instructions to ANY selected agent.

Mechanism (zero upstream edits): wraps the LLM object that is passed into
the targeted agent factories, so a labeled instruction block is prepended
to every message list at invoke time. This reaches all agents, supports
per-agent targeting, and keeps persisted state (reports, debate history)
clean.

Limitations (documented honestly):
- only ``invoke``-style calls are prepended; bare ``stream`` on the LLM is
  forwarded unwrapped (upstream nodes use invoke through LangGraph);
- structured-output calls invoked with dict payloads pass through unchanged
  (message-list inputs are still prepended).
"""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda

from ..patching import FACTORY_NAMES
from ..registry import Plugin
from .labels import (
    DEFAULT_MAX_CHARS,
    instruction_block,
    validate_instructions,
)


def _as_message_list(messages: object, block: str) -> list:
    prefix = SystemMessage(content=block)
    if isinstance(messages, str):
        return [prefix, HumanMessage(content=messages)]
    if isinstance(messages, (list, tuple)):
        return [prefix, *messages]
    return [prefix, messages]


class _PrefixRunnable:
    """Wraps a bound/structured runnable; prepends the block on invoke."""

    def __init__(self, inner: Callable, block: str) -> None:
        self._inner = inner
        self._block = block

    def invoke(self, first: object, *args: object, **kwargs: object) -> object:
        if isinstance(first, (str, list, tuple)):
            first = _as_message_list(first, self._block)
        return self._inner.invoke(first, *args, **kwargs)

    def __or__(self, other: object) -> object:
        return RunnableLambda(lambda x: other.invoke(self.invoke(x)))

    def __ror__(self, other: object) -> object:
        return RunnableLambda(lambda x: self.invoke(other.invoke(x)))

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


class _PrefixLLM:
    """Transparent proxy around an LLM; prepends the block on invoke."""

    def __init__(self, inner: object, block: str) -> None:
        self._inner = inner
        self._block = block

    def invoke(self, first: object, *args: object, **kwargs: object) -> object:
        return self._inner.invoke(_as_message_list(first, self._block), *args, **kwargs)

    def bind_tools(self, tools: object, **kwargs: object) -> object:
        return _PrefixRunnable(self._inner.bind_tools(tools, **kwargs), self._block)

    def with_structured_output(self, schema: object, **kwargs: object) -> object:
        return _PrefixRunnable(
            self._inner.with_structured_output(schema, **kwargs), self._block
        )

    def __or__(self, other: object) -> object:
        return RunnableLambda(lambda x: other.invoke(self.invoke(x)))

    def __ror__(self, other: object) -> object:
        return RunnableLambda(lambda x: self.invoke(other.invoke(x)))

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


def prompt_prefix_plugin(
    instructions: str,
    targets: set[str] | list[str] | tuple[str, ...],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> Plugin:
    """Build a plugin that prepends *instructions* to the given agents.

    ``targets`` are factory names from :data:`ta_plugins.FACTORY_NAMES`,
    e.g. {"create_bull_researcher", "create_market_analyst"}.
    """

    unknown = sorted(set(targets) - set(FACTORY_NAMES))
    if unknown:
        raise ValueError(f"unknown target factories: {unknown}")
    if not targets:
        raise ValueError("targets must contain at least one factory name")
    text = validate_instructions(instructions)
    block = instruction_block(text, max_chars)

    def make_wrapper(orig: Callable) -> Callable:
        def factory(llm: object, *args: object, **kwargs: object) -> object:
            return orig(_PrefixLLM(llm, block), *args, **kwargs)

        return factory

    return Plugin(
        name="builtin.prompt_prefix",
        version="0.1.0",
        description=(
            "Prepends labeled, length-capped user instructions to the LLM of "
            "the targeted agents."
        ),
        factory_wrappers=dict.fromkeys(targets, make_wrapper),
    )
