#!/bin/bash
set -e

WLA_DIR=/mnt/e/gh/SNES-SuperDragonsLairArcade/tools/wla-dx-9.5-svn
SRC93=/tmp/wla_dx_9.3

echo "=== Copying assembler source files ==="
for f in main.c main.h parse.c parse.h include_file.c include_file.h \
         pass_1.c pass_1.h pass_2.c pass_2.h pass_3.c pass_3.h \
         pass_4.c pass_4.h stack.c stack.h listfile.c listfile.h defines.h; do
  cp "${SRC93}/${f}" "${WLA_DIR}/${f}"
  echo "  ${f}"
done

echo "=== Copying decode/opcode files ==="
for f in ${SRC93}/decode_*.c ${SRC93}/opcodes_*.c; do
  bn=$(basename "${f}")
  cp "${f}" "${WLA_DIR}/${bn}"
  echo "  ${bn}"
done

echo "=== Copying linker source files ==="
for f in main.c main.h analyze.c analyze.h check.c check.h compute.c compute.h \
         defines.h discard.c discard.h files.c files.h listfile.c listfile.h \
         memory.c memory.h parse.c parse.h write.c write.h; do
  cp "${SRC93}/wlalink/${f}" "${WLA_DIR}/wlalink/${f}"
  echo "  wlalink/${f}"
done

echo "=== Cleaning old binaries and objects ==="
rm -f ${WLA_DIR}/*.o ${WLA_DIR}/wla-65816 ${WLA_DIR}/wla-spc700
rm -f ${WLA_DIR}/wlalink/wlalink ${WLA_DIR}/wlalink/*.o
echo "Done cleaning"

echo "=== Verifying version ==="
grep "wla_version" "${WLA_DIR}/main.c" | head -1
grep "version_string" "${WLA_DIR}/wlalink/main.c" | head -1
echo "=== All done ==="
