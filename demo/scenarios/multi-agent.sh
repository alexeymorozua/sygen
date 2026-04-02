#!/usr/bin/env bash
# ============================================================
# Sygen Multi-Agent Demo (~50 seconds)
# Record with: asciinema rec multi-agent.cast -c "bash scenarios/multi-agent.sh"
# ============================================================

set -e

TYPE_DELAY=0.04

type_cmd() {
    echo ""
    echo -n "$ "
    for (( i=0; i<${#1}; i++ )); do
        echo -n "${1:$i:1}"
        sleep $TYPE_DELAY
    done
    echo ""
    sleep 0.3
}

# -- Intro --
echo "========================================="
echo "  Sygen v1.1.9 -- Multi-Agent Demo"
echo "========================================="
sleep 2

# -- Step 1: Show current agents --
# NOTE: Real CLI output uses Rich tables; simplified here for recording
echo ""
echo "# Step 1: List existing agents"
sleep 1
type_cmd "sygen agents"
sleep 0.5
echo "AGENT        STATUS    MODEL"
echo "main         online    claude-sonnet-4-20250514"
echo ""
echo "1 agent(s) registered."
sleep 2

# -- Step 2: Create a sub-agent --
# NOTE: Real CLI prompts for token, user IDs, etc.; simplified here
echo ""
echo "# Step 2: Create a research sub-agent (interactive wizard)"
sleep 1
type_cmd "sygen agents add researcher"
sleep 0.5
echo "? Telegram bot token: 111111:AAA-BBB..."
sleep 0.4
echo "? Allowed user ID: 123456789"
sleep 0.4
echo "[INFO]  Agent 'researcher' added to agents.json"
echo "[INFO]  Workspace initialized at ~/.sygen/agents/researcher/"
sleep 2

# -- Step 3: Delegate a task --
echo ""
echo "# Step 3: Delegate a task from the main agent"
sleep 1
echo ""
echo "  User (in main chat):"
echo "    Ask researcher to find the top 5 Python web"
echo "    frameworks by GitHub stars in 2025."
sleep 2
echo ""
echo "  Main Agent:"
echo "    Delegating to researcher..."
sleep 1.5

# -- Step 4: Sub-agent works --
echo ""
echo "# The researcher agent works autonomously..."
sleep 1
echo "[researcher]  Searching GitHub API..."
sleep 0.8
echo "[researcher]  Analyzing star counts and trends..."
sleep 0.8
echo "[researcher]  Compiling results..."
sleep 1.5

# -- Step 5: Results delivered --
echo ""
echo "# Step 5: Results arrive in the main chat"
sleep 1
echo ""
echo "  Main Agent:"
echo "    Results from researcher:"
echo ""
echo "    | #  | Framework   | Stars  | Trend     |"
echo "    |----|-------------|--------|-----------|"
echo "    | 1  | FastAPI     | 82.4k  | +18% YoY  |"
echo "    | 2  | Django      | 81.1k  | +5% YoY   |"
echo "    | 3  | Flask       | 69.8k  | +3% YoY   |"
echo "    | 4  | Starlette   | 10.5k  | +8% YoY   |"
echo "    | 5  | Litestar    | 6.2k   | +95% YoY  |"
echo ""
echo "    You can also chat with @sygen_researcher_bot directly"
echo "    to continue this research."
sleep 3

echo ""
echo "========================================="
echo "  Autonomous agents. One Telegram message."
echo "========================================="
sleep 2
