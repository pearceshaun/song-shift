# YouTube Provider -- Implementation Prompt

## Context

You are implementing a YouTube provider for song-shift, a Python CLI tool that migrates playlists between music services. The provider uses yt-dlp to extract track metadata from YouTube videos (chapters and description timestamps) and converts them to Track objects. This is a read-only/source-only provider following the same pattern as the existing ShazamProvider. Tech stack: Python 3.12+, Click CLI, pytest, uv package manager.

## Session Startup Ritual

1. Run `pwd` to confirm you are in the project root (`/home/user/song-shift`)
2. Run `git log --oneline -5` to see recent progress
3. Study `tasks/loops/youtube-provider/AGENTS.md` -- absorb project patterns, commands, and architectural decisions
4. Study `tasks/loops/youtube-provider/todo.md` -- find the highest-priority INCOMPLETE task (first unchecked `- [ ]` item)
5. Study the spec at `tasks/loops/youtube-provider/specs/spec.md` for context on that task
6. Use parallel subagents to study the codebase files relevant to the task (e.g. `song_shift/providers/shazam.py`, `tests/providers/test_shazam.py`, `song_shift/models.py`)

## Subagent Rules

- **Use the main context as a scheduler.** Spawn subagents for expensive reading rather than doing it in the primary context window.
- **Parallel subagents for reading/research.** Use multiple subagents to study specs, source files, and existing patterns simultaneously.
- **Only 1 subagent for build/tests.** Build and test execution must be serial -- this is your backpressure mechanism. Never run tests in parallel.
- **Garbage collection.** Each subagent's context is discarded after it returns. Use subagents for investigation, then act on the findings in the main context.

## Execution Rules

- Complete exactly ONE task per iteration. Do not attempt multiple tasks.
- Do NOT assume functionality is missing -- confirm with code search first.
- Study existing code patterns before writing new code.
- Run `uv run pytest -v` after every change (backpressure).
- If tests fail, fix the root cause before committing. Do NOT move on with broken tests.
- If you cannot resolve a failure after 3 attempts, document the blocker in `tasks/loops/youtube-provider/todo.md` and move on.
- Commit with a descriptive message after tests pass.
- Push to the current branch after committing.
- It is UNACCEPTABLE to remove, skip, or weaken any existing test to make it pass.

## Implementation Order

Follow `tasks/loops/youtube-provider/todo.md` phases sequentially. Each phase should be a separate commit. Run `uv run pytest -v` after each phase to verify nothing is broken.

## Session End Ritual

**CRITICAL -- YOU MUST DO ALL OF THESE BEFORE EXITING:**

1. **UPDATE TODO.MD CHECKBOXES** -- Mark the completed task with `[x]` in `tasks/loops/youtube-provider/todo.md`. This is MANDATORY. If you skip this, the next iteration will redo the same task forever. Change `- [ ]` to `- [x]` for the task you just completed.
2. Run `uv run pytest -v` one final time to confirm clean state.
3. If all tasks in the current phase are complete, note this in todo.md.
4. **COMMIT AND PUSH the todo.md update** -- The todo.md change MUST be included in your commit or as a separate commit. Without pushing this, the next iteration cannot see your progress.
5. Push with: `git push -u origin claude/youtube-provider-ralph-loop-2vxsm`
