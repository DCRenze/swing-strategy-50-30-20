# Swing Trade Strategy Research

A research-and-validation pipeline to discover a **long-only swing trading strategy** (US stocks, 2–15 trading day holds) robust enough to hand to an automated trading agent via Alpaca paper trading.

## Approach

1. **Research** (`research/`) — parallel web research across Reddit, trading forums, quant blogs, and academic literature. Every candidate strategy is captured as a structured "strategy card" in `research/candidates/`, ranked in `research/CATALOG.md`.
2. **Backtest** (`backtest/`, `data/`) — top candidates are formalized into exact rules on daily OHLCV bars and run through a shared vectorized backtest engine with realistic execution assumptions (next-day-open entries, slippage).
3. **Validate** (`results/`) — out-of-sample testing, parameter-sensitivity sweeps, regime testing (2020 crash, 2022 bear, 2023–25 chop), Monte Carlo drawdown estimation. Strategies that fail are eliminated with the reason documented.
4. **Playbook** (`playbook/`) — the survivor(s) become `PLAYBOOK.md`: precise, mechanical instructions a Claude agent can execute, plus `screener.py` to produce today's signals.
5. **Paper trade** (`papertrade/`) — daily runner that submits bracket orders to the Alpaca paper endpoint and journals every decision.

## Pass bar for the playbook

Out-of-sample profit factor > 1.3, max drawdown < ~25%, ≥100 trades in the test window, beats buy-and-hold SPY on a risk-adjusted (Sharpe) basis.

## Known limitations

- Free daily-bar data (Alpaca IEX / yfinance) lacks delisted tickers → survivorship bias. Reports carry this caveat; universes are liquidity-screened to reduce its impact.
- Backtests model slippage but not borrow/locate issues (irrelevant: long-only) or intraday fills beyond the open.
- Past performance does not guarantee future results; the validation gauntlet reduces, but cannot eliminate, the risk that an edge is noise.

## Alpaca MCP server (local sessions only)

`.mcp.json` configures the [Alpaca MCP server](https://github.com/alpacahq/alpaca-mcp-server)
for Claude Code **project-wide**, so any local session in this repo picks it up — no
`%APPDATA%` editing, and unlike `claude_desktop_config.json` it applies to Claude Code
rather than Claude Desktop.

**Requires:** Python 3.10+, [`uv`](https://docs.astral.sh/uv/) on PATH, and the two keys
already used by `papertrade/` **exported into the environment** — `.mcp.json` expands
`${VAR}` from the shell, it does not read `.env` the way `python-dotenv` does:

```powershell
# PowerShell, from the project root
Get-Content .env | Where-Object { $_ -match '^\s*ALPACA_' } | ForEach-Object {
  $k, $v = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), 'User')
}
```

```bash
# bash/zsh
set -a && source .env && set +a
```

Then start Claude Code from the project root and approve the server when prompted
(`/mcp` lists its status).

**Toolsets are restricted to read-only by default.** `ALPACA_TOOLSETS` omits `trading`,
so the server cannot place, modify, or cancel orders — matching the golden rule in
`CLAUDE.md` that reporting and tooling never touch the order path. Note the `account`
toolset still exposes `close_position`, so this is "cannot open new orders" rather than
strictly read-only. `ALPACA_PAPER_TRADE` defaults to `true`; both are overridable via the
environment if you deliberately need more.

### Using it from a Claude Code cloud session

Cloud sessions run in a container whose default **Trusted** egress policy blocks
`*.alpaca.markets` and Yahoo, so the server starts but every call fails. To fix it, edit
the environment at [claude.ai/code](https://claude.ai/code): click the **cloud icon**
showing the environment name in the row above the message box, hover the environment, and
click the **gear**. (There is no settings URL for this selector.)

Set **Network access → Custom**, keep **"Also include default list of common package
managers"** checked — `uvx` needs PyPI — and add:

```text
paper-api.alpaca.markets
data.alpaca.markets
query1.finance.yahoo.com
query2.finance.yahoo.com
fc.yahoo.com
```

Deliberately **not** `*.alpaca.markets`: that would also reach `api.alpaca.markets`, the
live-trading endpoint. This list can only reach the paper account and market data, which
matches PLAYBOOK §5 ("never trade live"). If yfinance fails on its cookie/crumb handshake,
add `*.yahoo.com`.

In the same dialog, add the keys under **Environment variables** (`.env` format) —
`.env` is gitignored so it does **not** exist in the container, and `.mcp.json`'s
`${ALPACA_API_KEY}` would otherwise expand to nothing:

```text
ALPACA_API_KEY=PK...
ALPACA_SECRET_KEY=...
```

Note the dialog's own warning that these values are visible to anyone using the
environment; keep them paper-trading keys.

Save, then **start a new session** — the VM is provisioned at session start, so a running
session won't pick up the change. Verify with
`curl -sS -o /dev/null -w '%{http_code}\n' https://paper-api.alpaca.markets/v2/account`
(401 = reachable, credentials simply not passed by curl; `000` = still blocked).

GitHub traffic uses a separate proxy and is unaffected by this setting. Environments are
personal to your account, so no admin action is needed.

## Layout

```
research/    strategy cards + ranked catalog
data/        cached daily OHLCV (parquet), universe lists
backtest/    engine, universe builder, metrics, strategy modules
results/     per-strategy reports and robustness tables
playbook/    PLAYBOOK.md (agent-executable spec) + screener.py
papertrade/  Alpaca paper-trading daily runner + decision journal
```
