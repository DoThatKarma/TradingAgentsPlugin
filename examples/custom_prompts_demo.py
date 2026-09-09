"""Offline demo: custom user instructions reach a REAL upstream agent node.

Run:  python examples/custom_prompts_demo.py

Uses a recording fake LLM - no network, no API keys - while the genuine
bull_researcher factory is resolved through the patched setup module.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tradingagents.graph.setup as ta_setup
from ta_plugins import (
    apply_plugins,
    get_registry,
    prompt_prefix_plugin,
    reset_patches,
)


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLM:
    def __init__(self) -> None:
        self.seen: list = []

    def invoke(self, messages, config=None, **kwargs):
        self.seen.append(messages)
        return _Response("The bull case rests on datacenter demand and pricing power.")


STATE = {
    "company_of_interest": "NVDA",
    "trade_date": "2024-05-10",
    "asset_type": "stock",
    "instrument_context": "",
    "market_report": "AI accelerator demand remains strong.",
    "sentiment_report": "Retail sentiment bullish.",
    "news_report": "No material news.",
    "fundamentals_report": "Gross margins ~78%.",
    "investment_debate_state": {
        "history": "",
        "bull_history": "",
        "bear_history": "",
        "current_response": "",
        "count": 0,
    },
}


def main() -> None:
    get_registry().clear()
    reset_patches()
    get_registry().register(
        prompt_prefix_plugin(
            "Focus on NVDA datacenter demand and gross margins.",
            targets={"create_bull_researcher"},
        )
    )
    apply_plugins()

    llm = FakeLLM()
    node = ta_setup.create_bull_researcher(llm)  # REAL upstream factory
    node(STATE)

    prompt_text = "\n".join(
        str(m.content) for m in llm.seen[0] if hasattr(m, "content")
    )
    print("--- instruction block reached the model prompt? ---")
    print("USER-PROVIDED INSTRUCTIONS marker:", "USER-PROVIDED INSTRUCTIONS" in prompt_text)
    print("user text present:", "datacenter demand" in prompt_text)
    print("upstream bull prompt intact:", "Bull Analyst advocating" in prompt_text)


if __name__ == "__main__":
    main()
