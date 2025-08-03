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

# Test Kaggle endpoint connectivity
if [ "$KAGGLE_URL" != "not-configured" ] && [ "$KAGGLE_URL" != "https://your-ngrok-url.ngrok.io" ]; then
    echo "Testing Kaggle endpoint connectivity..."
    if curl -s --max-time 10 "$KAGGLE_URL/health" > /dev/null; then
        echo "✅ Kaggle endpoint is reachable!"
    else
        echo "⚠️  WARNING: Cannot reach Kaggle endpoint at $KAGGLE_URL"
        echo "   Make sure your Kaggle notebook is running and ngrok tunnel is active"
    fi
fi

echo "Starting Kaggle vLLM client..."


echo "✅ Kaggle client is running!"
echo "   Health endpoint: http://localhost:8000/health"
echo "   Kaggle endpoint: $KAGGLE_URL"
echo "   MCP server: $MCP_SERVER_URL"

echo "Dependencies ready, starting agent..."

# Start the main agent
python main.py &
AGENT_PID=$!

# Wait for either process to exit
wait $AGENT_PID
cleanup
