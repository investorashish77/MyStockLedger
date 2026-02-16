#!/bin/bash

echo "================================================"
echo "   EQUITY TRACKER - Quick Setup for macOS"
echo "================================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null
then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python from python.org or use Homebrew:"
    echo "  brew install python3"
    exit 1
fi

echo "Python detected successfully!"
python3 --version
echo ""

# Run the setup agent
echo "Running setup agent..."
echo ""
python3 setup_agent.py

if [ $? -ne 0 ]; then
    echo ""
    echo "Setup failed. Please check the errors above."
    exit 1
fi

echo ""
echo "================================================"
echo "   Setup Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env file to add your API keys"
echo "  2. Run: python3 main.py"
echo ""
