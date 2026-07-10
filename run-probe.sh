#!/usr/bin/env bash
# Drive a headless agent turn against a demo Claw instance.
#
# Usage: ./run-probe.sh <instance> <prompt-file> <session-key> [out.json]
#   ./run-probe.sh claw-plain  prompts/recall-only.txt demo-take1 plain.json
#   ./run-probe.sh claw-memory prompts/recall-only.txt demo-take1 memory.json
#
# Notes:
# - A NEW session-key = a fresh session (this is the session boundary).
# - The JSON result carries token usage at .result.meta.agentMeta.usage
#   and the reply text at .result.payloads[0].text.
set -euo pipefail
NS=${NS:?set NS to the namespace your demo Claws run in}
inst=$1; prompt=$2; key=$3; out=${4:-/dev/stdout}

start=$(date +%s)
oc exec -i -n "$NS" "deploy/$inst" -c gateway -- sh -c \
  'cat > /tmp/msg.txt && openclaw agent --message-file /tmp/msg.txt --session-key '"$key"' --json' \
  < "$prompt" > "$out"
echo "$inst rc=$? elapsed=$(( $(date +%s) - start ))s" >&2
