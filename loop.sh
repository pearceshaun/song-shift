#!/bin/bash
# loop.sh — Ralph Wiggum harness for autonomous Claude Code sessions
# Usage: ./loop.sh <prompt-path> [max-iterations]
#   ./loop.sh tasks/loops/playlist-migration/prompt.md       # default 30 iterations
#   ./loop.sh tasks/loops/playlist-migration/prompt.md 15    # 15 iterations

PROMPT_FILE=${1:?"Usage: ./loop.sh <prompt-path> [max-iterations]"}
MAX_ITERATIONS=${2:-30}
ITERATION=0

if [ ! -f "$PROMPT_FILE" ]; then
  echo "Error: prompt file not found: $PROMPT_FILE"
  exit 1
fi

echo "Starting Ralph loop"
echo "  Prompt: $PROMPT_FILE"
echo "  Max iterations: $MAX_ITERATIONS"
echo "Press Ctrl+C to stop at any time"
echo "---"

while [ "$ITERATION" -lt "$MAX_ITERATIONS" ]; do
  ITERATION=$((ITERATION + 1))
  echo ""
  echo "=== ITERATION $ITERATION / $MAX_ITERATIONS ==="
  echo "Started at: $(date)"
  echo "---"

  claude --dangerously-skip-permissions -p "$(cat "$PROMPT_FILE")"

  EXIT_CODE=$?
  echo "---"
  echo "Iteration $ITERATION finished at: $(date) (exit code: $EXIT_CODE)"

  if [ $EXIT_CODE -ne 0 ]; then
    echo "Claude exited with error code $EXIT_CODE. Pausing."
    echo "Review the state, then re-run to continue."
    exit $EXIT_CODE
  fi
done

echo ""
echo "=== REACHED MAX ITERATIONS ($MAX_ITERATIONS) ==="
echo "Review progress in the todo.md for your loop."
