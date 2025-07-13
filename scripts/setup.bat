@echo off
REM WakeDock Windows Setup Script

echo 🐳 Setting up WakeDock development environment...

REM Check dependencies
echo 📋 Checking dependencies...

docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not installed. Please install Docker Desktop first.
    exit /b 1
)

docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Compose is not installed. Please install Docker Compose first.
    exit /b 1
)

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed. Please install Python 3.8+ first.
    exit /b 1
)

node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js is not installed. Please install Node.js 18+ first.
    exit /b 1
)

echo ✅ All dependencies found!

REM Create configuration file
echo ⚙️ Setting up configuration...
if not exist "config\config.yml" (
    copy "config\config.example.yml" "config\config.yml"
    echo ✅ Configuration file created from example
) else (
    echo ℹ️ Configuration file already exists
)

REM Create data directories
echo 📁 Creating data directories...
mkdir data 2>nul
mkdir logs 2>nul
mkdir caddy\data 2>nul
mkdir caddy\config 2>nul

REM Install Python dependencies
echo 🐍 Installing Python dependencies...
pip install -r requirements.txt
echo ✅ Python dependencies installed

REM Install dashboard dependencies
echo 📦 Installing dashboard dependencies...
cd dashboard
npm install
cd ..
echo ✅ Dashboard dependencies installed

REM Build the project
echo 🔨 Building project...
docker-compose build

echo 🎉 Setup complete!
echo.
echo To start WakeDock:
echo   docker-compose up -d
echo.
echo To view logs:
echo   docker-compose logs -f
echo.
echo Dashboard will be available at:
echo   http://admin.localhost (or your configured domain)
