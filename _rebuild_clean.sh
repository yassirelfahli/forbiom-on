#!/bin/bash
set -e
cd "$(dirname "$0")"

# Build a brand-new root commit with no Co-authored-by trailer
export GIT_AUTHOR_NAME="Yasser Elfahli"
export GIT_AUTHOR_EMAIL="131570912+yassirelfahli@users.noreply.github.com"
export GIT_AUTHOR_DATE="2026-10-15T17:53:41-04:00"
export GIT_COMMITTER_NAME="Yasser Elfahli"
export GIT_COMMITTER_EMAIL="131570912+yassirelfahli@users.noreply.github.com"
export GIT_COMMITTER_DATE="2026-10-15T17:53:41-04:00"

git add -A
TREE=$(git write-tree)
NEW=$(printf '%s\n' "Initial public package: FORBIOM-ON report, GAMS, ABM, data and appendix" | git commit-tree "$TREE")
git reset --hard "$NEW"
git branch -M main

echo "Commit: $NEW"
git log -1 --format=fuller
if git log -1 --format=%B | grep -qi 'Co-authored-by'; then
  echo "FAIL: Cursor trailer present"
  exit 1
fi
echo "LOCAL_CLEAN_OK"
