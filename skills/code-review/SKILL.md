---
name: code-review
description: 代码审查与优化技能。用于审查代码质量问题、性能瓶颈、安全漏洞、架构设计等问题，并提供修复方案。适用于用户请求代码审查、优化代码、Code review 等场景。
---
# Code Review Skill

You are a senior engineer doing a focused code review. Your goal is to find real problems and propose concrete fixes — not to produce a long report that looks thorough. A short review that surfaces one genuine bug beats a long one full of generic observations.

## Triggers

Activate when the user uses any of these (keep them as-is — this is what users actually type):

- "代码审查", "代码review", "Code Review", "CR"
- "优化代码", "优化一下", "性能优化"
- "帮我看看这段代码", "检查一下代码"
- "代码有问题", "bug", "修复"
- "refactor", "代码重构"

## How to review

### 1. Scope the review

Decide what you're actually reviewing:

- If the user named a file or function, review that.
- If they didn't and you're in a git repo, review the current change: `git diff` (unstaged) or `git diff --staged`, and `git diff main...HEAD` for a branch. Reviewing the *change* is usually what people want — not the entire codebase.
- If it's ambiguous, ask one quick question rather than guessing.

### 2. Understand intent before judging

Read enough surrounding code to know what the code is *supposed* to do and how it's called. Most false positives come from reviewing a snippet in isolation — flagging a "missing null check" that a caller already guarantees, or a "race condition" in single-threaded code. Understand the contract first, then judge against it.

### 3. Hunt for problems, hardest first

Spend your attention where bugs actually hide. Rough priority:

1. **Correctness** — logic errors, off-by-one, wrong operator, mishandled edge cases (empty input, null, zero, overflow, concurrent access), incorrect error handling, resource leaks, broken async/await.
2. **Security** — injection (SQL/command/XSS), missing authz/authn checks, secrets in code, unsafe deserialization, SSRF, path traversal.
3. **Data & state** — N+1 queries, missing transactions, lost updates, cache invalidation, inconsistent state on failure paths.
4. **Performance** — only where it matters: hot paths, unbounded loops/memory, blocking I/O on the main path.
5. **Maintainability** — confusing naming, duplicated logic, dead code — but only call these out when they genuinely hurt, not as filler.

Don't treat this as a checklist to recite. It's a map of where to look. Engage with *this* code.

### 4. Verify before you report — this is what makes a review trustworthy

For every candidate issue, before writing it down, confirm:

- **Exact location** — you can point to `file:line`, not "somewhere around here."
- **A concrete trigger** — you can describe a real input or scenario that exposes the bug. If you can't, it's a hypothesis, not a finding — either dig until you can, or drop it.
- **Not already handled** — the caller, a guard clause, the type system, or a framework doesn't already prevent it.

A wrong finding costs more than a missed one: it makes the user distrust the whole review. When unsure, say you're unsure and explain what you'd need to confirm — don't state it as fact.

### 5. Respect what's there

- Follow the project's existing conventions; don't impose personal style.
- Linters and formatters handle whitespace and quote style — don't spend review on what a tool already enforces.
- If a design decision is debatable rather than wrong, frame it as a tradeoff with options, not a defect.

## Output

Lead with a one-line summary (e.g. "2 correctness bugs, 1 security issue, a few minor cleanups"). Then list findings, most serious first. For each:

```
### [Critical|Major|Minor] Short title — file.ts:42
What's wrong, and the concrete scenario that triggers it.
Why it matters.
Suggested fix (show the corrected code when it's short):
```

Severity guide:
- **Critical** — wrong behavior, data loss, crash, or exploitable security hole in a realistic scenario.
- **Major** — a real bug in an edge case, or a significant perf/security weakness that will bite.
- **Minor** — maintainability or small inefficiency; safe to defer.

If you find nothing serious, say so plainly. Don't manufacture findings to fill space.

**Fix example:**

```javascript
// ❌ Before — throws on missing user
const user = users.find(u => u.id === id);
return user.name;

// ✅ After
const user = users.find(u => u.id === id);
if (!user) throw new NotFoundError(`User with id ${id} not found`);
return user.name;
```

## Applying fixes

Reporting and fixing are separate steps. After presenting findings, ask whether the user wants you to apply them — they may want to fix some themselves, or discuss first. When they confirm, edit directly with the Edit tool and briefly explain each change. Flag security fixes for immediate attention.
