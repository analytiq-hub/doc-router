#!/bin/bash

# Read environment variables from .mcp.json
MCP_CONFIG=".mcp.json"

if [ ! -f "$MCP_CONFIG" ]; then
  echo "Error: $MCP_CONFIG not found"
  exit 1
fi

# Extract environment variables from .mcp.json using node
ENV_VARS=$(node -e "
  const fs = require('fs');
  const config = JSON.parse(fs.readFileSync('$MCP_CONFIG', 'utf8'));
  const env = config.mcpServers.docrouter.env || {};
  const vars = Object.entries(env).map(([k, v]) => \`\${k}=\${v}\`).join(' ');
  console.log(vars);
")

# Export the environment variables and run the inspector
eval "export $ENV_VARS"
npx -y @modelcontextprotocol/inspector tsx src/index.ts
