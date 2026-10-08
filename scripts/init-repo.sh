#!/usr/bin/env bash
# Replace placeholders with your GitHub / Docker Hub names.
set -euo pipefail
: "${GH_USER:?set GH_USER}" "${DH_USER:?set DH_USER}"
GH_REPO="${GH_REPO:-ai-sre-gitops}"
cd "$(dirname "$0")/.."
grep -rlE '__GH_USER__|__DH_USER__|__GH_REPO__' gitops terraform | while read -r f; do
  sed -i.bak -e "s/__GH_USER__/$GH_USER/g" -e "s/__DH_USER__/$DH_USER/g" -e "s/__GH_REPO__/$GH_REPO/g" "$f"
  rm -f "$f.bak"
done
echo "Done. Review with: git diff"
