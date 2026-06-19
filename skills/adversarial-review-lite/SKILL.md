---
name: adversarial-review-lite
description: "Adversarial review + TDD verification for Tech Lead — review dimensions, severity levels, 2-commit check, output format. Stripped constitution/sprint content."
version: 1.0.0
---

# Adversarial Review (Lite — Tech Lead Edition)

Three-pass review using a different model family from the coder.

## Pre-Review: TDD Verification

Before reading code, verify the two-commit pattern:
```
git log master..BRANCH --format="%H %ai %s"
```
- RED commit (test:) must have EARLIER timestamp than GREEN commit (feat:)
- Bundled commits (test + impl in one) = BLOCKER regardless of code quality

## Three Review Dimensions

### 1. Spec Compliance
- Approach matches decision table?
- API/interface matches proposal?
- ALL tasks completed?
- Scope creep? (code not in spec)
- README updated if spec required it?

### 2. Architectural Impact
- New dependencies or coupling?
- Breaking changes to API, DB schema, or types?
- Deployment impact?

### 3. Code Quality
- Correctness: does it do what it claims?
- Security: injection vectors, exposed secrets, missing auth?
- Error handling: edge cases, null checks, uncaught exceptions?
- Performance: N+1 queries, blocking calls where async needed?

## Severity

| Level | When | Action |
|-------|------|--------|
| **BLOCKER** | Spec violation, architecture break, TDD violation, missing guards, security, uncaught exceptions, missing README update when spec required it | Fix before merge |
| **SHOULD FIX** | Conventions, naming, AGENTS.md, redundant code, pre-existing pattern debt | File GitHub Issue |
| **NIT** | Formatting, comments, style | Optional |

## Judgment: Inherited vs New Debt

Pre-existing issues matching surrounding codebase pattern → SHOULD FIX (don't block). Only BLOCKER issues INTRODUCED by this change block merge.

## Output Format

```
## Adversarial Review

### Pre-Review: TDD Check
- RED commit: <hash> (<timestamp>)
- GREEN commit: <hash> (<timestamp>)
- Verdict: PASS / BLOCKED

### Spec Compliance
| Severity | Finding | Location |

### Architectural Impact
| Severity | Finding | Location |

### Code Quality
| Severity | Finding | Location |

### Verdict
VERDICT: APPROVED / CHANGES REQUESTED / BLOCKED
RISK: LOW / MEDIUM / HIGH
RELEASE: YES (patch/minor/major) / NO
- YES if: new functionality, API changes, or breaking changes visible to users
- level: patch=bugfix, minor=new feature, major=breaking change
```
