#!/bin/bash

# Build script for Alien4 C++ Extension
# This script compiles the alien4_extension.cpp and installs it to vav/audio/

set -e  # Exit on error

echo "=========================================="
echo "Alien4 C++ Extension Build Script"
echo "=========================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Working directory: $SCRIPT_DIR"
echo ""

# Check if pybind11 is installed
echo "Checking for pybind11..."
PYTHON_BIN="${SCRIPT_DIR}/venv/bin/python3"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi
$PYTHON_BIN -c "import pybind11" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Error: pybind11 not found!"
    echo "Please install it with: pip install pybind11"
    exit 1
fi
echo "✓ pybind11 found"
echo ""

# Create build directory
echo "Creating build directory..."
if [ -d "build" ]; then
    echo "Removing old build directory..."
    rm -rf build
fi
mkdir -p build
echo "✓ Build directory created"
echo ""

# Run CMake
echo "Running CMake configuration..."
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE="$PYTHON_BIN"
if [ $? -ne 0 ]; then
    echo "Error: CMake configuration failed!"
    exit 1
fi
echo "✓ CMake configuration successful"
echo ""

# Build
echo "Building alien4 extension..."
make -j$(sysctl -n hw.ncpu)
if [ $? -ne 0 ]; then
    echo "Error: Build failed!"
    exit 1
fi
echo "✓ Build successful"
echo ""

# Install (copy to vav/audio/)
echo "Installing to vav/audio/..."
make install
if [ $? -ne 0 ]; then
    echo "Error: Installation failed!"
    exit 1
fi
echo "✓ Installation successful"
echo ""

# Verify the .so file exists
cd "$SCRIPT_DIR"
SO_FILE=$(find vav/audio -name "alien4*.so" | head -n 1)
if [ -z "$SO_FILE" ]; then
    echo "Error: alien4.so not found in vav/audio/"
    exit 1
fi

echo "=========================================="
echo "Build completed successfully!"
echo "=========================================="
echo ""
echo "Extension location: $SO_FILE"
echo "File size: $(du -h "$SO_FILE" | cut -f1)"
echo ""

# Test import
echo "Testing Python import..."
cd "$SCRIPT_DIR"
$PYTHON_BIN -c "from vav.audio import alien4; print(f'✓ Import successful! Version: {alien4.__version__}')"
if [ $? -ne 0 ]; then
    echo "Warning: Import test failed, but build was successful"
    echo "You may need to check your Python path"
else
    echo ""
    echo "✓ All tests passed!"
fi

echo ""
echo "You can now use Alien4 in Python:"
echo "  from vav.audio.alien4_wrapper import Alien4EffectChain"
echo ""
