#!/bin/bash
# Script to clean up git tracking of build artifacts

echo "Removing build artifacts from git tracking..."
echo "=============================================="

# Remove data/chapters from git tracking (CRITICAL - auto-generated)
echo "Removing data/chapters/ from git..."
git rm -r --cached data/chapters/ 2>/dev/null || echo "  (not tracked)"

# Remove build directory if tracked
echo "Removing build/ from git..."
git rm -r --cached build/ 2>/dev/null || echo "  (not tracked)"

# Remove WLA-DX object files if tracked (but keep binaries!)
echo "Removing WLA-DX object files from git..."
git rm --cached tools/wla-dx-9.5-svn/*.o 2>/dev/null || echo "  (not tracked)"
git rm --cached tools/wla-dx-9.5-svn/wlalink/*.o 2>/dev/null || echo "  (not tracked)"
echo "  (keeping WLA-DX binaries: wla-65816, wla-spc700, wlalink)"

# Remove Python cache if tracked
echo "Removing Python cache from git..."
find . -name '__pycache__' -type d | while read dir; do
    git rm -r --cached "$dir" 2>/dev/null || true
done

find . -name '*.pyc' -type f | while read file; do
    git rm --cached "$file" 2>/dev/null || true
done

echo ""
echo "=============================================="
echo "Done! Now commit the updated .gitignore:"
echo ""
echo "  git add .gitignore Makefile"
echo "  git commit -m 'Update .gitignore and enhance make clean'"
echo ""
echo "Note: The .gitignore has been updated to prevent"
echo "these files from being tracked in the future."
