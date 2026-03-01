#!/bin/bash
# loop-monitor.sh — Live dashboard for Ralph Wiggum loop progress
# Usage: ./loop-monitor.sh [todo-path] [refresh-seconds]
#   ./loop-monitor.sh tasks/loops/playlist-migration/todo.md       # default 5s refresh
#   ./loop-monitor.sh tasks/loops/playlist-migration/todo.md 3     # custom refresh

TODO_FILE=${1:?"Usage: ./loop-monitor.sh <todo-path> [refresh-seconds]"}
REFRESH=${2:-5}

# Colours
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'
GREEN='\033[32m'
RED='\033[31m'
YELLOW='\033[33m'
CYAN='\033[36m'
MAGENTA='\033[35m'
BLUE='\033[34m'
WHITE='\033[97m'
BG_GREEN='\033[42m'
BG_BLUE='\033[44m'

draw_progress_bar() {
  local done=$1 total=$2 width=40
  local pct=$((done * 100 / total))
  local filled=$((done * width / total))
  local empty=$((width - filled))
  printf "${GREEN}"
  printf "  ["
  for ((i=0; i<filled; i++)); do printf "█"; done
  printf "${DIM}"
  for ((i=0; i<empty; i++)); do printf "░"; done
  printf "${RESET}${GREEN}] ${BOLD}%d/%d${RESET} ${DIM}(%d%%)${RESET}\n" "$done" "$total" "$pct"
}

while true; do
  clear

  # Header
  printf "${BG_BLUE}${WHITE}${BOLD}%-60s${RESET}\n" "  🔄 RALPH WIGGUM LOOP MONITOR"
  printf "${DIM}  %s • refreshing every %ds${RESET}\n" "$(date '+%H:%M:%S')" "$REFRESH"
  echo ""

  # ── Progress ──
  if [ -f "$TODO_FILE" ]; then
    DONE=$(grep -cE '^\- \[x\]' "$TODO_FILE" 2>/dev/null || echo 0)
    TOTAL=$(grep -cE '^\- \[[ x]\]' "$TODO_FILE" 2>/dev/null || echo 0)
    REMAINING=$((TOTAL - DONE))

    printf "${BOLD}${CYAN}  ── PROGRESS ──${RESET}\n"
    draw_progress_bar "$DONE" "$TOTAL"
    echo ""

    # Current task (first unchecked)
    CURRENT=$(grep -m1 -E '^\- \[ \]' "$TODO_FILE" 2>/dev/null | sed 's/^- \[ \] //')
    if [ -n "$CURRENT" ]; then
      printf "${BOLD}${YELLOW}  ▶ CURRENT TASK${RESET}\n"
      if [ ${#CURRENT} -gt 120 ]; then
        printf "  ${WHITE}%s...${RESET}\n" "${CURRENT:0:120}"
      else
        printf "  ${WHITE}%s${RESET}\n" "$CURRENT"
      fi
    else
      printf "${BG_GREEN}${WHITE}${BOLD}  ✅ ALL TASKS COMPLETE${RESET}\n"
    fi
    echo ""

    # Recently completed (last 3)
    COMPLETED=$(grep -E '^\- \[x\]' "$TODO_FILE" | tail -3 | sed 's/^- \[x\] //')
    if [ -n "$COMPLETED" ]; then
      printf "${BOLD}${GREEN}  ── RECENTLY COMPLETED ──${RESET}\n"
      while IFS= read -r line; do
        SHORT="${line:0:100}"
        printf "  ${GREEN}✓${RESET} ${DIM}%s${RESET}\n" "$SHORT"
      done <<< "$COMPLETED"
      echo ""
    fi
  else
    printf "${RED}  ⚠ Todo file not found: %s${RESET}\n\n" "$TODO_FILE"
  fi

  # ── Git Activity ──
  printf "${BOLD}${MAGENTA}  ── GIT LOG (last 8) ──${RESET}\n"
  BRANCH=$(git branch --show-current 2>/dev/null)
  printf "  ${DIM}branch:${RESET} ${CYAN}%s${RESET}\n" "$BRANCH"
  echo ""
  git log --oneline -8 --color=always 2>/dev/null | while IFS= read -r line; do
    printf "  %s\n" "$line"
  done
  echo ""

  # ── Uncommitted Changes ──
  UNSTAGED=$(git status --short 2>/dev/null)
  if [ -n "$UNSTAGED" ]; then
    printf "${BOLD}${RED}  ── UNCOMMITTED CHANGES ──${RESET}\n"
    echo "$UNSTAGED" | head -8 | while IFS= read -r line; do
      STATUS="${line:0:2}"
      FILE="${line:3}"
      case "$STATUS" in
        "??") printf "  ${YELLOW}+ new${RESET}     %s\n" "$FILE" ;;
        " M") printf "  ${RED}~ mod${RESET}     %s\n" "$FILE" ;;
        "M ")  printf "  ${GREEN}✓ staged${RESET}  %s\n" "$FILE" ;;
        "A ")  printf "  ${GREEN}✓ added${RESET}   %s\n" "$FILE" ;;
        *)     printf "  ${DIM}%s${RESET}  %s\n" "$STATUS" "$FILE" ;;
      esac
    done
    EXTRA=$(echo "$UNSTAGED" | wc -l | tr -d ' ')
    if [ "$EXTRA" -gt 8 ]; then
      printf "  ${DIM}... and %d more${RESET}\n" "$((EXTRA - 8))"
    fi
  else
    printf "${DIM}  No uncommitted changes${RESET}\n"
  fi
  echo ""

  # Footer
  printf "${DIM}  Press Ctrl+C to stop${RESET}\n"

  sleep "$REFRESH"
done
