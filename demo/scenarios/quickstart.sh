#!/usr/bin/env bash
# ============================================================
# Sygen Quickstart Demo (~60 seconds)
# Record with: asciinema rec quickstart.cast -c "bash scenarios/quickstart.sh"
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
echo "  Sygen v1.1.9 -- Quickstart Demo"
echo "========================================="
sleep 2

# -- Step 1: Install --
echo ""
echo "# Step 1: Install Sygen from PyPI"
sleep 1
type_cmd "pip install sygen"
sleep 0.5
echo "Collecting sygen"
echo "  Downloading sygen-1.1.9-py3-none-any.whl (245 kB)"
sleep 0.8
echo "Installing collected packages: sygen"
sleep 0.5
echo "Successfully installed sygen-1.1.9"
sleep 1.5

# -- Step 2: Initialize config --
echo ""
echo "# Step 2: Create a configuration file"
sleep 1
type_cmd "sygen onboarding"
sleep 0.5
echo "Welcome to Sygen setup!"
echo "Created config.json with defaults."
echo "Edit ~/.sygen/config/config.json to add your Telegram bot token."
sleep 1.5

# -- Step 3: Set bot token in config --
echo ""
echo "# Step 3: Add your Telegram bot token to config (from @BotFather)"
sleep 1
type_cmd "jq '.telegram_token = \"123456:ABC-DEF...\"' ~/.sygen/config/config.json > tmp && mv tmp ~/.sygen/config/config.json"
sleep 1

# -- Step 4: Start the bot --
echo ""
echo "# Step 4: Start Sygen"
sleep 1
type_cmd "sygen"
sleep 0.5
echo "[INFO]  Loading configuration..."
sleep 0.4
echo "[INFO]  Connecting to Telegram API..."
sleep 0.6
echo "[INFO]  Bot @my_sygen_bot is online."
echo "[INFO]  Listening for messages..."
sleep 2

# -- Step 5: Simulate first message --
echo ""
echo "# A user sends a message in Telegram..."
sleep 1.5
echo ""
echo "  User:  What can you do?"
sleep 1
echo ""
echo "  Sygen: I'm your personal AI assistant. I can:"
echo "         - Answer questions with web search & RAG"
echo "         - Run scheduled tasks (cron)"
echo "         - Manage sub-agents for parallel work"
echo "         - Integrate with 3000+ services via MCP"
echo "         - Remember your preferences across sessions"
sleep 3

echo ""
echo "========================================="
echo "  That's it. Self-hosted AI in 60 seconds."
echo "========================================="
sleep 2
