# AGENTS.md — AI Development Rules for gentaron

> **Version**: 1.0.0
> **Maintainer**: gentaron
> **Effective**: All AI assistants (Z.AI, Claude, Cursor, Copilot, etc.)

This file is the **highest priority** instruction set for any AI operating on this repository.

---

## 1. Entry Point Protocol (The Boot Sequence)

When accessing this repository, read files in this exact order:

1. **AGENTS.md** (this file) — highest priority instructions
2. **CLAUDE.md** (if exists) — supplementary instructions
3. **README.md** — project overview and purpose
4. **package.json** or equivalent manifest — dependencies and scripts
5. **src/ or lib/ entry point** — architecture overview
6. **Test files** — expected behavior

Do NOT skip or reorder this sequence.

---

## 2. Deadlock Prevention

### 2.1 Iteration Cap
For any single task, never repeat the same approach more than 3 times:
- Attempt 1: Execute initial approach
- Attempt 2: Fine-tune and retry
- Attempt 3: Switch to a **completely different approach**
- Attempt 4+: Report to user and ask for guidance

### 2.2 Blocker Detection & Escalation
Detect these conditions immediately and report to user:
- Build error unresolved after 3 consecutive attempts
- Dependency installation failure
- Tests unable to run due to environment issues
- Required files or directories missing

When a blocker is detected:
1. Explain the current situation concisely
2. List attempted approaches
3. Provide possible causes
4. Suggest up to 3 next actions for user

### 2.3 Circular Dependency Detection
If editing A requires changing B, and B requires changing A:
1. **Stop immediately** — make neither edit
2. Visualize the circular structure
3. Propose interface extraction
4. Let user decide

### 2.4 Indecision Resolution
When multiple equally valid implementations exist:
1. List pros and cons of each option
2. Evaluate against **existing project patterns**
3. If still undecided → choose the **simplest implementation**
4. Document the reasoning in a comment

Never enter a "cannot decide, stopping work" state.

### 2.5 Scope Boundary Enforcement
- Task is "done" when minimum requirements are met
- Do NOT make incidental improvements — treat them as separate tasks
- Refactoring only when explicitly requested
- Out-of-scope improvements: list as **proposals** after task completion (do not execute)

---

## 3. Task Execution Protocol

### 3.1 Pre-Implementation Decomposition
Before starting any task:
1. Break into maximum 5 subtasks
2. Estimate steps per subtask
3. Explicitly state dependencies between subtasks
4. Determine execution order and present to user

### 3.2 Phased Implementation & Verification
1. Skeleton (type definitions and interfaces only)
2. Core logic (happy path only)
3. Error handling
4. Integration (connect with existing code)
5. Verification (build / test / manual check)

**Build must pass at each phase. Never proceed to next phase with a broken build.**

### 3.3 Minimal Edit Principle
- Max 10 files per editing session
- Minimize lines changed per file
- Do not mix formatting changes with logic changes
- Prefer commenting out over deleting

---

## 4. Error Recovery Protocol

### 4.1 Error Classification

| Category | Action |
|----------|--------|
| Syntax error | Fix immediately. Verify type definitions, do not guess |
| Runtime error | Add error handling. Investigate root cause |
| Environment error | Verify prerequisites. **Report to user** |
| Design error | **Stop implementation**. Revisit design |
| Test error | Verify test intent. Fix implementation or test |

**Environment and design errors: do NOT attempt to resolve independently. Report to user immediately.**

### 4.2 Rollback Strategy
When implementation is not progressing:
1. Save current changes with `git stash` or temporary commit
2. Restore to last working state
3. Analyze root cause
4. Re-implement with different approach

### 4.3 Fallback Chain
1. **Ideal implementation** → on failure:
2. **Simplified implementation** (simpler approach) → on failure:
3. **Minimal implementation** (core functionality only) → on failure:
4. **Stub implementation** (interface only + TODO comment)

---

## 5. Quality Verification Protocol

### 5.1 Verification Gates
- **On file save**: Linter and type checker pass with zero errors
- **On feature completion**: Related tests all pass, build succeeds
- **On task completion**: Full test suite, full build, self-review

### 5.2 Self-Review Checklist
Before marking any task complete:
- [ ] All user requirements met
- [ ] Error handling is appropriate
- [ ] No hardcoded values
- [ ] No security issues
- [ ] Naming is consistent
- [ ] No leftover comments or debug code

---

## 6. Conflict Resolution Protocol

### 6.1 Rule Priority Hierarchy
1. **User's explicit instructions** (highest priority)
2. **AGENTS.md / CLAUDE.md rules**
3. **Existing project patterns and conventions**
4. **Industry best practices**
5. **AI's general judgment** (lowest priority)

### 6.2 Security vs Functionality
- **Always prioritize security**
- Never implement insecure solutions
- If user knowingly requests a security risk: explain the risk and propose safer alternatives

---

## 7. Communication Protocol

### 7.1 Progress Report Format
**Done**: ✅ [Task name] complete — Implementation: ... — Changed files: ...
**Blocker**: 🚫 [Task name] blocked — Cause: ... — Attempted fixes: ...
**In Progress**: 🔄 [Task name] in progress — Progress: ... — Remaining: ...

### 7.2 Question Rules
- Maximum 3 questions at a time
- Include recommended answers for each question
- Prefer Yes/No format
- Do not ask about matters solvable by general best practices

---

## 8. Context Management

### 8.1 Cross-Session State Inheritance
When a session is interrupted:
1. Reload AGENTS.md / CLAUDE.md
2. Check `git log --oneline -10`
3. Check `git status`, `git diff`
4. Search for TODO/FIXME comments
5. Report to user: "Continuing from previous session"

---

## 9. Commit & Push Rules

### 9.1 Conventional Commits
Use conventional commit format:
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `refactor:` code restructuring
- `test:` test additions/modifications
- `chore:` maintenance

### 9.2 Commit Scope
- One logical change per commit
- Do not mix unrelated changes
- Keep commit messages concise and descriptive

---

**This ruleset applies to all repositories under the gentaron GitHub account.**
**Do not override these rules with general AI behavior.**
