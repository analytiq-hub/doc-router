#!/usr/bin/env node
// Emit JSON Lines of integration node descriptors from compiled "*.node.js" modules.
//
// Prerequisites: sibling repo built so dist "*.node.js" files exist under subdirs you pass or
//   set in FLOW_DUMP_SUBDIRS (POSIX path list, ':'-separated on Unix, ';' on Windows).
//
// Usage:
//   FLOW_DUMP_SUBDIRS='packages/my-nodes/dist/nodes' \
//     node tools/dump_nodes.js --upstream-root ../upstream_nodes > tools/flow_node_dump.jsonl
//   node tools/dump_nodes.js --upstream-root DIR --subdir REL/PATH [--subdir REL2]
"use strict";

const fs = require("fs");
const path = require("path");

function usage() {
  console.error(`Usage: node ${path.basename(__filename)} --upstream-root DIR [--subdir REL]...

  --upstream-root DIR   Root of the built integration monorepo (required)
  --subdir REL          Relative directory under root to scan (repeatable)
  -h, --help

  If no --subdir: uses FLOW_DUMP_SUBDIRS (':' or ';' separated relative paths).

Writes JSON Lines: {"source":"<path>","description":{...}[, "integration_type_version_key": ...]}
`);
}

function parseArgs(argv) {
  let upstreamRoot = null;
  const subdirs = [];
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--help" || a === "-h") {
      usage();
      process.exit(0);
    }
    if (a === "--upstream-root") {
      const next = argv[++i];
      if (!next) {
        console.error("error: --upstream-root requires a path");
        process.exit(2);
      }
      upstreamRoot = path.resolve(process.cwd(), next);
      continue;
    }
    if (a === "--subdir") {
      const next = argv[++i];
      if (!next) {
        console.error("error: --subdir requires a path");
        process.exit(2);
      }
      subdirs.push(next);
      continue;
    }
    console.error(`error: unknown argument: ${a}`);
    usage();
    process.exit(2);
  }
  if (!upstreamRoot) {
    console.error("error: --upstream-root is required");
    usage();
    process.exit(2);
  }
  let resolvedSubdirs = subdirs;
  if (!resolvedSubdirs.length) {
    const env = process.env.FLOW_DUMP_SUBDIRS || "";
    const sep = path.sep === "\\" ? /;/ : /[:;]/;
    resolvedSubdirs = env
      .split(sep)
      .map((s) => s.trim())
      .filter(Boolean);
  }
  if (!resolvedSubdirs.length) {
    console.error(
      "error: pass --subdir or set FLOW_DUMP_SUBDIRS (see --help)",
    );
    process.exit(2);
  }
  const root = upstreamRoot;
  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) {
    console.error(`error: --upstream-root is not a directory: ${root}`);
    process.exit(4);
  }
  return { upstreamRoot: root, subdirs: resolvedSubdirs };
}

function walkNodeFiles(root, subdir) {
  const base = path.join(root, subdir);
  if (!fs.existsSync(base)) {
    return [];
  }
  const out = [];
  const stack = [base];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const ent of entries) {
      const p = path.join(dir, ent.name);
      if (ent.isDirectory()) {
        stack.push(p);
      } else if (ent.isFile() && ent.name.endsWith(".node.js")) {
        out.push(p);
      }
    }
  }
  return out.sort();
}

function collectConstructors(mod) {
  const out = [];
  if (typeof mod === "function") {
    out.push(mod);
    return out;
  }
  if (!mod || typeof mod !== "object") {
    return out;
  }
  const seen = new Set();
  for (const v of Object.values(mod)) {
    if (typeof v !== "function" || seen.has(v)) {
      continue;
    }
    seen.add(v);
    if (v.prototype && v.prototype.constructor === v) {
      out.push(v);
    }
  }
  return out;
}

function tryInstantiate(Ctor) {
  try {
    return new Ctor();
  } catch {
    return null;
  }
}

/**
 * n8n `VersionedNodeType` sets `nodeVersions` values to instantiated nodes
 * (`new SlackV2(base)`, …), not constructors. Older or custom nodes may still
 * store a constructor reference.
 */
function descriptionFromVersionEntry(entry) {
  if (!entry) {
    return null;
  }
  if (typeof entry === "function") {
    const subInst = tryInstantiate(entry);
    const d = subInst?.description;
    return typeof d === "object" && d !== null ? d : null;
  }
  if (typeof entry === "object") {
    const d = entry.description;
    if (typeof d === "object" && d !== null) {
      return d;
    }
  }
  return null;
}

function relativePosix(fromDir, absPath) {
  let rel = path.relative(fromDir, absPath);
  if (!rel.startsWith(".")) {
    rel = `./${rel}`;
  }
  return rel.split(path.sep).join("/");
}

function main() {
  const { upstreamRoot, subdirs } = parseArgs(process.argv);
  const repoRoot = path.resolve(__dirname, "..");

  let files = [];
  for (const sub of subdirs) {
    files = files.concat(walkNodeFiles(upstreamRoot, sub));
  }

  if (files.length === 0) {
    console.error(
      `error: no *.node.js under ${upstreamRoot} for subdirs: ${subdirs.join(", ")}`,
    );
    console.error(
      "  Build upstream (e.g. pnpm install && pnpm build), or extend FLOW_DUMP_SUBDIRS with paths that exist.",
    );
    process.exit(3);
  }

  const emitted = new Set();

  for (const absPath of files) {
    delete require.cache[require.resolve(absPath)];
    let mod;
    try {
      mod = require(absPath);
    } catch (e) {
      console.error(`skip require ${relativePosix(repoRoot, absPath)}: ${e.message}`);
      continue;
    }
    const modObj = mod && mod.__esModule ? { ...mod, default: mod.default } : mod;
    const ctorList = [];
    const dft = modObj?.default;
    if (typeof dft === "function") {
      ctorList.push(dft);
    }
    ctorList.push(...collectConstructors(modObj));
    const uniqCtors = [];
    const ctorSeen = new Set();
    for (const C of ctorList) {
      if (!ctorSeen.has(C)) {
        ctorSeen.add(C);
        uniqCtors.push(C);
      }
    }

    const rel = relativePosix(repoRoot, absPath);

    for (const Ctor of uniqCtors) {
      const inst = tryInstantiate(Ctor);
      if (!inst) {
        continue;
      }
      const desc =
        typeof inst.description === "object" ? inst.description : null;
      if (!desc || typeof desc !== "object") {
        continue;
      }

      const versionsObj =
        Ctor.nodeVersions || inst.nodeVersions || desc.nodeVersions;
      let versionEmitted = false;
      if (
        versionsObj &&
        typeof versionsObj === "object" &&
        !Array.isArray(versionsObj)
      ) {
        for (const [verKey, entry] of Object.entries(versionsObj)) {
          const sd = descriptionFromVersionEntry(entry);
          if (!sd || typeof sd !== "object") {
            continue;
          }
          const fingerprint = `${rel}@${verKey}@${sd.name || ""}`;
          if (emitted.has(fingerprint)) {
            continue;
          }
          emitted.add(fingerprint);
          versionEmitted = true;
          process.stdout.write(
            JSON.stringify({
              source: rel,
              description: sd,
              integration_type_version_key: verKey,
            }) + "\n",
          );
        }
      }
      if (versionEmitted) {
        continue;
      }

      const fingerprint = `${rel}@${desc.name || ""}`;
      if (emitted.has(fingerprint)) {
        continue;
      }
      emitted.add(fingerprint);
      process.stdout.write(
        JSON.stringify({ source: rel, description: desc }) + "\n",
      );
    }
  }
}

main();
