#!/usr/bin/env bash
#
# publish.sh — Publish the archive to GitHub as a SINGLE clean commit, no LFS,
# no history. This is destructive on the remote BY DESIGN (the owner never wants
# history on Hub). A full local backup lives at ../_BACKUP_quantum_repo_*/.
#
# Usage:
#   bash tools/publish.sh             # prepare single commit locally, then PROMPT before force-push
#   bash tools/publish.sh --push      # prepare AND force-push without prompting
#   bash tools/publish.sh --local     # only rebuild the single commit, never push
#
set -euo pipefail
cd "$(dirname "$0")/.."

MODE="${1:-prompt}"
MSG="Update quantum repository archive ($(date +%F))"
REMOTE_BRANCH="main"

echo "==> Disabling Git LFS for this repo"
git lfs uninstall --local 2>/dev/null || true
rm -rf .git/lfs   # drop the local LFS object cache (originals are backed up)

echo "==> Building a fresh single orphan commit"
git checkout --orphan _publish_tmp
# Fully empty the index, then re-stage everything from the working tree. This
# guarantees every file is committed with its REAL on-disk bytes — files that
# were unchanged since the old LFS commit would otherwise keep their stale LFS
# *pointer* blob (132 bytes) instead of the real PDF.
git read-tree --empty
git add -A
git commit -q -m "$MSG"

# Safety net: refuse to continue if any LFS pointer slipped into the commit.
if git lfs ls-files 2>/dev/null | grep -q .; then
  echo "ERROR: LFS pointer blobs still present in commit — aborting." >&2
  git lfs ls-files >&2
  exit 1
fi

# Replace main with the fresh root commit
git branch -D "$REMOTE_BRANCH" 2>/dev/null || true
git branch -m "$REMOTE_BRANCH"

echo "==> Reclaiming space from old objects"
git reflog expire --expire=now --all 2>/dev/null || true
git gc --prune=now --aggressive 2>/dev/null || true

echo ""
echo "Local repo is now a single commit on '$REMOTE_BRANCH':"
git log --oneline -1
echo "Repo size: $(du -sh .git | cut -f1) (.git)  /  $(du -sh --exclude=.git . 2>/dev/null | cut -f1 || du -sh . | cut -f1) (tree)"
echo ""

do_push() { echo "==> Force-pushing to origin/$REMOTE_BRANCH"; git push --force origin "$REMOTE_BRANCH"; echo "Done."; }

case "$MODE" in
  --push) do_push ;;
  --local) echo "Local only (mode=--local). Run 'git push --force origin $REMOTE_BRANCH' when ready." ;;
  *)
    read -r -p "Force-push this single commit to GitHub (origin/$REMOTE_BRANCH)? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] && do_push || echo "Skipped push. Run with --push when ready."
    ;;
esac
