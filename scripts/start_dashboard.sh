#!/bin/bash
# Start SoCal Maker Dashboard
# Access at http://YOUR-IP:8501

cd "$(dirname "$0")/.."

# Activate virtual environment
source venv/bin/activate

# Start Streamlit
echo "Starting SoCal Maker Dashboard..."
echo "Access at: http://$(curl -s -4 ifconfig.me 2>/dev/null || echo 'YOUR-IP'):8501"
echo ""

streamlit run dashboard.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
