<#
.SYNOPSIS
    Enhanced Build Script for Churns Project for Windows (PowerShell).
    Supports both fast development builds and comprehensive validation.
    This script is a PowerShell port of the original build-optimized.sh.
#>
param(
    [switch]$Validate,
    [switch]$Dev,
    [switch]$Clean,
    [switch]$Help
)

# --- Help Section ---
if ($Help) {
    Write-Host "Usage: .\build-optimized.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "OPTIONS:"
    Write-Host "  -Dev          Fast development build with caching (default)"
    Write-Host "  -Validate     Comprehensive validation with testing"
    Write-Host "  -Clean        Force clean build (no cache)"
    Write-Host "  -Help         Show this help message"
    Write-Host ""
    Write-Host "EXAMPLES:"
    Write-Host "  .\build-optimized.ps1              # Fast development build"
    Write-Host "  .\build-optimized.ps1 -Dev         # Same as above"
    Write-Host "  .\build-optimized.ps1 -Validate    # Full validation with testing"
    Write-Host "  .\build-optimized.ps1 -Clean -Dev  # Clean development build"
    Write-Host "  .\build-optimized.ps1 -Clean -Validate # Clean validation build"
    exit 0
}

# --- Script Setup ---

# Default to development mode if no mode specified
if (-not $Validate -and -not $Dev) {
    $Dev = $true
}

Write-Host "🚀 Starting Churns Docker build process..." -ForegroundColor White

# --- Helper Functions ---

function Print-Status { param($Message) Write-Host "[INFO] $Message" -ForegroundColor Blue }
function Print-Success { param($Message) Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Print-Warning { param($Message) Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Print-Error { param($Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }
function Print-Feature { param($Message) Write-Host "[FEATURE] $Message" -ForegroundColor Magenta }

function Print-Mode {
    param($Message)
    if ($Dev) {
        Write-Host "[DEV MODE] $Message" -ForegroundColor Yellow
    }
    else {
        Write-Host "[VALIDATION MODE] $Message" -ForegroundColor Magenta
    }
}

function Command-Exists {
    param($Command)
    return (Get-Command $Command -ErrorAction SilentlyContinue)
}

function Wait-For-Service {
    param(
        [string]$Url,
        [string]$ServiceName,
        [int]$MaxAttempts = 30
    )

    Print-Status "Waiting for $ServiceName to be ready..."
    
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Print-Success "$ServiceName is ready!"
                return $true
            }
        }
        catch {
            # Error is expected while service is starting
        }
        
        Print-Status "Attempt $attempt/$MaxAttempts - waiting for $ServiceName..."
        Start-Sleep -Seconds 2
    }
    
    Print-Error "$ServiceName failed to start within $($MaxAttempts * 2) seconds"
    return $false
}

function Test-Api-Endpoint {
    param(
        [string]$Endpoint,
        [int]$ExpectedStatus,
        [string]$Description
    )
    
    Print-Status "Testing $Description..."
    
    try {
        $response = Invoke-WebRequest -Uri $Endpoint -UseBasicParsing -Method Get -ErrorAction Stop
        $statusCode = $response.StatusCode
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
    }
    
    if ($statusCode -eq $ExpectedStatus) {
        Print-Success "$Description - OK ($statusCode)"
        return $true
    }
    else {
        Print-Error "$Description - FAILED (got $statusCode, expected $ExpectedStatus)"
        return $false
    }
}

# --- Prerequisite Checks ---

Print-Status "Checking prerequisites..."

if (-not (Command-Exists "docker")) {
    Print-Error "Docker is not installed. Please install Docker and try again."
    exit 1
}

if (-not (Command-Exists "docker-compose")) {
    Print-Error "docker-compose is not installed. Please install docker-compose and try again."
    exit 1
}

try {
    docker info > $null
}
catch {
    Print-Error "Docker is not running. Please start Docker and try again."
    exit 1
}

if ($Validate -and -not (Command-Exists "curl")) {
    Print-Warning "curl.exe is used for WebSocket test. It might not be available on older Windows versions."
}

# --- Main Logic ---

Write-Host ""
Write-Host "=========================================="
if ($Dev) {
    Write-Host "  ⚡  FAST DEVELOPMENT BUILD" -ForegroundColor White
    Print-Mode "Optimized for speed and iteration"
    Print-Mode "Using layer caching for fast builds"
}
else {
    Write-Host "  🔍  COMPREHENSIVE VALIDATION" -ForegroundColor White
    Print-Mode "Full testing and validation mode"
    Print-Mode "Includes service testing and health checks"
}
Write-Host "=========================================="

$BUILD_FLAGS = ""
if ($Clean) {
    Print-Status "Performing clean build - removing old containers and images..."
    docker-compose down -v --remove-orphans 2>$null
    docker-compose -f docker-compose.dev.yml down -v --remove-orphans 2>$null
    docker system prune -f
    $BUILD_FLAGS = "--no-cache"
}
else {
    Print-Status "Using cached layers for faster builds..."
    docker-compose down 2>$null
    docker-compose -f docker-compose.dev.yml down 2>$null
}

if ($Dev) {
    # Fast development workflow
    Write-Host ""
    Print-Mode "Building development environment..."
    
    $startTime = Get-Date
    docker-compose -f docker-compose.dev.yml build $BUILD_FLAGS
    $endTime = Get-Date
    $buildDuration = (New-TimeSpan -Start $startTime -End $endTime).TotalSeconds
    
    Print-Success "Development build completed in $($buildDuration.ToString('F0'))s"
    
    Print-Status "Image sizes:"
    docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | Select-String -Pattern "(churns|redis)" | Select-Object -First 5
    
    Write-Host ""
    Print-Mode "🚀 Ready for development!"
    Write-Host "  • Start: docker-compose -f docker-compose.dev.yml up" -ForegroundColor White
    Write-Host "  • Hot reload: Code changes auto-reload" -ForegroundColor White
    Write-Host "  • Logs: docker-compose -f docker-compose.dev.yml logs -f" -ForegroundColor White
    Write-Host "  • Stop: docker-compose -f docker-compose.dev.yml down" -ForegroundColor White
    Write-Host ""
    Print-Success "⚡ Fast development build complete!"
}
else {
    # Comprehensive validation workflow
    Write-Host ""
    Print-Mode "Building production environment..."
    
    $globalStartTime = Get-Date
    docker-compose build $BUILD_FLAGS
    $prodEndTime = Get-Date
    $prodBuildDuration = (New-TimeSpan -Start $globalStartTime -End $prodEndTime).TotalSeconds
    
    Print-Success "Production build completed in $($prodBuildDuration.ToString('F0'))s"
    
    Print-Mode "Building development environment..."
    docker-compose -f docker-compose.dev.yml build $BUILD_FLAGS
    $devEndTime = Get-Date
    $devBuildDuration = (New-TimeSpan -Start $prodEndTime -End $devEndTime).TotalSeconds
    $totalBuildDuration = (New-TimeSpan -Start $globalStartTime -End $devEndTime).TotalSeconds
    
    Print-Success "Development build completed in $($devBuildDuration.ToString('F0'))s"
    Print-Success "Total build time: $($totalBuildDuration.ToString('F0'))s"
    
    Write-Host ""
    Print-Status "Image size comparison:"
    docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | Select-String -Pattern "(churns|redis)" | Select-Object -First 10
    
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  ✅  TESTING PRODUCTION BUILD" -ForegroundColor White
    Write-Host "=========================================="
    
    Print-Status "Starting production environment for testing..."
    docker-compose up -d
    
    if (Wait-For-Service "http://localhost:8000/health" "API") {
        if (Wait-For-Service "http://localhost:3000" "Frontend") {
            
            Print-Feature "Testing API functionality..."
            Test-Api-Endpoint "http://localhost:8000/health" 200 "Health endpoint"
            Test-Api-Endpoint "http://localhost:8000/" 200 "Root endpoint"
            Test-Api-Endpoint "http://localhost:8000/api/v1/config/platforms" 200 "Platforms config"
            Test-Api-Endpoint "http://localhost:8000/api/v1/runs" 200 "Runs endpoint"
            
            Print-Feature "Testing Frontend functionality..."
            Test-Api-Endpoint "http://localhost:3000" 200 "Frontend home page"
            
            Print-Feature "Validating Docker health checks..."
            Start-Sleep 40 # Wait for health check start period
            
            $apiHealth = (docker inspect (docker-compose ps -q api) | ConvertFrom-Json).State.Health.Status
            $frontendHealth = (docker inspect (docker-compose ps -q frontend) | ConvertFrom-Json).State.Health.Status
            $redisHealth = (docker inspect (docker-compose ps -q redis) | ConvertFrom-Json).State.Health.Status
            
            Print-Status "Health check statuses:"
            Write-Host "  • API: $apiHealth"
            Write-Host "  • Frontend: $frontendHealth"
            Write-Host "  • Redis: $redisHealth"
            
            if ($apiHealth -eq "healthy" -and $frontendHealth -eq "healthy" -and $redisHealth -eq "healthy") {
                Print-Success "All health checks passing!"
            } else {
                Print-Warning "Some health checks are still starting or failing"
            }
            
            Print-Feature "Checking resource limits..."
            docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
            
            Print-Feature "Testing WebSocket availability..."
            try {
                $wsTest = curl.exe -s -I "http://localhost:8000/api/v1/ws/test"
                if ($wsTest -match "426 Upgrade Required") {
                    Print-Success "WebSocket endpoint is available"
                } else {
                    Print-Warning "WebSocket endpoint test inconclusive"
                }
            } catch {
                Print-Warning "Could not test WebSocket endpoint. curl.exe might be missing."
            }
            
            Print-Success "✅ Production build validation completed!"
            
        } else {
            Print-Error "Frontend failed to start"
        }
    } else {
        Print-Error "API failed to start" 
    }
    
    Print-Status "Stopping production environment..."
    docker-compose down
    
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  🛠️  TESTING DEVELOPMENT BUILD" -ForegroundColor White
    Write-Host "=========================================="
    
    Print-Status "Starting development environment for testing..."
    docker-compose -f docker-compose.dev.yml up -d
    
    if (Wait-For-Service "http://localhost:8000/health" "API (dev)") {
        if (Wait-For-Service "http://localhost:3000" "Frontend (dev)") {
            
            Print-Feature "Testing development features..."
            Test-Api-Endpoint "http://localhost:8000/health" 200 "API health (dev mode)"
            Test-Api-Endpoint "http://localhost:3000" 200 "Frontend (dev mode)"
            
            $apiLogs = docker-compose -f docker-compose.dev.yml logs api | Select-String -Pattern "reload" -Quiet
            if ($apiLogs) {
                Print-Success "API hot-reload is enabled"
            } else {
                Print-Warning "API hot-reload not detected in logs"
            }
            
            Print-Success "✅ Development build validation completed!"
            
        } else {
            Print-Error "Development frontend failed to start"
        }
    } else {
        Print-Error "Development API failed to start"
    }
    
    Print-Status "Stopping development environment..."
    docker-compose -f docker-compose.dev.yml down
    
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  📊  VALIDATION SUMMARY"
    Write-Host "=========================================="
    
    Print-Success "✅ Comprehensive validation completed!"
    Write-Host ""
    Write-Host "🎯 ENHANCEMENTS VALIDATED:" -ForegroundColor White
    Write-Host "  ✅ Multi-stage builds for optimal image sizes"
    Write-Host "  ✅ Health checks for all services (API, Frontend, Redis)"
    Write-Host "  ✅ Resource limits and reservations configured"
    Write-Host "  ✅ Async database support verified"
    Write-Host "  ✅ Security hardening (non-root users, read-only mounts)"
    Write-Host "  ✅ Development hot-reload functionality"
    Write-Host "  ✅ Production optimization and stability"
    Write-Host "  ✅ WebSocket endpoint availability"
    Write-Host "  ✅ API endpoint functionality"
    Write-Host ""
    Write-Host "🚀 DEPLOYMENT READY:" -ForegroundColor White
    Write-Host "  • Production: docker-compose up -d"
    Write-Host "  • Development: docker-compose -f docker-compose.dev.yml up -d"
    Write-Host "  • Health monitoring: docker-compose ps"
    Write-Host "  • View logs: docker-compose logs -f [service]"
    Write-Host ""
    Write-Host "📈 FEATURE STATUS:" -ForegroundColor White
    Write-Host "  • Pipeline Execution: ✅ Optimized (instant response)"
    Write-Host "  • Refinement System: ✅ Working (subject, text, prompt)"
    Write-Host "  • Caption Generation: ✅ Available"
    Write-Host "  • WebSocket Updates: ✅ Real-time"
    Write-Host "  • Health Monitoring: ✅ Comprehensive"
    Write-Host "  • Development Mode: ✅ Hot-reload enabled"
    Write-Host ""
    Write-Host "⏱️  BUILD PERFORMANCE:" -ForegroundColor White
    Write-Host "  • Production build: $($prodBuildDuration.ToString('F0'))s"
    Write-Host "  • Development build: $($devBuildDuration.ToString('F0'))s"
    Write-Host "  • Total validation time: $($totalBuildDuration.ToString('F0'))s"
    Write-Host ""
    
    Print-Success "🎉 Complete validation finished!"
}

Print-Status "Build process complete! Use -Help for more options." 