#!/bin/bash
# Manual build script for WLA-DX with correct library linking order

set -e
cd /mnt/e/gh/SNES-SuperDragonsLairArcade/tools/wla-dx-9.5-svn

echo "Building WLA-65816..."
cp makefiles/makefile.unix.65816 makefile
make clean
# Compile object files
make main.o parse.o include_file.o pass_1.o pass_2.o pass_3.o pass_4.o stack.o listfile.o
# Link with math library AFTER object files
gcc main.o parse.o include_file.o pass_1.o pass_2.o pass_3.o pass_4.o stack.o listfile.o -lm -o wla-65816
strip wla-65816
echo "✓ wla-65816 built"

echo ""
echo "Building WLA-SPC700..."
make clean
cp makefiles/makefile.unix.spc700 makefile
make main.o parse.o include_file.o pass_1.o pass_2.o pass_3.o pass_4.o stack.o listfile.o
gcc main.o parse.o include_file.o pass_1.o pass_2.o pass_3.o pass_4.o stack.o listfile.o -lm -o wla-spc700
strip wla-spc700
echo "✓ wla-spc700 built"

echo ""
echo "Building WLALINK..."
cd wlalink
cp makefile.unix makefile
make clean
make
cd ..
echo "✓ wlalink built"

echo ""
echo "Verifying binaries..."
ls -lh wla-65816 wla-spc700 wlalink/wlalink
echo ""
echo "Testing wla-65816..."
./wla-65816 -v || true
echo ""
echo "All done!"
