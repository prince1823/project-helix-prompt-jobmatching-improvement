#!/bin/bash

# Function to handle shutdown gracefully
cleanup() {
    echo "Shutting down services..."
    kill $(jobs -p) 2>/dev/null
    wait
    echo "All services stopped."
    exit 0
}

# Set up signal handlers for graceful shutdown
trap cleanup SIGTERM SIGINT

echo "Starting background services..."

# Start each service in the background
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 --access-log --log-level info --timeout-keep-alive 5 &
echo "Started fastapi main.py (PID: $!)"

uv run consume_user_events.py &
echo "Started consume_user_events.py (PID: $!)"

uv run consume_admin_events.py &
echo "Started consume_admin_events.py (PID: $!)"

uv run consume_multiline_events.py &
echo "Started consume_multiline_events.py (PID: $!)"

uv run consume_schedule_send.py &
echo "Started consume_schedule_send.py (PID: $!)"

echo "All services started. Press Ctrl+C to stop all services."

# Wait for all background jobs to finish (or for a signal)
wait

echo "Script finished."
