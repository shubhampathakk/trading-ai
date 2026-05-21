#!/bin/zsh

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${PURPLE}===================================================="
echo -e "       STARTING KITE TERMINAL TRADING DASHBOARD"
echo -e "====================================================${NC}\n"

# Check if another instance is already running on port 5001
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${BLUE}[Proxy] REST API Proxy is already running on port 5001.${NC}"
else
    echo -e "${BLUE}[Proxy] Starting REST API Proxy server in background...${NC}"
    python3 mcp_helpers/mcp_server_proxy.py &
    PROXY_PID=$!
    # Wait a moment for it to initialize
    sleep 3
fi

echo -e "${GREEN}[Frontend] Opening Kite Terminal Dashboard in your browser...${NC}"
open dashboard/index.html

echo -e "\n${GREEN}🚀 Dashboard is live!${NC}"
echo -e "• Local API Endpoint: ${BLUE}http://localhost:5001/${NC}"
echo -e "• Frontend Directory: ${BLUE}dashboard/index.html${NC}"
echo -e "• Subprocess Logs & Output are active. Press ${PURPLE}Ctrl+C${NC} in this shell to stop the proxy server."

# Trap Ctrl+C to shut down proxy cleanly if we spawned it
if [ ! -z "$PROXY_PID" ]; then
    trap "echo -e '\n${PURPLE}[Shutdown] Terminating Proxy Server...${NC}'; kill $PROXY_PID; exit" INT
    wait $PROXY_PID
else
    echo -e "${BLUE}[System] Proxy was already active. Keeping this shell open for logs. Press Ctrl+C to exit.${NC}"
    # Keep shell open
    while true; do sleep 1; done
fi
