#!/bin/bash

# go to project root (one level up from this script)
dn="$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.."
cd "$dn" || exit 1

# derive session name from script filename (without “.sh”)
script="$(basename "${BASH_SOURCE[0]}" .sh)"
SESSION="command_${script}_tmux_session"

# your three long‑running commands
COMMAND_1="cd frontend && pnpm run dev"
COMMAND_2="./__inenv python backend/app.py"
COMMAND_3="multitail -cT ansi backend/logs/debug.txt"

# clean logs
rm -f backend/logs/debug.txt
touch backend/logs/debug.txt

# cleanup: kill the tmux session (ignore errors if it's already gone)
cleanup() {
  tmux kill-session -t "$SESSION" 2>/dev/null || true
}
trap cleanup EXIT

# tear down any old session by this name
if tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux kill-session -t "$SESSION"
fi

# start a fresh, detached session (one blank pane)
tmux new-session -d -s "$SESSION"

# Pane 0 (left column): run COMMAND_1


# split pane 0 to create Pane 1 (center column), then run COMMAND_2
tmux split-window -h -t "${SESSION}:0.0"

# split pane 0 again to create Pane 2 (right column), then run COMMAND_3
tmux split-window -h -t "${SESSION}:0.0"



# even‑out all three columns
tmux select-layout -t "$SESSION" even-horizontal

tmux send-keys -t "${SESSION}:0.0" "$COMMAND_1" C-m
tmux send-keys -t "${SESSION}:0.1" "$COMMAND_2" C-m
tmux send-keys -t "${SESSION}:0.2" "$COMMAND_3" C-m


# attach you into the session
tmux attach -t "$SESSION"
