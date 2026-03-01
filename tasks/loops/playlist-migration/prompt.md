# Playlist Migration — Implementation Prompt

## Context

You are building `song-shift`, a Python CLI tool that migrates playlists between music streaming services. The initial version supports Apple Music and Tidal. The tech stack is Python 3.12+, Click (CLI), httpx (HTTP), tidalapi (Tidal SDK), PyJWT (Apple Music auth), rapidfuzz (track matching), and pytest (testing). Package management uses `uv`.

## Session Startup Ritual

1. Run `pwd` to confirm you are in `/Users/shaun/Documents/song-shift`
2. Run `git log --oneline -5` to see recent progress
3. Study `tasks/loops/playlist-migration/AGENTS.md` — absorb project patterns, commands, and architectural decisions
4. Study `tasks/loops/playlist-migration/todo.md` — find the highest-priority INCOMPLETE task (first unchecked `- [ ]` item)
5. Study the spec at `tasks/loops/playlist-migration/specs/spec.md` for context on that task
6. Use parallel subagents to study the codebase files relevant to the task (e.g. if implementing TidalProvider, study models.py, base.py, and config.py in parallel)

## Subagent Rules

- **Use the main context as a scheduler.** Spawn subagents for expensive reading rather than doing it in the primary context window.
- **Parallel subagents for reading/research.** Use multiple subagents to study specs, source files, and existing patterns simultaneously.
- **Only 1 subagent for build/tests.** Build and test execution must be serial — this is your backpressure mechanism. Never run tests in parallel.
- **Garbage collection.** Each subagent's context is discarded after it returns. Use subagents for investigation, then act on the findings in the main context.

## Execution Rules

- Complete exactly ONE task per iteration. Do not attempt multiple tasks.
- Do NOT assume functionality is missing — confirm with code search first.
- Study existing code patterns before writing new code.
- Run `uv run pytest -x -q` after every change (backpressure).
- If a task says to run tests for a specific file, run that specific test file first, then run the full suite.
- If tests fail, fix the root cause before committing. Do NOT move on with broken tests.
- If you cannot resolve a failure after 3 attempts, document the blocker in `tasks/loops/playlist-migration/todo.md` as a note under the task and move on to the next task.
- Commit with a descriptive message after tests pass.
- Push to the working branch after committing: `git push -u origin claude/playlist-migration-plan-SfdvN`
- **NEVER push to any other branch.**
- It is UNACCEPTABLE to remove, skip, or weaken any existing test to make it pass.
- It is UNACCEPTABLE to use `# type: ignore`, `noqa`, or similar suppressions to hide real issues.

## Implementation Order

Follow `tasks/loops/playlist-migration/todo.md` phases sequentially. Each phase should be a separate commit (or multiple commits if the phase has multiple tasks). Run `uv run pytest -x -q` after each change to verify nothing is broken.

## Session End Ritual

**CRITICAL — YOU MUST DO ALL OF THESE BEFORE EXITING:**

1. **UPDATE TODO.MD CHECKBOXES** — Mark the completed task with `[x]` in `tasks/loops/playlist-migration/todo.md`. This is MANDATORY. If you skip this, the next iteration will redo the same task forever. Change `- [ ]` to `- [x]` for the task you just completed.
2. Run `uv run pytest -x -q` one final time to confirm clean state.
3. If all tasks in the current phase are complete, note this in todo.md.
4. **COMMIT AND PUSH the todo.md update** — The todo.md change MUST be included in your commit or as a separate commit. Without pushing this, the next iteration cannot see your progress.
5. **VERIFY THE PUSH SUCCEEDED** — Run `git log --oneline -3` and confirm your commit is there, then run `git push -u origin claude/playlist-migration-plan-SfdvN` if not already pushed.
