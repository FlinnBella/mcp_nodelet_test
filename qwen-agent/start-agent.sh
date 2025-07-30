#!/bin/bash

# Start health server in background
python health_server.py &
HEALTH_PID=$!

# Function to cleanup on exit
cleanup() {
    echo "Shutting down..."
    kill $HEALTH_PID 2>/dev/null
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Wait for dependencies
echo "Waiting for MCP server..."
while ! nc -z mcp-server 8001; do
    sleep 2
done

OLLAMA_URL=${OLLAMA_URL:-"http://ollama:11434"}
MODEL_NAME=${MODEL_NAME:-"hf.co/unsloth/Qwen3-1.7B-GGUF:Q4_K_M"}

# In qwen-agent/start-agent.sh
echo "Testing connection to existing Ollama..."
while ! curl -s http://ollama:11434/api/tags > /dev/null; do
    echo "Waiting for Ollama..."
    sleep 2
done
echo "Ollama connection successful!"

echo "Dependencies ready, starting agent..."

# Start the main agent
python main.py &
AGENT_PID=$!

# Wait for either process to exit
wait $AGENT_PID
cleanup
