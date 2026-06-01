---
name: cr
description: Code review slash command. Review a specific file or the current git diff for quality issues, bugs, security vulnerabilities, and performance problems.
---

# Code Review

## Input

If `$ARGUMENTS` is provided, treat it as the target:
- A file path → read and review that file
- A glob or directory → read all matching files
- Empty → run `git diff HEAD` (or `git diff --staged` if there are staged changes) and review the diff

## Review dimensions

Analyze the target code across these dimensions — skip any that aren't applicable:

**Code quality**: naming, readability, DRY violations, error handling, function complexity  
**Security**: injection risks, auth/authz gaps, sensitive data exposure, input validation  
**Performance**: N+1 queries, unnecessary re-renders, missing indexes, blocking calls  
**Architecture**: separation of concerns, dependency direction, coupling  
**Frontend** (if applicable): component design, state management, XSS/CSRF, accessibility  
**Backend** (if applicable): API design, database efficiency, concurrency safety, logging  

## Output format

```
## Code Review: [file or "current diff"]

### Issues found

#### [Critical] <title>
- **Location**: file:line
- **Problem**: what's wrong and why it matters
- **Fix**: concrete suggestion or corrected code snippet

#### [Warning] <title>
...

#### [Suggestion] <title>
...

### Positives
- ...

### Summary
One or two sentences on overall quality and the most important thing to address.
```

Use only the severity levels that apply. If nothing is found in a category, omit it — don't write "no issues found" for every dimension.

## After the report

Ask the user: "Should I apply any of these fixes?" If they say yes (or specify which ones), make the edits directly with the Edit tool. Explain briefly what changed and why.
