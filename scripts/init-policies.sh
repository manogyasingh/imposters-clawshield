#!/usr/bin/env bash
# ---------------------------------------------------------------
# ClawShield — ArmorClaw Policy Initialization
#
# Sets up all security policies for the ClawShield agent.
# Run this after the OpenClaw gateway is started.
#
# Usage: bash scripts/init-policies.sh
# ---------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
POLICY_FILE="$PROJECT_DIR/workspace/armorclaw-policy.json"

cat > "$POLICY_FILE" << 'POLICY_EOF'
{
  "version": "1.0",
  "name": "clawshield-policy",
  "description": "ClawShield form-filling agent security policies",
  "rules": [
    {
      "id": "allow-detect-fields",
      "action": "allow",
      "tool": "form_detect_fields",
      "description": "Allow form field detection on inbox PDFs"
    },
    {
      "id": "allow-extract-profile",
      "action": "allow",
      "tool": "form_extract_profile_data",
      "description": "Allow reading profile data for field matching"
    },
    {
      "id": "allow-fill-pdf",
      "action": "allow",
      "tool": "form_fill_pdf",
      "description": "Allow filling PDFs (output goes to staged)"
    },
    {
      "id": "allow-save-output",
      "action": "allow",
      "tool": "form_save_output",
      "description": "Allow saving staged PDFs to outbox"
    },
    {
      "id": "allow-transcribe",
      "action": "allow",
      "tool": "form_transcribe_audio",
      "description": "Allow audio transcription within workspace"
    },
    {
      "id": "deny-write-file",
      "action": "deny",
      "tool": "write_file",
      "description": "Prevent bypassing form tools with raw file writes"
    },
    {
      "id": "deny-exec",
      "action": "deny",
      "tool": "exec",
      "description": "Prevent arbitrary command execution"
    },
    {
      "id": "deny-shell",
      "action": "deny",
      "tool": "shell",
      "description": "Prevent shell access"
    },
    {
      "id": "deny-web-fetch",
      "action": "deny",
      "tool": "web_fetch",
      "description": "Prevent arbitrary web requests"
    },
    {
      "id": "deny-read-file-outside",
      "action": "deny",
      "tool": "read_file",
      "description": "Prevent reading files outside workspace"
    }
  ]
}
POLICY_EOF

echo "Policy file written to: $POLICY_FILE"
echo ""
echo "Policies configured:"
echo "  [ALLOW] form_detect_fields     — inbox PDF analysis"
echo "  [ALLOW] form_extract_profile_data — profile data reading"
echo "  [ALLOW] form_fill_pdf          — PDF filling to staged"
echo "  [ALLOW] form_save_output       — staged to outbox copy"
echo "  [ALLOW] form_transcribe_audio  — voice transcription"
echo "  [DENY]  write_file             — no raw file writes"
echo "  [DENY]  exec                   — no command execution"
echo "  [DENY]  shell                  — no shell access"
echo "  [DENY]  web_fetch              — no arbitrary web requests"
echo "  [DENY]  read_file              — no reads outside workspace"
echo ""
echo "Done. Policy is ready for ArmorClaw enforcement."
