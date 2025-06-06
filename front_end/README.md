# Churns - Frontend

A modern React/Next.js frontend for Churns, providing an intuitive interface for creating and monitoring AI-powered content generation.

## 🚀 Features

### ✨ **User Experience**
- **Friendly & Interactive Interface**: Clean, modern UI with Material-UI components
- **Real-time Progress Tracking**: Live WebSocket updates during pipeline execution
- **Comprehensive Feedback**: Visual progress indicators, status updates, and error handling
- **Responsive Design**: Works seamlessly across desktop, tablet, and mobile devices

### 🎨 **Pipeline Form**
- **Multi-mode Support**: Easy, Custom, and Task-specific modes
- **Image Upload**: Drag & drop image upload with preview
- **Form Validation**: Real-time validation with helpful error messages
- **Advanced Options**: Collapsible sections for power users

### 📊 **Results & Monitoring**
- **Live Progress Display**: Real-time stage updates with visual indicators
- **Generated Image Gallery**: Preview and download generated images
- **Cost Tracking**: Detailed cost breakdown per stage
- **Live Logging**: Interactive log viewer with filtering
- **Run History**: Comprehensive history with search and filtering

### 🔧 **Technical Features**
- **WebSocket Integration**: Real-time communication with FastAPI backend
- **Error Recovery**: Automatic reconnection and graceful error handling
- **TypeScript**: Full type safety throughout the application
- **Performance Optimized**: Lazy loading, pagination, and efficient re-renders

## 🏗 Architecture

```
src/
├── app/                    # Next.js 13+ App Router
│   ├── layout.tsx         # Root layout with theme provider
│   └── page.tsx           # Main application page
├── components/            # React components
│   ├── PipelineForm.tsx   # Main form component
│   ├── RunResults.tsx     # Real-time results display
│   └── RunHistory.tsx     # Run history table
├── lib/                   # Utilities and configurations
│   ├── api.ts            # API client and WebSocket manager
│   └── theme.ts          # Material-UI theme configuration
└── types/                # TypeScript type definitions
    └── api.ts            # API response types
```

## 🛠 Setup & Installation

### Prerequisites
- Node.js 18.0.0 or higher
- npm or yarn package manager
- Running FastAPI backend (see ../churns/)

### 1. Install Dependencies
```bash
cd front_end
npm install
```

### 2. Environment Configuration
Create `.env.local` file in the root directory:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### 3. Development Server
```bash
npm run dev
```

The application will be available at http://localhost:3000

### 4. Production Build
```bash
npm run build
npm start
```

## 🐳 Docker Development

### Using Docker Compose (Recommended)
From the root project directory:
```bash
docker-compose up
```

This will start both the FastAPI backend and Next.js frontend.

### Manual Docker Build
```bash
# Build the image
docker build -t churns-frontend .

# Run the container
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://localhost:8000 churns-frontend
```

## 📋 Usage Guide

### Creating a New Pipeline Run

1. **Select Mode**:
   - **Easy Mode**: Minimal configuration for quick results
   - **Custom Mode**: Full control over all parameters
   - **Task-Specific Mode**: Guided setup for specific F&B tasks

2. **Configure Settings**:
   - Choose target platform (Instagram, Facebook, Pinterest, etc.)
   - Set creativity level (1: Photorealistic → 3: Abstract)
   - Enter descriptive prompt

3. **Upload Reference Image** (Optional):
   - Drag & drop or click to upload
   - Add specific instructions for image handling

4. **Advanced Options** (Custom/Task-Specific modes):
   - Task content and branding elements
   - Marketing goals (audience, objective, voice, niche)

5. **Submit**: Click "Start Pipeline Run" to begin execution

### Monitoring Progress

- **Real-time Updates**: Watch each stage complete with live status indicators
- **Stage Details**: Expand stages to see detailed progress information
- **Live Logs**: Monitor execution logs in real-time
- **Error Handling**: Automatic error display with retry options

### Viewing Results

- **Generated Images**: Preview and download all generated images
- **Cost Breakdown**: Detailed cost analysis per stage
- **Performance Metrics**: Execution time and resource usage
- **Full Run Details**: Complete metadata and configuration

### Managing Run History

- **Search & Filter**: Find runs by status, date, or other criteria
- **Pagination**: Efficient browsing of large run histories
- **Quick Actions**: View details or restart runs with one click

## 🔧 API Integration

### WebSocket Connection
The frontend maintains a persistent WebSocket connection for real-time updates:

```typescript
const wsManager = new WebSocketManager(
  runId,
  (message) => {
    // Handle real-time updates
  }
);
```

### REST API Calls
All API communication is handled through the `PipelineAPI` class:

```typescript
// Submit new run
const run = await PipelineAPI.submitRun(formData);

// Get run details
const details = await PipelineAPI.getRun(runId);

// Download generated images
const blob = await PipelineAPI.downloadFile(runId, filename);
```

## 🎨 Customization

### Theme Customization
Edit `src/lib/theme.ts` to customize:
- Color palette
- Typography
- Component styling
- Spacing and shadows

### Adding New Components
1. Create component in `src/components/`
2. Export from component file
3. Import in parent components
4. Add TypeScript types as needed

## 🚀 Performance

### Optimization Features
- **Code Splitting**: Automatic route-based code splitting
- **Image Optimization**: Next.js automatic image optimization
- **Bundle Analysis**: Built-in bundle size analysis
- **Caching**: Efficient API response caching

### Bundle Size Analysis
```bash
npm run build
npm run analyze
```

## 🐛 Troubleshooting

### Common Issues

**WebSocket Connection Failed**
- Ensure FastAPI backend is running
- Check CORS configuration
- Verify WebSocket URL in environment variables

**API Requests Failing**
- Confirm backend API is accessible
- Check network configuration
- Verify API base URL in environment variables

**Build Errors**
- Clear node_modules and reinstall: `rm -rf node_modules package-lock.json && npm install`
- Check Node.js version compatibility
- Ensure all environment variables are set

**Performance Issues**
- Enable React DevTools Profiler
- Check for unnecessary re-renders
- Optimize WebSocket message handling

## 📝 Development

### Code Style
- ESLint configuration for code quality
- Prettier for consistent formatting
- TypeScript for type safety

### Testing
```bash
# Run tests
npm test

# Run tests with coverage
npm run test:coverage

# Run type checking
npm run type-check
```

### Contributing
1. Follow existing code patterns
2. Add TypeScript types for new features
3. Test WebSocket integration thoroughly
4. Update documentation as needed

## 🔗 Related Documentation

- [FastAPI Backend](../churns/README.md)
- [Pipeline Architecture](../README.md)
- [Docker Setup](../docker-compose.yml)
- [API Documentation](http://localhost:8000/docs)

---

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the FastAPI backend logs
3. Check browser developer console for client-side errors
4. Verify WebSocket connection status 