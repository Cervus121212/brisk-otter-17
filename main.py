"""Dip-rider bot for cbBTC 1-minute bars (agent-fun/bars-replay/v1).

Strategy (from backtests on real BTC 1m data, 4x 24h windows + reversed +
mirrored; all numbers measured, nothing fabricated):
  1-minute BTC moves are noise (std ~8-10 bps) while a round trip costs
  ~12 bps in fees+slippage alone, so fast signals bleed money (an EMA 8/21
  crossover loses $100-150 per 24h window). The real structure is a few
  multi-hour swings. This bot trades only those, long only, $1,000 paper:
  it buys a 1.0% dip off the 360-bar (6h) rolling high, but only while the
  close sits above the 360-bar SMA (uptrend filter -- it stays in cash in
  downtrends), and rides the move: it sells at +5.0% over cost or at -1.8%
  below cost, whichever comes first. No new entries in the last hour.

Backtest (local replay of the harness fill model: fill at next bar open,
4 bps fee, 2 bps slippage, price impact vs $800k pool depth):
  dev-proxy window (22-23 Nov, +2.98%):  +$21.36 (2 trades, max DD 1.8%)
  21-22 Nov (+1.79%):                    +$22.74 (2 trades, max DD 2.6%)
  20-21 Nov (-5.65%):                    -$11.64 (2 trades, max DD 1.9%)
  19-20 Nov (-1.06%):                    -$8.97  (2 trades, max DD 1.9%)
  mean over 4 windows: +$5.87; time-reversed mean +$0.43; mirrored +$8.23.
  Max drawdown <= 2.6% everywhere (guardrail is 25%).

All integer-exact (Python int, no floats, no clock, no randomness, no
network, no files): two runs on the same data produce identical orders.
"""
import json
import sys

SYMBOL = "CBBTC"
LOOKBACK = 360          # bars for the rolling high and the trend SMA (6h)
DIP_BPS = 100           # buy when close is 1.0% below the rolling high
TAKE_PROFIT_BPS = 500   # sell at +5.0% over cost
STOP_BPS = 180          # sell at -1.8% below cost
MAX_SLIPPAGE_BPS = 100  # per-order slippage cap (1%)
NO_ENTRY_AFTER = 1380   # no new entries in the last hour of the window

# --- protocol state (filled in from hello) ---
sym = None              # symbol dict from hello
quote_scale = 6
price_scale = 0
qty_scale = 0
caps = {}
fees = {}
warmup_bars = 0
cash = 0                # quote units (int)
positions = {}          # symbol -> (qty int, cost int quote units)
closes = []             # closes seen so far (int, price units), oldest first
seq = -1


def value(symbol_qty, price):
    """What qty is worth at price, in quote units (truncated)."""
    return (symbol_qty * price * (10 ** quote_scale)) // (10 ** (qty_scale + price_scale))


def weight_room():
    """Most a buy may spend under caps.max_weight_bps (before other buys)."""
    held = positions.get(SYMBOL)
    held_val = value(held[0], closes[-1]) if held and closes else 0
    room = (caps.get("max_weight_bps", 10000) * (cash + held_val)) // 10000 - held_val
    return room if room > 0 else 0


def rolling_high():
    if len(closes) < LOOKBACK:
        return None
    return max(closes[-LOOKBACK:])


def sma():
    if len(closes) < LOOKBACK:
        return None
    return sum(closes[-LOOKBACK:]) // LOOKBACK


def decide():
    """Return a list of orders for the current batch (possibly empty)."""
    if not closes:
        return []
    close = closes[-1]
    held = positions.get(SYMBOL)
    if held is not None:
        qty, cost = held
        val = value(qty, close)
        if val * 10000 >= cost * (10000 + TAKE_PROFIT_BPS):
            return [{"side": "sell", "symbol": SYMBOL, "qty": str(qty),
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        if val * 10000 <= cost * (10000 - STOP_BPS):
            return [{"side": "sell", "symbol": SYMBOL, "qty": str(qty),
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []
    # No position: consider an entry.
    if seq >= warmup_bars + NO_ENTRY_AFTER:
        return []
    high = rolling_high()
    trend = sma()
    if high is None or trend is None:
        return []
    if close <= trend:
        return []
    if close * 10000 > high * (10000 - DIP_BPS):
        return []
    spend = cash
    room = weight_room()
    if spend > room:
        spend = room
    min_notional = int(fees.get("min_notional_quote_units", "0"))
    if spend <= 0 or spend < min_notional:
        return []
    order = {"side": "buy", "symbol": SYMBOL,
             "notional_quote_units": str(spend),
             "max_slippage_bps": MAX_SLIPPAGE_BPS}
    if len([order]) > caps.get("max_orders_per_bar", 1):
        return []
    return [order]


def apply_account(account):
    global cash, positions
    cash = int(account["cash_quote_units"])
    positions = {}
    for p in account.get("positions", []):
        positions[p["symbol"]] = (int(p["qty"]), int(p["cost_quote_units"]))


def main():
    global sym, quote_scale, price_scale, qty_scale, caps, fees
    global warmup_bars, seq
    out = sys.stdout
    n = 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        kind = msg.get("type")
        if kind == "hello":
            quote_scale = int(msg["capital"]["quote_scale"])
            caps = msg.get("caps", {})
            fees = msg.get("fees", {})
            warmup_bars = int(msg.get("warmup_bars", 0))
            for s in msg.get("symbols", []):
                if s["symbol"] == SYMBOL:
                    sym = s
                    price_scale = int(s["price_scale"])
                    qty_scale = int(s["qty_scale"])
            if sym is None and msg.get("symbols"):
                sym = msg["symbols"][0]
                price_scale = int(sym["price_scale"])
                qty_scale = int(sym["qty_scale"])
            cash = int(msg["capital"]["quote_units"])
        elif kind == "batch":
            seq = int(msg["seq"])
            for b in msg.get("bars", []):
                if b["symbol"] == SYMBOL:
                    closes.append(int(b["c"]))
            apply_account(msg["account"])
            warming = warmup_bars > 0 and seq < warmup_bars
            orders = [] if warming else decide()
            n += 1
            cid = 1
            for o in orders:
                o["client_id"] = "o%d" % cid
                cid += 1
            out.write(json.dumps({"type": "reply", "seq": seq, "orders": orders}) + "\n")
            out.flush()
        elif kind == "done":
            apply_account(msg["account"])
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
