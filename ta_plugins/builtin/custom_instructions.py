"""Example plugin: inject free-text user instructions into every run.

This is the reference implementation for the WebGUI custom-prompt feature.
The text lands in the ``past_context`` state field, which agent prompts
already consume, so no upstream file needs to change.
"""

from __future__ import annotations

from ..registry import Plugin


def custom_instructions_plugin(instructions: str) -> Plugin:
    """Build a plugin that injects *instructions* into the initial state."""

    text = instructions.strip()
    if not text:
        raise ValueError("instructions must be a non-empty string")

    def inject(state: dict) -> dict:
        state = dict(state)
        existing = (state.get("past_context") or "").strip()
        state["past_context"] = f"{existing}\n\n{text}" if existing else text
        return state

    return Plugin(
        name="custom_instructions",
        version="0.1.0",
        state_injectors=[inject],
    )
