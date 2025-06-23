#!/bin/bash

echo "Starting Docker services..."
docker-compose -f docker-compose.dev.yml up -d

echo "Waiting for services to be ready..."
sleep 10

echo "Starting ngrok tunnels..."
ngrok start --config=ngrok.yml --all &
NGROK_PID=$!

echo "Setup complete!"
echo "- ngrok dashboard: http://localhost:4040"
echo "- ngrok PID: $NGROK_PID"
echo ""
echo "Log viewing options:"
echo "1. View all logs: docker-compose -f docker-compose.dev.yml logs -f"
echo "2. View API logs: docker-compose -f docker-compose.dev.yml logs -f api"
echo "3. View frontend logs: docker-compose -f docker-compose.dev.yml logs -f frontend"
echo ""
echo "To stop ngrok: kill $NGROK_PID"
echo "To stop all services: docker-compose -f docker-compose.dev.yml down"

# Optional: Automatically show logs
read -p "Show all service logs now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose -f docker-compose.dev.yml logs -f
fi 