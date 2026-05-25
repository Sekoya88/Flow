#!/usr/bin/env bash
# Get a Flow JWT and print ready-to-use MCP connection URLs.
# Usage: FLOW_EMAIL=you@example.com FLOW_PASSWORD=secret bash scripts/get-flow-token.sh

set -euo pipefail

EMAIL="${FLOW_EMAIL:-}"
PASSWORD="${FLOW_PASSWORD:-}"
API_URL="${FLOW_API_URL:-http://localhost:18000}"
MCP_URL="${FLOW_MCP_URL:-http://localhost:18001}"

if [[ -z "$EMAIL" || -z "$PASSWORD" ]]; then
  echo "Usage: FLOW_EMAIL=<email> FLOW_PASSWORD=<pass> bash scripts/get-flow-token.sh"
  exit 1
fi

TOKEN=$(curl -sf -X POST "$API_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jq -r .access_token)

if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
  echo "Login failed — check credentials or that the API is running at $API_URL"
  exit 1
fi

echo ""
echo "=== Flow JWT Token ==="
echo "$TOKEN"
echo ""
echo "=== MCP Connection URLs ==="
echo "SSE (Claude Desktop, Cursor, Claude Code SSE):"
echo "  $MCP_URL/sse?token=$TOKEN"
echo ""
echo "Streamable HTTP (Claude Code, Cursor, Windsurf):"
echo "  $MCP_URL/mcp?token=$TOKEN"
echo ""
echo "=== Claude Desktop config snippet ==="
cat <<EOF
{
  "mcpServers": {
    "flow": {
      "url": "$MCP_URL/sse?token=$TOKEN"
    }
  }
}
EOF
echo ""
echo "=== Claude Code settings.json snippet ==="
cat <<EOF
{
  "mcpServers": {
    "flow": {
      "type": "sse",
      "url": "$MCP_URL/sse?token=$TOKEN"
    }
  }
}
EOF
echo ""
echo "=== .cursor/mcp.json snippet ==="
cat <<EOF
{
  "mcpServers": {
    "flow": {
      "url": "$MCP_URL/sse?token=$TOKEN"
    }
  }
}
EOF
