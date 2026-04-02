#!/usr/bin/env bash
# ============================================================
# Sygen RAG Pipeline Demo (~45 seconds)
# Record with: asciinema rec rag-demo.cast -c "bash scenarios/rag-demo.sh"
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
echo "  Sygen v1.1.9 -- RAG Pipeline Demo"
echo "========================================="
sleep 2

# -- Step 1: Enable RAG in config --
echo ""
echo "# Step 1: Enable local RAG in config.json"
sleep 1
type_cmd "cat config.json | jq '.rag'"
sleep 0.5
cat <<'JSONBLOCK'
{
  "enabled": false,
  "chunk_size": 512,
  "top_k_final": 5,
  "reranker_model": "antoinelouis/colbert-xm"
}
JSONBLOCK
sleep 1.5

type_cmd "jq '.rag.enabled = true' config.json > tmp && mv tmp config.json"
sleep 0.5
echo "RAG enabled."
sleep 1

# -- Step 2: Restart bot --
echo ""
echo "# Step 2: Restart Sygen to activate RAG"
sleep 1
type_cmd "sygen restart"
sleep 0.5
echo "[INFO]  Restarting..."
echo "[INFO]  RAG pipeline registered (lazy init)"
echo "[INFO]  Bot @my_sygen_bot is online."
sleep 1

echo ""
echo "# RAG indexes automatically on first query."
echo "# ColBERT v2 model downloads on first use (~560MB)."
sleep 2

# -- Step 3: Query without RAG context (before) --
echo ""
echo "# Before RAG -- generic answer:"
sleep 1
echo ""
echo "  User:  What is our refund policy?"
sleep 1
echo "  Sygen: I don't have specific information about your"
echo "         refund policy. Could you share more details?"
sleep 2

# -- Step 4: Query with RAG context (after) --
echo ""
echo "# After RAG -- grounded answer with sources:"
sleep 1
echo ""
echo "  User:  What is our refund policy?"
sleep 1
echo "  Sygen: Based on your documentation:"
echo "         Refunds are available within 30 days of purchase."
echo "         Digital products are non-refundable after download."
echo "         Contact support@example.com for exceptions."
echo ""
echo "         Sources: refund-policy.md (§ Returns), faq.md (line 47)"
sleep 3

echo ""
echo "========================================="
echo "  Local RAG. 50+ languages. Zero cloud."
echo "========================================="
sleep 2
