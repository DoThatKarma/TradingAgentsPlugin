"""Built-in plugin: prepend user instructions to ANY selected agent.

Mechanism (zero upstream edits): wraps the LLM object passed into the
targeted agent factories, so a labeled instruction block is prepended to
every LLM invocation - including tool-bound analyst loops (``llm.bind_tools``)
and structured-output calls (``llm.with_structured_output``).

The proxies subclass ``langchain_core.runnables.Runnable`` so they compose
natively in upstream ``prompt | llm.bind_tools(...)`` chains, and they convert
``PromptValue`` inputs (produced by ``prompt | llm`` sequences) via
``to_messages()`` before prefixing. Attribute access forwards transparently
to the inner LLM; native non-invoke paths reached only through that
forwarding (e.g. a manually grabbed ``inner.stream``) bypass the prefix by
design - upstream agent nodes invoke through the wrapped runnables.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompt_values import PromptValue
from langchain_core.runnables import Runnable

from ..patching import FACTORY_NAMES
from ..registry import Plugin
from .labels import DEFAULT_MAX_CHARS, instruction_block, validate_instructions


def _prepare_input(first: object, block: str) -> object:
    """Normalize chain inputs so the instruction block is always prepended."""
    if isinstance(first, PromptValue):
        first = first.to_messages()
    if isinstance(first, (str, list, tuple)):
        prefix = SystemMessage(content=block)
        if isinstance(first, str):
            return [prefix, HumanMessage(content=first)]
        return [prefix, *first]
    return first


class _PrefixRunnable(Runnable):
    """Wraps a bound/structured runnable; prepends the block on invoke."""

    def __init__(self, inner: Runnable, block: str) -> None:
        self._inner = inner
        self._block = block

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:  # noqa: A002
        return self._inner.invoke(_prepare_input(input, self._block), config, **kwargs)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._inner, name)


class _PrefixLLM(Runnable):
    """Transparent LLM proxy; prepends the block on invoke."""

    def __init__(self, inner: Any, block: str) -> None:
        self._inner = inner
        self._block = block

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:  # noqa: A002
        return self._inner.invoke(_prepare_input(input, self._block), config, **kwargs)

    def bind_tools(self, tools: Any, **kwargs: Any) -> Runnable:
        return _PrefixRunnable(self._inner.bind_tools(tools, **kwargs), self._block)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Runnable:
        return _PrefixRunnable(self._inner.with_structured_output(schema, **kwargs), self._block)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._inner, name)


def prompt_prefix_plugin(
    instructions: str,
    targets: set[str] | list[str] | tuple[str, ...],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> Plugin:
    """Build a plugin that prepends *instructions* to the given agents.

    ``targets`` are factory names from :data:`ta_plugins.FACTORY_NAMES`,
    e.g. ``{"create_bull_researcher", "create_market_analyst"}``.
    """

    unknown = sorted(set(targets) - set(FACTORY_NAMES))
    if unknown:
        raise ValueError(f"unknown target factories: {unknown}")
    if not targets:
        raise ValueError("targets must contain at least one factory name")
    text = validate_instructions(instructions)
    block = instruction_block(text, max_chars)

    def make_wrapper(orig: Callable) -> Callable:
        def factory(llm: Any, *args: Any, **kwargs: Any) -> Any:
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
