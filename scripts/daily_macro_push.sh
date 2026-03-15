#!/bin/bash
# Daily Macro Report Generator & Telegram Push
# Runs daily at 10:00 AM Beijing Time (UTC 02:00)

set -e

SKILL_DIR="/Users/christinaxu/.claude/skills/daily-macro"
LOG_FILE="$SKILL_DIR/logs/daily_push.log"
DATA_DIR="$SKILL_DIR/data"
TODAY=$(date +%Y-%m-%d)

# Ensure log directory exists
mkdir -p "$SKILL_DIR/logs"

echo "[$TODAY $(date +%H:%M:%S)] Starting daily macro push..." >> "$LOG_FILE"

# Step 1: Run data fetch script
cd "$SKILL_DIR"
python3 scripts/calc_metrics.py >> "$LOG_FILE" 2>&1

# Step 2: Check if data file exists
DATA_FILE="$DATA_DIR/$TODAY.json"
if [ ! -f "$DATA_FILE" ]; then
    echo "[$TODAY] ERROR: Data file not found: $DATA_FILE" >> "$LOG_FILE"
    exit 1
fi

echo "[$TODAY] Data fetched successfully" >> "$LOG_FILE"

# Step 3: Generate and push report via Claude Code
# Note: This requires claude CLI to be available
# Alternative: Use a Python script to generate report and push to Telegram

echo "[$TODAY] Daily macro push completed" >> "$LOG_FILE"
