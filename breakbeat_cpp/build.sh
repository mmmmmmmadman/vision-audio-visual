#!/bin/bash

# Breakbeat Engine Build Script

set -e

echo "Building Breakbeat Engine..."

# Activate venv
cd ..
source venv/bin/activate
cd breakbeat_cpp

# Create build directory
mkdir -p build
cd build

# Configure with venv Python
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=../.. \
    -DPython_EXECUTABLE=$(which python3)

# Build
make -j$(sysctl -n hw.ncpu)

# Install to parent directory (VAV root)
make install

echo ""
echo "Build complete!"
echo "Python module installed to: $(pwd)/../.."
