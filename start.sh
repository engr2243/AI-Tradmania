#!/bin/bash
set -e

echo "=== AI-Tradmania Startup ==="

# Check for .env
if [ ! -f .env ]; then
  echo "Creating .env from .env.example..."
  cp .env.example .env
  echo "Please edit .env and add your ANTHROPIC_API_KEY, then re-run."
  exit 1
fi

# Install backend deps
echo "[1/4] Installing Python dependencies..."
pip install -r requirements.txt -q

# Install frontend deps
echo "[2/4] Installing Node dependencies..."
cd frontend && npm install --silent && cd ..

# Start backend
echo "[3/4] Starting backend (port 8000)..."
cd backend && python main.py &
BACKEND_PID=$!
cd ..

# Wait for backend to be ready
echo "Waiting for backend..."
for i in {1..15}; do
  curl -sf http://localhost:8000/health > /dev/null 2>&1 && break
  sleep 1
done

# Start frontend
echo "[4/4] Starting frontend (port 5173)..."
cd frontend && npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "==================================="
echo "  AI-Tradmania is running!"
echo "  Dashboard: http://localhost:5173"
echo "  API:       http://localhost:8000"
echo "  Press Ctrl+C to stop"
echo "==================================="

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
