# F026: Auto-Update Docs CLI Cache on Release

**Priority:** P2
**Dependencies:** F021 (--release), F024 (--help-json generation), dokima-docs repo
**Status:** Pending

## User Story

As a maintainer running `dokima --release patch`, the docs site at https://dokima-docs.vercel.app automatically reflects the new version and any new/changed CLI flags without manual intervention.

## Current State

```
dokima --release patch
  → bumps VERSION to 1.2.5
  → tags v1.2.5
  → creates GitHub Release

dokima-docs site
  → CLI page shows v1.2.4 (stale)
  → new flags from v1.2.5 missing
```

## Desired State

```
dokima --release patch
  → bumps VERSION to 1.2.5
  → tags v1.2.5  
  → creates GitHub Release
  → clones dokima-docs repo (shallow)
  → runs dokima --help-json > scripts/cli-help.json
  → commits + pushes to dokima-docs main
  → Vercel auto-deploys → CLI page shows v1.2.5 ✅
```

## Design

### Approach
Update `do_release()` in `utils.py` to push the updated `--help-json` output to the docs repo after release. Use a temp directory for shallow clone, avoid credentials in code.

### Files Changed
| File | Change |
|------|--------|
| `utils.py:do_release()` | After tag push, clone docs repo, update cache, commit, push |
| `VERSION` | No change |

### Flow

```
do_release(bump, project_dir, dry_run):
  1-16. [existing] validate, bump, commit, tag, push, create release
  17.  [NEW] If not dry_run and gh CLI available:
       a. Clone dokima-docs to /tmp with `gh repo clone siongsheng/dokima-docs -- --depth=1`
       b. Run `dokima --help-json > <clone>/scripts/cli-help.json`  
       c. cd clone && git add scripts/cli-help.json
       d. git commit -m "chore: update CLI reference for v{new_version}"
       e. git push
       f. rm -rf clone
  18. Print summary (existing)
```

### Edge Cases
- **docs clone fails** → warn, continue release (non-blocking)
- **git push to docs fails** → warn, continue release (non-blocking)
- **dry_run mode** → skip docs update, print "[DRY RUN] Would update docs cache"
- **gh CLI not installed** → skip docs update, warn
- **dokima-docs repo doesn't exist** → skip, warn
- **merge conflict on docs push** → skip, warn (docs maintainers resolve)

### Non-Goals
- Does NOT auto-add new pages for new features — only updates CLI reference cache
- Does NOT require GitHub credentials beyond `gh` CLI (already required by `do_release`)
- Does NOT run on every merge — only on `--release`

## Impact

Maintainers run one command and everything stays in sync. No manual "oh I forgot to update the docs" moments. The docs site always reflects the actual CLI, version-accurate, within 60 seconds of a release.

## Confidence

**High** — single well-bounded change in an existing function. Non-blocking on failure. Uses `gh` CLI already available. 15-20 lines of new code.
