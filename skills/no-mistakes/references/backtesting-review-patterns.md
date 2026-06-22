# Backtesting Review Patterns

Common numerical and logic errors found by nm adversarial review on financial
backtesting code. These are reusable review checkpoints — when reviewing any
backtesting, P&L, or options-trading code, test each of these explicitly.

## 1. P&L Percentage Inversion

**Pattern:** `close_value / entry_value` instead of `(entry_value - close_value) / entry_value`

When closing a short options position, the formula for percentage profit is:
```
pnl_pct = (credit_received - exit_cost) / credit_received
```

A common bug computes `exit_cost / credit_received` instead — this inverts
every result (a 72% winner reports as 28%, a 30% loser reports as 70%).

**Review check:** For every `pnl_pct` / `return_pct` field, verify the
formula produces `> 0` for profitable trades and `< 0` for losing trades.
Test with known values: credit=$6.40, exit=$1.80 → should be 72%, not 28%.

## 2. Equity Curve Corruption on Missing Pricing Data

**Pattern:** When bid/ask data is missing (delisted strikes, zero bids),
the MTM function returns `bid_close=0`. If the equity curve tracking uses
this raw value without checking `bid_missing`, unrealised P&L appears
inflated (position looks fully profitable) and max drawdown is corrupted.

**Fix:** Check `bid_missing` flag before computing unrealised P&L for the
equity curve. When pricing is unavailable, fall back to cumulative realised
P&L only — unrealised gain/loss is unknowable.

**Review check:** Trace the equity curve push path. When `bid_missing=true`,
does the code skip unrealised P&L? When all bids in a day are missing, does
the equity curve degrade gracefully or corrupt the drawdown?

## 3. End-of-Data Position Close Missing from Drawdown

**Pattern:** Positions closed at end-of-data (after the main loop) update
`cumulative_pnl` and push a trade record, but the final equity curve point
and drawdown update are omitted. The last trade's effect is invisible to
`max_drawdown` and `max_drawdown_pct`.

**Fix:** Push a final equity point after the end-of-data close, and
recalculate peak/drawdown.

**Review check:** Find the end-of-data / force-close path. Is there a
corresponding equity curve push and drawdown update?

## 4. Breakeven Trade Classification

**Pattern:** `filter(|t| t.pnl_dollars <= 0.0)` counts breakeven trades as
losses, understating win rate. Should use `< 0.0` (strictly negative) for
losses, or handle `pnl == 0` as a separate category.

**Review check:** Check the win/loss filter boundary. Is `<=` used where
`<` should be? Are breakeven trades inflated into losses?

## 5. Mid vs Bid Exit Pricing

**Pattern:** Spec says "exit at bid (conservative)" but code uses
`(bid + ask) / 2` for the exit price. In options, exiting at bid means
using the bid side only (what you pay to buy back).

**Review check:** Cross-reference the spec's exit execution section with the
code's exit price formula. For short options backtesting, exit_cost should
be `put_bid + call_bid`, not `(put_bid+put_ask+call_bid+call_ask)/2`.

## 6. Missing Entry Gates

**Pattern:** Spec mandates calling `decisions::check_duplicate`,
`check_symbol_count`, and `check_global_bpr` before entry. Code skips some
because they're "not needed for v1 single-symbol."

**Review check:** List every gate function imported. Is each one called in
the entry path? Missing calls should be TODO-documented, not silently absent.

## 7. Cross-Module Filter Boundary Drift

**Pattern:** Module A classifies losses as `pnl_dollars < 0.0` (strict). Module B
computes average loss using `pnl_dollars <= 0.0` (inclusive). Module A reports
`loss_count` = 10 but Module B sums over 12 trades — denominator mismatch,
average silently wrong.

**Root cause:** Filter boundaries copied independently in each module without
a shared constant or type. `<=` and `<` look similar but produce different sets
when pnl_dollars can be exactly zero.

**Fix:** Use identical predicates everywhere. Prefer `< 0.0` for losses (breakevens
are their own category, not losses). Grep for every `pnl_dollars` comparison
— all must match.

**Review check:** `rg 'pnl_dollars.*[<>]'` across the entire codebase. Every
occurrence should use the same boundary (`< 0.0`, not `<= 0.0`). If they differ,
flag as SHOULD FIX — the consumer and producer are out of sync.

## 8. NaN Silently Corrupts f64 Comparisons (Rust)

**Pattern:** `f64::NAN > 0.0` is always `false`. When NaN enters an equity
curve (from 0/0 division, `sqrt(-1)`, or propagating from upstream), all
subsequent `max()` and `>` comparisons silently fail. Max drawdown, peak equity,
and Sharpe ratio all under-report with zero warning.

**Review check:** Every `if current > peak` or `max(value, other)` that operates
on f64 values from user calculations (P&L, equity, ratios) must guard with
`is_finite()`. Flag any unguarded comparison on a computed f64 as SHOULD FIX.

## 9. Max Drawdown Denominator Uses Final Peak

**Pattern:** `max_drawdown_pct = max_dd / peak` where `peak` is the final
(full-history) peak equity, not the peak at the time the max drawdown occurred.
This understates the drawdown percentage — a $10k drawdown from a $110k peak
during a dip reports as $10k/$130k (7.7%) instead of $10k/$110k (9.1%) if the
portfolio later recovered to $130k.

**Fix:** Capture `peak_at_dd_time` when updating `max_dd` inside the drawdown
loop. Use that as the denominator, not the final `peak`:

```python
if dd > max_dd:
    max_dd = dd
    dd_pct_at_peak = peak  # capture peak at drawdown time
return max_dd, max_dd / dd_pct_at_peak if dd_pct_at_peak > 0 else 0.0
```

**Review check:** Find every `max_drawdown` / `max_dd_pct` computation. Does the
percentage use the peak at drawdown time or the all-time peak? If it uses the
all-time peak, the reported drawdown is lower than the actual worst-case
experienced by the portfolio. Flag as SHOULD FIX.

## 10. Duplicate Equity Curve Entry on End-of-Data Close

**Pattern:** The main loop pushes an equity curve entry every trading day. After
the loop, an end-of-data force-close pushes a **second** entry for the final
date — one with unrealised P&L, one with realised P&L after closing. When no
position is open (already closed during the loop), both entries have the SAME
value — a true duplicate that inflates the equity curve length and confuses
downstream analysis (date-indexed lookups return different values depending on
which entry they hit).

**Fix:** After the end-of-data close, check whether the last equity curve entry
already has the same date. If yes, **update** the entry's value instead of
pushing a new one:

```rust
let is_dup = equity_curve.last().map(|(d, _)| *d == date).unwrap_or(false);
if is_dup {
    equity_curve.last_mut().unwrap().1 = cumulative_pnl;
} else {
    equity_curve.push((date, cumulative_pnl));
}
```

**Review check:** Find every `equity_curve.push` call. Is there more than one
per date? Trace the end-of-data close path — does it push a new entry for a
date that already has one in the curve? Flag as SHOULD FIX if duplicates are
possible.
