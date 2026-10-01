#!/usr/bin/env bash
# Rejects AI-assistant attribution in commit messages.
#
# Contributors to this repository are people. A Co-Authored-By trailer naming
# an AI assistant makes GitHub list that assistant as a contributor, and
# session links leak tooling URLs into permanent history.
#
# Usage:
#   check-attribution.sh --message-file FILE   one message (the commit-msg hook)
#   check-attribution.sh --rev REV             every commit reachable from REV (CI)

set -euo pipefail

PATTERN='^(co-authored-by:.*(claude|anthropic)|claude-session:|.*generated with \[?claude code)'

offending_lines() { grep -inE "$PATTERN" || true; }

case "${1:-}" in
  --message-file)
    hits=$(sed '/^#/d' "$2" | offending_lines)
    if [ -n "$hits" ]; then
      echo "Commit rejected: AI attribution in the message." >&2
      echo "$hits" | sed 's/^/  line /' >&2
      echo "Remove those lines and commit again (see CONTRIBUTING.md)." >&2
      exit 1
    fi
    ;;
  --rev)
    status=0
    for sha in $(git rev-list "$2"); do
      hits=$(git log -1 --format=%B "$sha" | offending_lines)
      if [ -n "$hits" ]; then
        echo "::error::$(git log -1 --format='%h %s' "$sha") carries AI attribution:"
        echo "$hits" | sed 's/^/  line /'
        status=1
      fi
    done
    [ "$status" -eq 0 ] && echo "No AI attribution in $(git rev-list --count "$2") commits."
    exit "$status"
    ;;
  *)
    echo "usage: $0 --message-file FILE | --rev REV" >&2
    exit 2
    ;;
esac
