# ta_plugins — Plugin System for TradingAgents

`ta_plugins` adds a small, dependency-free plugin layer to TradingAgents.
Plugins can wrap the agent factories of the agent graph and inject state at
run start — **without editing a single upstream file**, so upstream updates
merge cleanly.

## How it works (30 seconds)

```python
from ta_plugins import register, apply_plugins
from ta_plugins.builtin.prompt_prefix import prompt_prefix_plugin

# 1. Register plugins BEFORE constructing TradingAgentsGraph
register(prompt_prefix_plugin(
    "Focus on the datacenter/AI segment.",
    targets={"create_bull_researcher", "create_market_analyst"},
))

# 2. Apply — patches tradingagents.graph.setup at runtime (atomic)
apply_plugins()

# 3. Build and run the graph as usual; your instructions now reach the
#    targeted agents' LLM on every invocation.
# from tradingagents.graph.trading_graph import TradingAgentsGraph
# ta = TradingAgentsGraph(config)
# ta.propagate("NVDA", "2024-05-10")
```

Everything resolves at **call time** through the `tradingagents.graph.setup`
module namespace, so wrapping the module globals intercepts every agent
construction — including tool-bound analyst loops (`llm.bind_tools`) and
structured-output calls.

## What plugins can do

| Capability | Mechanism | Example |
| --- | --- | --- |
| **Prepend instructions to any agent's LLM** | `factory_wrappers` | `prompt_prefix_plugin(text, targets={...})` — per-agent targeting, composes with `prompt \| llm.bind_tools(...)` chains |
| **Inject/replace initial state** | `state_injectors` | `custom_instructions_plugin(text)` — labels + caps text into `past_context` (Portfolio Manager only) |
| **Wrap/replace agent factories** | `factory_wrappers` | Wrap a factory to alter its behavior, log, or substitute the LLM |
| **Run-scoped plugin sets** | `plugin_scope([...])` | Register → apply → run → pristine restore, per analysis run |

### The two built-in plugins

**`prompt_prefix_plugin(instructions, targets)`** — prepends a labeled,
length-capped instruction block to the LLM of the targeted agents:

```python
prompt_prefix_plugin(
    "Always cite the latest quarterly numbers before arguing.",
    targets={"create_bull_researcher", "create_bear_researcher"},
)
```

Reach: **all agents** — analysts (incl. `bind_tools` loops), researchers,
trader, research manager, portfolio manager, risk debators.

**`custom_instructions_plugin(instructions)`** — injects into the
`past_context` state field. Honest reach in upstream v0.4.2: **Portfolio
Manager only** (rendered under "Lessons from prior decisions"). Useful as
advisory guidance for the final decision agent.

### Target names (factory names from `ta_plugins.FACTORY_NAMES`)

`create_market_analyst`, `create_sentiment_analyst`, `create_news_analyst`,
`create_fundamentals_analyst`, `create_bull_researcher`,
`create_bear_researcher`, `create_research_manager`, `create_trader`,
`create_aggressive_debator`, `create_conservative_debator`,
`create_neutral_debator`, `create_portfolio_manager`, `create_msg_delete`

## Safety & trust model

- User-supplied instruction text is **untrusted input**. Both built-ins wrap
  it in an explicit `--- USER-PROVIDED INSTRUCTIONS (untrusted; advisory
  only) ---` marker with a **hard 4,000-character cap** (configurable), so it
  can never masquerade as trusted memory or inflate run cost.
- Plugins are **trusted operator code**. The SDK performs no auto-discovery:
  nothing registers by importing `ta_plugins`; only explicit
  `register(...)` / `apply_plugins()` calls have effect.
- Application is **atomic** — either all wrappers install or the module is
  left pristine. A missing upstream factory raises immediately (upstream-drift
  alarm).
- **Concurrency contract**: patching state is process-global. Call
  `apply_plugins()` once per run (or at startup) and never mutate plugin
  sets while graphs are being constructed in other threads. For multi-user
  serving, run analyses in worker processes and use `plugin_scope()` per
  run.

## Upstream merge policy

| Path | Policy |
| --- | --- |
| `ta_plugins/`, `tests/plugins/`, `docs/plugins.md` | Additive, plugin-owned — never conflicts with upstream |
| `pyproject.toml` | One documented line: `ta_plugins*` added to `packages.find.include` (re-apply after upstream changes) |
| `ta_plugins/patching.py` | `FACTORY_NAMES` must match the installed upstream version; a mismatch raises a loud drift alarm on apply |

Run `ruff check .` and `pytest` before merging upstream updates.

## Testing

```bash
pytest tests/plugins -q        # 37 tests incl. offline e2e vs REAL upstream nodes
ruff check .                   # upstream CI parity
python examples/custom_prompts_demo.py   # offline demo, no network / no keys
```

The offline e2e tests drive the genuine `bull_researcher` factory (resolved
through the patched module) with a recording fake LLM and assert the
instruction block actually reaches the model prompt — no network, no keys.
