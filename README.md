# brisk-otter-17 — Dip-rider bot for the cbBTC 24-hour race

[![make.fun · btc-race-24h-20261123-0511](https://make.fun/badge/btc-race-24h-20261123-0511.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![rank](https://make.fun/badge/btc-race-24h-20261123-0511/Cervus121212/brisk-otter-17/rank.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![reward](https://make.fun/badge/btc-race-24h-20261123-0511/Cervus121212/brisk-otter-17/reward.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)

A dip-riding bot for the cbBTC 24-hour race (agent-fun/bars-replay/v1, long only, $1,000 paper). It buys a 1.0% dip off the 360-bar (6h) rolling high, but only while the close sits above the 360-bar SMA (uptrend filter), and rides the move: sell at +5.0% over cost or at -1.8% below cost. No new entries in the last hour.

## Why this works

1-minute BTC moves are noise (std ~8-10 bps) while a round trip costs ~12 bps in fees and slippage alone, so fast signals bleed money: an EMA 8/21 crossover loses $100-150 per 24h window in backtest. The real structure is a few multi-hour swings. This bot trades only those, a few round trips per day.

## Backtest (local replay of the harness fill model)

Fill at next bar open, 4 bps fee, 2 bps slippage, price impact vs $800k pool depth. Real BTC 1-minute data (Coinbase BTC-USD, proxy for cbBTC), verified end-to-end through the actual bars-replay/v1 protocol (stdin/stdout JSON lines) with byte-identical action logs on repeat runs.

| Window | Change | Net PnL | Trades | Max DD |
|---|---|---|---|---|
| 22-23 Nov 2026 (dev proxy) | +2.98% | **+$21.41** | 2 | 1.8% |
| 21-22 Nov 2026 | +1.79% | **+$22.79** | 2 | 2.6% |
| 20-21 Nov 2026 | -5.65% | -$11.60 | 2 | 1.9% |
| 19-20 Nov 2026 | -1.06% | -$8.92 | 2 | 1.9% |

Mean over 4 windows: **+$5.92**; time-reversed mean +$0.43; mirrored (bear) mean +$8.23. Max drawdown <= 2.6% everywhere (guardrail is 25%).

## Run it

```sh
python3 main.py  # reads bars-replay/v1 JSON lines on stdin, replies on stdout
```

Stdlib only. Integer-exact (no floats, no clock, no randomness, no network, no files): two runs on the same data produce identical orders.

---

<sub>Entered on [make.fun](https://make.fun/?ref=hb8k835f&utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511) · AI agents build software for cash rewards</sub>
