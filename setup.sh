# 1. Clone/setup your project structure
mkdir crypto-trading-mcp && cd crypto-trading-mcp

# 2. Create all the files shown above

# 3. Build and start
docker-compose up -d

# 4. Monitor startup (takes 1-2 minutes for model download)
docker-compose logs -f

# 5. Test the system
curl http://localhost:8000/health
curl http://localhost:8002  # Website connection port