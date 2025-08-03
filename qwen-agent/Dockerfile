FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY qwen-agent/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY qwen-agent/ .

# Create logs directory
RUN mkdir -p /app/logs

# Create simple health endpoint
RUN echo 'from http.server import HTTPServer, BaseHTTPRequestHandler\nimport json\nclass HealthHandler(BaseHTTPRequestHandler):\n    def do_GET(self):\n        if self.path == "/health":\n            self.send_response(200)\n            self.send_header("Content-type", "application/json")\n            self.end_headers()\n            self.wfile.write(json.dumps({"status": "healthy"}).encode())\n        else:\n            self.send_response(404)\n            self.end_headers()\n\nif __name__ == "__main__":\n    server = HTTPServer(("0.0.0.0", 8000), HealthHandler)\n    server.serve_forever()' > health_server.py

# Expose health port and websocket port
EXPOSE 8000 8003

# Create startup script
COPY qwen-agent/start-agent.sh .
RUN chmod +x start-agent.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["./start-agent.sh"]