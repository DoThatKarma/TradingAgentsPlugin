"""Built-in plugin: inject user instructions into the Portfolio Manager.

HONEST REACH (upstream v0.4.2): the ``past_context`` state field has exactly
one prompt consumer in the whole framework - the Portfolio Manager - where
it is rendered under "Lessons from prior decisions and outcomes". Text
injected here reaches ONLY that agent, alongside real memory-log lessons.

Because of that, the text is wrapped in an explicit untrusted-instructions
marker and hard-capped in length so it can never masquerade as trusted
memory or inflate run cost.

For instructions that must reach ALL agents (analysts, researchers, trader,
debators), use :func:`ta_plugins.builtin.prompt_prefix.prompt_prefix_plugin`
instead - that is the mechanism the WebGUI custom-prompt feature builds on.
"""

from __future__ import annotations

from ..registry import Plugin
from .labels import instruction_block, validate_instructions


def custom_instructions_plugin(
    instructions: str, *, max_chars: int = 4000
) -> Plugin:
    """Build a plugin injecting *instructions* into the Portfolio Manager."""

    text = validate_instructions(instructions)
    block = instruction_block(text, max_chars)

    def inject(state: dict) -> None:
        existing = (state.get("past_context") or "").strip()
        state["past_context"] = f"{existing}\n\n{block}" if existing else block

    return Plugin(
        name="builtin.custom_instructions",
        version="0.1.0",
        description=(
            "Injects user text into the Portfolio Manager only, wrapped in an "
            "untrusted-instructions marker with a hard length cap."
        ),
        state_injectors=[inject],
    )
