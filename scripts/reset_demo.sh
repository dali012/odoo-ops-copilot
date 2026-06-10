#!/usr/bin/env bash
# Scheduled demo reset — run via cron, e.g. every 6 hours:
#   0 */6 * * * /path/to/scripts/reset_demo.sh >> /var/log/demo_reset.log 2>&1
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting demo reset..."

# Wipe chat sessions and writeback audit log so visitors don't see each other's history
docker compose -f "$REPO_ROOT/docker-compose.yml" exec -T db psql -U odoo -d odoo_copilot \
  -c "TRUNCATE copilot.messages, copilot.sessions, copilot.writeback_actions RESTART IDENTITY CASCADE;"

# Re-run seed to restore any Odoo records mutated outside DEMO_MODE guard
docker compose -f "$REPO_ROOT/docker-compose.yml" exec -T backend \
  python -m app.seed

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Demo reset complete."
