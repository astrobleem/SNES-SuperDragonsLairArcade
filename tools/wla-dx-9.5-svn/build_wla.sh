#!/bin/bash
# Build WLA-DX assembler suite for SNES development

set -e  # Exit on error

echo "Building WLA-DX assembler suite..."
echo "Current directory: $(pwd)"

# Clean previous builds
echo "Cleaning previous builds..."
make clean 2>/dev/null || true

# Build all assemblers and linker
echo "Building WLA-DX..."
make

# Check if binaries were created
echo ""
echo "Build complete! Checking binaries..."
if [ -f "wla-65816" ]; then
    echo "✓ wla-65816 built successfully"
    ./wla-65816 -v || true
else
    echo "✗ wla-65816 not found"
fi

if [ -f "wla-spc700" ]; then
    echo "✓ wla-spc700 built successfully"
else
    echo "✗ wla-spc700 not found"
fi

if [ -f "wlalink/wlalink" ]; then
    echo "✓ wlalink built successfully"
    ./wlalink/wlalink -v || true
else
    echo "✗ wlalink not found"
fi

echo ""
echo "WLA-DX build complete!"
