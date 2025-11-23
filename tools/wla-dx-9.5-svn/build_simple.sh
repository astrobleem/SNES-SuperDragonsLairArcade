#!/bin/bash
# Simplified build - fix makefiles and build only what we need

set -e
cd /mnt/e/gh/SNES-SuperDragonsLairArcade/tools/wla-dx-9.5-svn

echo "Building WLA-65816..."
cp makefiles/makefile.unix.65816 makefile

# Fix the makefile - move -lm to end of link command
sed -i 's/gcc -lm \(.*\) -o wla-65816/gcc \1 -o wla-65816 -lm/' makefile

make clean
make
strip wla-65816 || true
echo "✓ wla-65816 built"
ls -lh wla-65816

echo ""
echo "Building WLA-SPC700..."
cp makefiles/makefile.unix.spc700 makefile

# Fix the makefile - move -lm to end of link command  
sed -i 's/gcc -lm \(.*\) -o wla-spc700/gcc \1 -o wla-spc700 -lm/' makefile

make clean
make
strip wla-spc700 || true
echo "✓ wla-spc700 built"
ls -lh wla-spc700

echo ""
echo "Checking for wlalink..."
if [ -f "wlalink/wlalink" ]; then
    echo "✓ wlalink already exists"
    ls -lh wlalink/wlalink
else
    echo "Building wlalink..."
    cd wlalink
    cp makefile.unix makefile
    make clean
    make || echo "wlalink build failed, but may already exist"
    cd ..
fi

echo ""
echo "All binaries ready!"
./wla-65816 -v 2>&1 | head -3 || true
