# Exposing Your Local Churns App for Testing

This guide shows you how to share your locally running Churns app with other users for testing.

## 🏗️ Your App Architecture

Your Churns app runs on two services:
- **Frontend**: Next.js on `http://localhost:3000`
- **Backend API**: FastAPI (likely on `http://localhost:8000`)

## 🚀 Method 1: ngrok (Recommended)

**ngrok** creates secure tunnels to your localhost - perfect for sharing with testers.

### Step 1: Start Your Services

```bash
# Terminal 1: Start the backend API
source venv/bin/activate
uvicorn churns.api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start the frontend
cd front_end
npm run dev
```

### Step 2: Expose with ngrok

```bash
# Terminal 3: Expose frontend (port 3000)
ngrok http 3000

# Terminal 4: Expose backend API (port 8000) 
ngrok http 8000
```

### Step 3: Share the URLs

ngrok will give you URLs like:
```
Frontend: https://abc123.ngrok.io → http://localhost:3000
Backend:  https://def456.ngrok.io → http://localhost:8000
```

**Send both URLs to your testers:**
- **Main App**: `https://abc123.ngrok.io`
- **API Docs**: `https://def456.ngrok.io/docs`

### Step 4: Update Frontend to Use Public API

You'll need to temporarily update your frontend to use the public API URL:

```bash
# Create a temporary environment file
echo "NEXT_PUBLIC_API_URL=https://def456.ngrok.io" > front_end/.env.local
```

Then restart your frontend:
```bash
cd front_end
npm run dev
```

## 🌐 Method 2: Localtunnel (Free Alternative)

```bash
# Install localtunnel
npm install -g localtunnel

# Expose frontend
lt --port 3000 --subdomain churns-app

# Expose backend (in another terminal)
lt --port 8000 --subdomain churns-api
```

URLs will be:
- Frontend: `https://churns-app.loca.lt`
- Backend: `https://churns-api.loca.lt`

## 🏠 Method 3: Local Network Sharing

If your testers are on the same WiFi network:

### Step 1: Find Your Local IP
```bash
# On macOS
ipconfig getifaddr en0
# Example output: 192.168.1.100
```

### Step 2: Start Services with Network Binding
```bash
# Backend - bind to all interfaces
uvicorn churns.api.main:app --reload --host 0.0.0.0 --port 8000

# Frontend - expose to network
cd front_end
npm run dev -- --hostname 0.0.0.0
```

### Step 3: Share Local URLs
- Frontend: `http://192.168.1.100:3000`
- Backend: `http://192.168.1.100:8000`

## ☁️ Method 4: Quick Cloud Deployment

### Using Vercel (Frontend)
```bash
cd front_end
npx vercel --prod
```

### Using Railway (Full Stack)
```bash
# Install Railway CLI
npm install -g @railway/cli

# Deploy
railway login
railway init
railway up
```

## 🛠️ Complete Setup Script

Create a script to automate the setup:

```bash
#!/bin/bash
# save as setup_sharing.sh

echo "🚀 Setting up Churns for external testing..."

# Start backend
echo "Starting backend API..."
source venv/bin/activate
uvicorn churns.api.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start ngrok for backend
echo "Creating tunnel for API..."
ngrok http 8000 --log=stdout > ngrok-api.log &
NGROK_API_PID=$!

# Wait and extract API URL
sleep 3
API_URL=$(grep -o 'https://[^"]*\.ngrok\.io' ngrok-api.log | head -1)
echo "API URL: $API_URL"

# Update frontend environment
echo "NEXT_PUBLIC_API_URL=$API_URL" > front_end/.env.local

# Start frontend
echo "Starting frontend..."
cd front_end
npm run dev &
FRONTEND_PID=$!

# Start ngrok for frontend
cd ..
echo "Creating tunnel for frontend..."
ngrok http 3000 --log=stdout > ngrok-frontend.log &
NGROK_FRONTEND_PID=$!

# Wait and extract frontend URL
sleep 3
FRONTEND_URL=$(grep -o 'https://[^"]*\.ngrok\.io' ngrok-frontend.log | head -1)

echo ""
echo "🎉 Your app is now accessible!"
echo "================================"
echo "Frontend: $FRONTEND_URL"
echo "Backend:  $API_URL"
echo "API Docs: $API_URL/docs"
echo ""
echo "Share the Frontend URL with your testers!"
echo ""
echo "To stop all services, press Ctrl+C"

# Keep script running
wait
```

## 📱 Testing Instructions for Your Users

Send this to your testers:

```markdown
# Testing Churns App

Hi! You've been invited to test the Churns app.

## How to Access
🌐 **App URL**: [Your ngrok URL here]
📚 **API Docs**: [Your API ngrok URL]/docs

## How to Test
1. Visit the app URL
2. Upload an image or use the sample images
3. Select a platform (Instagram, Pinterest, etc.)
4. Enter a creative prompt
5. Click "Generate Marketing Content"
6. Wait for the AI to create your marketing materials

## What to Test
- [ ] Image upload works
- [ ] Different platforms generate different layouts
- [ ] Generated content looks good
- [ ] Download functionality works
- [ ] Any errors or broken features

## Report Issues
Please report any issues you find:
- What you were doing when it broke
- What error message you saw
- Screenshots if possible

Thanks for testing! 🙏
```

## 🔒 Security Considerations

**For ngrok:**
- URLs are public but hard to guess
- Add basic auth if needed: `ngrok http 3000 --auth="username:password"`

**For production sharing:**
- Consider using environment variables for API URLs
- Add rate limiting for public APIs
- Monitor usage and costs

## 🐛 Troubleshooting

### Frontend can't reach API
```bash
# Check if API is accessible
curl https://your-api-url.ngrok.io/health

# Update frontend API URL
echo "NEXT_PUBLIC_API_URL=https://your-api-url.ngrok.io" > front_end/.env.local
```

### CORS Issues
Add your ngrok domain to CORS settings in your FastAPI app:

```python
# In your FastAPI app
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://*.ngrok.io", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Ngrok Session Expired
Free ngrok sessions expire after 8 hours. Restart with:
```bash
ngrok http 3000
ngrok http 8000
```

That's it! Your app is now accessible to external testers. 🎉 