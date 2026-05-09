#!/usr/bin/env node
/**
 * Emit one NDJSON line per n8n credential type from compiled *.credentials.js files.
 *
 * Prerequisites: built n8n `packages/nodes-base` (`pnpm build` in upstream monorepo).
 *
 * Usage:
 *   node tools/dump_credentials.js --n8n-nodes-base ../n8n/packages/nodes-base > tools/credential_dump.jsonl
 *
 * Environment:
 *   N8N_NODES_BASE  Optional path (used if --n8n-nodes-base omitted).
 */
"use strict";

const fs = require("fs");
const path = require("path");

function usage() {
  console.error(`Usage: node ${path.basename(__filename)} [--n8n-nodes-base DIR]

  --n8n-nodes-base DIR   Path to n8n-nodes-base package (must contain dist/credentials/*.credentials.js)
  -h, --help

  Default DIR: process.env.N8N_NODES_BASE or ../n8n/packages/nodes-base (relative to cwd).
`);
}

function parseArgs(argv) {
  let nodesBase = process.env.N8N_NODES_BASE || null;
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--help" || a === "-h") {
      usage();
      process.exit(0);
    }
    if (a === "--n8n-nodes-base") {
      const next = argv[++i];
      if (!next) {
        console.error("error: --n8n-nodes-base requires a path");
        process.exit(2);
      }
      nodesBase = path.resolve(process.cwd(), next);
      continue;
    }
    console.error(`error: unknown argument: ${a}`);
    usage();
    process.exit(2);
  }
  if (!nodesBase) {
    nodesBase = path.resolve(process.cwd(), "../n8n/packages/nodes-base");
  }
  return nodesBase;
}

function collectCredentialConstructors(mod) {
  const out = [];
  if (!mod || typeof mod !== "object") {
    return out;
  }
  const seen = new Set();
  for (const v of Object.values(mod)) {
    if (typeof v !== "function" || seen.has(v)) continue;
    seen.add(v);
    if (v.prototype && v.prototype.constructor === v) {
      out.push(v);
    }
  }
  return out;
}

function serializeInstance(inst) {
  return JSON.parse(
    JSON.stringify(inst, (_k, v) => {
      if (typeof v === "function") return undefined;
      if (v === undefined) return undefined;
      return v;
    }),
  );
}

function walkCredentialJsFiles(credentialsDistDir) {
  if (!fs.existsSync(credentialsDistDir)) {
    return [];
  }
  const out = [];
  const entries = fs.readdirSync(credentialsDistDir, { withFileTypes: true });
  for (const ent of entries) {
    if (!ent.isFile()) continue;
    if (!ent.name.endsWith(".credentials.js")) continue;
    if (ent.name.includes(".test.")) continue;
    out.push(path.join(credentialsDistDir, ent.name));
  }
  return out.sort();
}

function main() {
  const nodesBaseRoot = parseArgs(process.argv);
  const credentialsDist = path.join(nodesBaseRoot, "dist", "credentials");

  if (!fs.existsSync(nodesBaseRoot) || !fs.statSync(nodesBaseRoot).isDirectory()) {
    console.error(`error: n8n nodes-base directory not found: ${nodesBaseRoot}`);
    console.error("  Build upstream (pnpm install && pnpm build in n8n repo).");
    process.exit(4);
  }

  const files = walkCredentialJsFiles(credentialsDist);
  if (files.length === 0) {
    console.error(`error: no *.credentials.js under ${credentialsDist}`);
    console.error("  Run pnpm build in packages/nodes-base.");
    process.exit(3);
  }

  let emitted = 0;
  let requireFailures = 0;
  let ctorFailures = 0;

  for (const absPath of files) {
    delete require.cache[require.resolve(absPath)];
    let mod;
    try {
      mod = require(absPath);
    } catch (e) {
      requireFailures += 1;
      console.error(`skip require ${absPath}: ${e.message}`);
      continue;
    }

    const ctorList = [];
    if (typeof mod.default === "function") ctorList.push(mod.default);
    ctorList.push(...collectCredentialConstructors(mod));

    const uniq = [];
    const seenCtor = new Set();
    for (const C of ctorList) {
      if (!seenCtor.has(C)) {
        seenCtor.add(C);
        uniq.push(C);
      }
    }

    if (uniq.length === 0) {
      console.error(`skip ${absPath}: no exported class`);
      ctorFailures += 1;
      continue;
    }

    const Ctor = uniq[0];
    let inst;
    try {
      inst = new Ctor();
    } catch (e) {
      ctorFailures += 1;
      console.error(`skip instantiate ${absPath}: ${e.message}`);
      continue;
    }

    const row = serializeInstance(inst);
    row._dumpSource = path.basename(absPath);
    process.stdout.write(JSON.stringify(row) + "\n");
    emitted += 1;
  }

  if (emitted === 0) {
    console.error("error: zero credential rows emitted");
    process.exit(5);
  }

  console.error(
    `[dump_credentials] emitted=${emitted} requireFailures=${requireFailures} ctorFailures=${ctorFailures}`,
  );
}

main();
