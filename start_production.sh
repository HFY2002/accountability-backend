#!/bin/bash
# Production backend starter for Accountability Hub

cd /root/backend

# Activate virtual environment
source backend_env/bin/activate

# Start FastAPI with uvicorn
# Using --host 0.0.0.0 to listen on all network interfaces
# Using --port 8000 for the backend API
# No --reload flag for production stability

echo "Starting Accountability Hub Backend..."
echo "======================================"
echo "API will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"
echo "Press Ctrl+C to stop"
echo "======================================"

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info \
    --access-log > /root/backend/backend.log 2>&1
