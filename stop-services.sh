#!/bin/bash

echo "Stopping ngrok tunnels..."
pkill ngrok

echo "Stopping Docker services..."
docker-compose -f docker-compose.dev.yml down

echo "All services stopped!"

# Optional: Clean up any remaining processes
echo "Checking for remaining processes..."
if pgrep ngrok > /dev/null; then
    echo "Warning: Some ngrok processes may still be running"
    echo "Run 'pkill -f ngrok' to force kill"
else
    echo "ngrok processes cleaned up successfully"
fi 