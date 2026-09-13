"""Built-in skill-pack plugin: demographics analysis via verified FRED series.

Teaches agents how to use ``get_macro_indicators`` with VERIFIED raw FRED
series IDs for demographics / aging-cohort analysis (65+ population share,
old-age dependency, care-demand proxies) — with honest caveats about what
FRED does *not* provide (e.g. national 75+/85+ population levels).

Mechanism: identical to :func:`ta_plugins.builtin.prompt_prefix
.prompt_prefix_plugin` (labeled, length-capped LLM prefix), rebuilt via
``dataclasses.replace`` so the plugin registers under its own name
(``fred_skill_pack``) without duplicating wrapper logic.

Honest reach: ``get_macro_indicators`` is bound ONLY to the news analyst in
upstream v0.4.2, so the default target is ``create_news_analyst``. Other
targets receive the pack text as context but cannot call the tool.

Every series ID below was verified to exist on fred.stlouisfed.org
(HTTP 200 + matching title) at packaging time. Never add guessed IDs —
verify at https://fred.stlouisfed.org/series/<ID> first.
"""

from __future__ import annotations

import dataclasses

from ..registry import Plugin
from .labels import DEFAULT_MAX_CHARS
from .prompt_prefix import prompt_prefix_plugin

#: Default reach: the only upstream agent with get_macro_indicators bound.
DEFAULT_TARGETS = ("create_news_analyst",)

#: Verified FRED series IDs -> plain-language meaning (see module docstring).
FRED_SERIES: dict[str, str] = {
    "SPPOP65UPTOZSUSA": (
        "US population ages 65+ as % of total (annual, World Bank/UN mirror)"
    ),
    "SPPOPDPNDOLUSA": (
        "US old-age dependency ratio: people 65+ per 100 working-age (15-64), annual"
    ),
    "LNU01375379": (
        "US labor force participation rate, 65 and over, with no disability "
        "(monthly) — active-aging signal; covers non-disabled only"
    ),
    "SPPOP65UPTOZSWLD": (
        "World population ages 65+ as % of total (annual, lagging) — global "
        "aging backdrop"
    ),
    "SPPOPDPNDOLWLD": (
        "World old-age dependency ratio (annual, lagging) — global aging backdrop"
    ),
    "CES6562300001": (
        "US all employees, nursing & residential care facilities (monthly, SA) "
        "— care-demand proxy"
    ),
    "CEU6562300001": (
        "US all employees, nursing & residential care facilities (monthly, NSA)"
    ),
    "CES6562310001": (
        "US all employees, skilled nursing care facilities (monthly, SA) — "
        "care-demand proxy"
    ),
    "CES6562160001": (
        "US all employees, home health care services (monthly, SA) — "
        "home-care demand proxy"
    ),
    "CCRCAALFFTE416233": (
        "US revenue, continuing-care retirement & assisted-living facilities "
        "for the elderly (annual, Census) — senior-living demand proxy"
    ),
}

PACK_TEXT = """You have access to the tool get_macro_indicators(indicator, curr_date, look_back_days). It accepts a friendly alias ('cpi', 'unemployment', ...) or a RAW FRED series ID, and returns the series title, units, frequency, latest value, change over the window, and a recent observation table.

API KEY: this tool needs FRED_API_KEY (free key: https://fred.stlouisfed.org/docs/api/api_key.html). If it is not configured, the FRED vendor is skipped and the tool returns no data — say so explicitly instead of inventing numbers.

VERIFIED FRED series IDs for demographics/aging analysis (verified on fred.stlouisfed.org; do NOT guess other IDs — if you need a series not listed here, say so):

US aging:
""" + "\n".join(
    f"- {sid} — {meaning}" for sid, meaning in FRED_SERIES.items()
) + """

KNOWN LIMITS (be honest about them): FRED has NO national '75 and over' or '85 and over' population-level series — approximate deep-aging demand with the 65+ share, the dependency ratio, and care-sector trends. The World Bank mirrors are annual and lag roughly a year. LNU01375379 covers people with no disability only. Employment/revenue series are care-demand proxies, not population counts.

HOW TO USE: translate demographics into demand/thesis context, labeled as MACRO CONTEXT, never as stock-specific facts. Prefer growth rates (year-over-year, percentage-point changes) over levels; cohort scaling (65+ share x total population from series POP) only as a rough magnitude check. When relevant, connect to affected sectors (senior housing, home health, long-term care, insurers, pharma) and state the causal chain as a hypothesis, not a fact about the company under analysis. Cite series ID, units, and window for every number you report."""


def fred_skill_pack_plugin(
    targets: set[str] | list[str] | tuple[str, ...] | None = None,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> Plugin:
    """Build the ``fred_skill_pack`` prompt-prefix plugin.

    ``targets`` defaults to ``create_news_analyst`` (the only agent with
    ``get_macro_indicators`` bound in upstream v0.4.2). Any valid
    :data:`ta_plugins.FACTORY_NAMES` subset is accepted; other agents get the
    pack text as advisory context but cannot call the tool.
    """

    base = prompt_prefix_plugin(
        PACK_TEXT,
        targets=DEFAULT_TARGETS if targets is None else targets,
        max_chars=max_chars,
    )
    return dataclasses.replace(
        base,
        name="fred_skill_pack",
        version="0.1.0",
        description=(
            "Skill pack: teaches agents to use get_macro_indicators with "
            "verified FRED series IDs for demographics/aging analysis "
            "(labeled, length-capped prompt prefix)."
        ),
    )
