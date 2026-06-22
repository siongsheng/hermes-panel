# Python Default Argument Binding Trap

Default arguments in Python are evaluated at **definition time**, not call time.
This causes a silent bug when the default references a module-level constant that
gets reassigned after import.

## The Trap

```python
# At module level — evaluated at import time
STARTING_CAPITAL = 100_000.0

def max_drawdown(pnl_list, starting=STARTING_CAPITAL):
    # `starting` is bound to 100_000.0 AT IMPORT — forever
    ...
```

Later, in `main()`:
```python
def main():
    global STARTING_CAPITAL
    STARTING_CAPITAL = args.starting_capital  # changed to 200_000

    # But max_drawdown() STILL defaults to 100_000!
    results = max_drawdown(pnls)  # silently wrong
```

Callers that pass no argument get the **import-time** value, which ignores any
runtime overrides applied via `--starting-capital` or similar.

## The Fix

Use `None` as the sentinel default and resolve at call time:

```python
def max_drawdown(pnl_list, starting=None):
    if starting is None:
        starting = STARTING_CAPITAL  # evaluated NOW, at call time
    ...
```

## Why nm Flags This

The function works correctly as long as callers explicitly pass `starting`.
But any call site that relies on the default (e.g., `check_regimes` calling
`max_drawdown(pnls)` without an explicit `starting`) will use stale values
after a `--starting-capital` override.

## Review Check

For any Python function with `param=MODULE_LEVEL_CONSTANT`:
1. Is the constant ever reassigned after import (via `global` or `nonlocal`)?
2. Are there call sites that rely on the default rather than passing explicitly?
3. If yes to both, the default is stale. Use `None` + runtime resolution.

## Impact

- `max_drawdown()` dollar amounts: **Cosmetic** — drawdown *percentage* unchanged
- `sharpe_ci()` / `sharpe_ratio()` risk-free rate: **Low** — default changes 1-2%
- Any function computing taxable gains or cost basis: **HIGH** — audit immediately
