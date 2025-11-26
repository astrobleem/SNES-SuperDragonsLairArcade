#!/bin/bash
# Start build in background with logging

cd /mnt/e/gh/SNES-SuperDragonsLairArcade

# Clean first
make clean

# Start build with superfamiconv in background
# Use disown to prevent process from being killed when script exits
USE_SUPERFAMICONV=1 make > build.log 2>&1 &
BUILD_PID=$!
disown $BUILD_PID

echo $BUILD_PID > build.pid
echo "Build started with PID: $BUILD_PID"
echo "Monitor progress with: tail -f build.log"
echo "Check status with: ps -p $BUILD_PID"
