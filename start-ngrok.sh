#!/bin/bash

echo "Starting Docker services..."
docker-compose -f docker-compose.dev.yml up -d

echo "Waiting for services to be ready..."
sleep 10

echo "Starting ngrok tunnels..."
ngrok start --config=ngrok.yml --all &

echo "Setup complete! Check ngrok dashboard at http://localhost:4040"
echo "Your frontend will be available at the ngrok URL displayed above." 