#!/bin/bash

# WakeDock Development Setup Script

set -e

echo "🐳 Setting up WakeDock development environment..."

# Check dependencies
echo "📋 Checking dependencies..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

echo "✅ All dependencies found!"

# Create configuration file
echo "⚙️ Setting up configuration..."
if [ ! -f "config/config.yml" ]; then
    cp config/config.example.yml config/config.yml
    echo "✅ Configuration file created from example"
else
    echo "ℹ️ Configuration file already exists"
fi

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data logs caddy/data caddy/config

# Set up Python virtual environment
echo "🐍 Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

source venv/bin/activate
pip install -r requirements.txt
echo "✅ Python dependencies installed"

# Install dashboard dependencies
echo "📦 Installing dashboard dependencies..."
cd dashboard
npm install
cd ..
echo "✅ Dashboard dependencies installed"

# Build the project
echo "🔨 Building project..."
docker-compose build

echo "🎉 Setup complete!"
echo ""
echo "To start WakeDock:"
echo "  docker-compose up -d"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
echo "Dashboard will be available at:"
echo "  http://admin.localhost (or your configured domain)"
