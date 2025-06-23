#!/bin/bash

echo "Starting ngrok tunnels in background..."
ngrok start --config=ngrok.yml --all &
NGROK_PID=$!

echo "ngrok PID: $NGROK_PID"
echo "ngrok dashboard: http://localhost:4040"
echo ""

sleep 3

echo "Starting Docker services with logs..."
echo "Press Ctrl+C to stop all services"
echo ""

# Trap Ctrl+C to cleanup
trap "echo 'Stopping services...'; kill $NGROK_PID; docker-compose -f docker-compose.dev.yml down; exit" INT

# Start docker services in foreground (logs visible)
docker-compose -f docker-compose.dev.yml up 