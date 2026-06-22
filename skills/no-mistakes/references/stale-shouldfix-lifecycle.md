# Stale SHOULD FIX Lifecycle

nm creates GitHub issues for deferred SHOULD FIX findings. Over time, these stack
up — most are **already resolved** by later merges or were **false positives** from
the start. Before implementing any old SHOULD FIX, verify against current code.

## Pattern

1. List open issues: `gh issue list --state open --limit 20`
2. For each SHOULD FIX: pull the body, read the referenced code paths
3. **Verify** — is the problem still present in current master?
4. Categorize and act:

| Verdict | Action |
|---------|--------|
| **Still valid** | Fix it (add test, remove dead code, etc.) |
| **False positive** | Close: `gh issue close N -r "completed" -c "explanation"` |
| **Already resolved** | Close: `gh issue close N -r "completed" -c "explanation"` |
| **WONTFIX / test-only** | Close: `gh issue close N -r "not planned" -c "explanation"` |

## Common false-positive patterns

- **"Dead code" that IS called** — nm didn't see the call site in another module
- **"Test deleted" that was renamed/updated** — old name gone, new test exists
- **"Duplication" in test helpers** — test-only code with different signatures
- **"Inconsistency" post-merge** — later feature branches fixed the issue

## Close reasons

Use `--reason` to signal intent:
- `"completed"` — fixed, or verified as already fixed
- `"not planned"` — test-only, not feasible, or not worth the complexity

Always include `--comment` with specific evidence (file:line of the call site,
test name that replaced the old one, etc.). This prevents re-opening and gives
the next reviewer context.

## After resolution

- Update AGENTS.md test count if tests were added
- Single commit with per-item summary
- Push to master (no PR needed for SHOULD FIX cleanup — these aren't features)

## Example from Huat #5, #10-13

Five SHOULD FIX from old BAG-combo and zero-market-data features:
- #13 "resolve_option_conid dead" → false positive, called at trade.rs:50,58
- #12 "contract duplication" → test-only helper, WONTFIX
- #11 "AGENTS.md inconsistency" → already resolved post-BAG-combo
- #10 "PendingOrders test deleted" → renamed to pending_orders_single_order_tracks_strangle
- #5 "asymmetrical call-side edge" → genuine gap, added mirrored test

Result: 1 code fix, 4 closed as resolved/false-positive. 235 tests.
