#!/usr/bin/env python3
"""Reset the Datos demo orgs to their starting state.

Usage (from the repo root, with the venv active):
    python tests-ui/demo/datos-2026/reset.py --setup     # once: demo user + knowledge base
    python tests-ui/demo/datos-2026/reset.py             # before every run
    python tests-ui/demo/datos-2026/reset.py --dry-run   # show what would change

What a reset does in the `insurance` org:
  * deletes the FNOL copy that Part 3 uploads,
  * deletes every prompt, schema and tag that is not part of the baseline
    (the chat agent creates these during the demo),
  * restores the tags on the home FNOL, the auto FNOL and the home policy,
  * deletes the demo user's agent chat threads on the home FNOL.

The `test` org's surgery flow is only checked (active, pinned input present).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import bcrypt
import httpx
import yaml
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def load_env() -> dict[str, str]:
    env = {**dotenv_values(REPO / ".env"), **dotenv_values(HERE / ".env")}
    env.update({k: v for k, v in os.environ.items() if k.startswith(("DEMO_", "MONGODB_", "ENV"))})
    for key in ("DEMO_EMAIL", "DEMO_PASSWORD"):
        if not env.get(key):
            sys.exit(f"{key} is not set. Put it in {HERE / '.env'}")
    return env


class Api:
    def __init__(self, base: str, email: str, password: str, dry_run: bool):
        self.dry_run = dry_run
        self.http = httpx.Client(base_url=base, timeout=60)
        r = self.http.post("/v0/account/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            sys.exit(f"Login failed for {email}: {r.status_code} {r.text}. Run with --setup first.")
        self.http.headers["Authorization"] = f"Bearer {r.json()['token']}"

    def get(self, path: str, **params):
        r = self.http.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def write(self, method: str, path: str, label: str, json=None):
        print(f"  {'would ' if self.dry_run else ''}{label}")
        if self.dry_run:
            return None
        r = self.http.request(method, path, json=json)
        if r.status_code >= 400:
            sys.exit(f"{method} {path} failed: {r.status_code} {r.text}")
        return r.json() if r.content else None


# ---------------------------------------------------------------- setup

def ensure_demo_user(db, env, cfg, dry_run: bool) -> None:
    email = env["DEMO_EMAIL"]
    user = db.users.find_one({"email": email})
    hashed = bcrypt.hashpw(env["DEMO_PASSWORD"].encode(), bcrypt.gensalt(12)).decode()
    if user:
        print(f"  demo user {email} exists; refreshing password")
        if not dry_run:
            db.users.update_one({"_id": user["_id"]}, {"$set": {"password": hashed, "email_verified": True}})
        user_id = str(user["_id"])
    else:
        print(f"  {'would create' if dry_run else 'creating'} demo user {email}")
        if dry_run:
            return
        user_id = str(db.users.insert_one({
            "email": email,
            "password": hashed,
            "name": env.get("DEMO_NAME") or "Demo Presenter",
            "email_verified": True,
            "has_seen_tour": True,
            "created_at": datetime.now(UTC),
        }).inserted_id)

    for org_key in ("insurance", "test"):
        org_id = cfg[org_key]["org_id"]
        org = db.organizations.find_one({"_id": ObjectId(org_id)})
        if not org:
            sys.exit(f"Organization {org_id} ({org_key}) not found")
        if any(m["user_id"] == user_id for m in org.get("members", [])):
            continue
        print(f"  {'would add' if dry_run else 'adding'} demo user to {org['name']} as admin")
        if not dry_run:
            db.organizations.update_one(
                {"_id": org["_id"]},
                {"$push": {"members": {"user_id": user_id, "permission_group_ids": ["admin"]}}},
            )


def ensure_kb(api: Api, cfg) -> None:
    ins = cfg["insurance"]
    org = ins["org_id"]
    kb_cfg = ins["kb"]
    tags = {t["name"]: t["id"] for t in api.get(f"/v0/orgs/{org}/tags", limit=100)["tags"]}
    existing = [k for k in api.get(f"/v0/orgs/{org}/knowledge-bases")["knowledge_bases"] if k["name"] == kb_cfg["name"]]
    if existing:
        kb = existing[0]
        print(f"  knowledge base '{kb_cfg['name']}' exists ({kb['status']}, {kb['document_count']} docs, {kb['chunk_count']} chunks)")
        return
    api.write("POST", f"/v0/orgs/{org}/knowledge-bases", f"create knowledge base '{kb_cfg['name']}'", json={
        "name": kb_cfg["name"],
        "description": kb_cfg["description"],
        "system_prompt": kb_cfg["system_prompt"],
        "tag_ids": [tags[kb_cfg["tag"]]],
    })
    if api.dry_run:
        return
    for _ in range(60):
        kb = [k for k in api.get(f"/v0/orgs/{org}/knowledge-bases")["knowledge_bases"] if k["name"] == kb_cfg["name"]][0]
        if kb["status"] == "active" and kb["document_count"] > 0:
            print(f"  indexed: {kb['document_count']} docs, {kb['chunk_count']} chunks")
            return
        if kb["status"] == "error":
            sys.exit("Knowledge base indexing failed; check the worker log")
        time.sleep(3)
    print("  knowledge base still indexing; check it before recording")


# ---------------------------------------------------------------- reset

def reset_insurance(api: Api, cfg) -> None:
    ins = cfg["insurance"]
    org = ins["org_id"]
    baseline = set(ins["baseline_tags"])

    # 0. The document Part 3 uploads.
    listing = api.get(f"/v0/orgs/{org}/documents", limit=50, name_search=ins["upload_file_name"])
    for d in listing["documents"]:
        if d["document_name"] == ins["upload_file_name"]:
            api.write("DELETE", f"/v0/orgs/{org}/documents/{d['id']}", f"delete uploaded {d['document_name']} ({d['id']})")

    tags = api.get(f"/v0/orgs/{org}/tags", limit=100)["tags"]
    name_to_id = {t["name"]: t["id"] for t in tags}
    missing = baseline - name_to_id.keys()
    if missing:
        sys.exit(f"Baseline tags missing from insurance org: {sorted(missing)}")
    extra_tags = [t for t in tags if t["name"] not in baseline]

    # 1. Prompts first: tags and schemas cannot be deleted while a prompt uses them.
    for p in api.get(f"/v0/orgs/{org}/prompts", limit=100)["prompts"]:
        api.write("DELETE", f"/v0/orgs/{org}/prompts/{p['prompt_id']}", f"delete prompt '{p['name']}'")

    # 2. Restore document tags (this also detaches any agent-created tag).
    for doc_key, tags_key in (
        ("home_fnol_doc_id", "home_fnol_tags"),
        ("auto_fnol_doc_id", "auto_fnol_tags"),
        ("home_policy_doc_id", "home_policy_tags"),
    ):
        want = [name_to_id[n] for n in ins[tags_key]]
        doc = api.get(f"/v0/orgs/{org}/documents/{ins[doc_key]}")
        if sorted(doc.get("tag_ids") or []) != sorted(want):
            api.write("PUT", f"/v0/orgs/{org}/documents/{ins[doc_key]}",
                      f"set tags on {doc['document_name']} to {ins[tags_key]}", json={"tag_ids": want})

    # Any other document still carrying an agent tag gets it removed.
    extra_ids = {t["id"] for t in extra_tags}
    if extra_ids:
        listing = api.get(f"/v0/orgs/{org}/documents", limit=200)
        for d in listing["documents"]:
            if d["id"] in (ins["home_fnol_doc_id"], ins["auto_fnol_doc_id"], ins["home_policy_doc_id"]):
                continue
            current = d.get("tag_ids") or []
            if extra_ids & set(current):
                keep = [t for t in current if t not in extra_ids]
                api.write("PUT", f"/v0/orgs/{org}/documents/{d['id']}",
                          f"remove agent tags from {d['document_name']}", json={"tag_ids": keep})

    # 3. Schemas, then 4. tags.
    for s in api.get(f"/v0/orgs/{org}/schemas", limit=100)["schemas"]:
        api.write("DELETE", f"/v0/orgs/{org}/schemas/{s['schema_id']}", f"delete schema '{s['name']}'")
    for t in extra_tags:
        api.write("DELETE", f"/v0/orgs/{org}/tags/{t['id']}", f"delete tag '{t['name']}'")

    # 5. Agent chat threads on the home FNOL, so the panel opens empty.
    doc_id = ins["home_fnol_doc_id"]
    for th in api.get(f"/v0/orgs/{org}/documents/{doc_id}/chat/threads"):
        api.write("DELETE", f"/v0/orgs/{org}/documents/{doc_id}/chat/threads/{th['id']}",
                  f"delete chat thread '{th.get('title')}'")


def ensure_upload_file(api: Api, cfg) -> None:
    """Part 3 uploads a copy of the auto FNOL; keep it out of git, fetch it from the API."""
    ins = cfg["insurance"]
    target = HERE / ".cache" / ins["upload_file_name"]
    if target.exists():
        return
    target.parent.mkdir(exist_ok=True)
    r = api.http.get(f"/v0/orgs/{ins['org_id']}/documents/{ins['auto_fnol_doc_id']}/file")
    r.raise_for_status()
    target.write_bytes(r.content)
    print(f"  cached {target.relative_to(HERE)} ({len(r.content)} bytes)")


CREDITS_PER_RUN = 40  # measured: one full pass uses roughly 30 SPU credits in `insurance`


def check_credits(db, cfg) -> None:
    """LLM, OCR and KB steps fail with SPUCreditException when an org runs out."""
    for key in ("insurance", "test"):
        org_id = cfg[key]["org_id"]
        c = db.payments_customers.find_one({"org_id": org_id}) or {}
        left = (c.get("granted_credits", 0) - c.get("granted_credits_used", 0)
                + c.get("purchased_credits", 0) - c.get("purchased_credits_used", 0))
        note = "" if left >= CREDITS_PER_RUN else f"  <-- LOW: add credits as a sysadmin (about {CREDITS_PER_RUN} per run)"
        print(f"  {key}: {left} SPU credits left{note}")


def check_surgery_flow(db, cfg) -> None:
    flow_id = cfg["test"]["surgery_flow_id"]
    flow = db.flows.find_one({"_id": ObjectId(flow_id)})
    if not flow:
        sys.exit(f"Surgery flow {flow_id} not found")
    rev = db.flow_revisions.find_one({"_id": ObjectId(flow["active_flow_revid"])})
    pins = (rev or {}).get("pin_data") or {}
    pinned = any(items for node in pins.values() for items in node.get("main", []))
    print(f"  surgery flow v{rev['flow_version']}: active={flow.get('active')}, pinned input={'yes' if pinned else 'MISSING'}")
    if not pinned:
        sys.exit("The surgery flow has no pinned input; pin surgery_schedule_packet.pdf on the trigger")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--setup", action="store_true", help="create the demo user and the knowledge base")
    ap.add_argument("--dry-run", action="store_true", help="print changes without making them")
    args = ap.parse_args()

    cfg = yaml.safe_load((HERE / "steps.yaml").read_text())["config"]
    env = load_env()
    db = MongoClient(env.get("MONGODB_URI") or "mongodb://127.0.0.1:27017")[env.get("ENV") or "test"]

    if args.setup:
        print("Demo user")
        ensure_demo_user(db, env, cfg, args.dry_run)

    api = Api(cfg["api_url"], env["DEMO_EMAIL"], env["DEMO_PASSWORD"], args.dry_run)

    print("insurance org")
    reset_insurance(api, cfg)
    ensure_upload_file(api, cfg)
    if args.setup:
        ensure_kb(api, cfg)
    print("test org")
    check_surgery_flow(db, cfg)
    print("credits")
    check_credits(db, cfg)
    print("Done." if not args.dry_run else "Dry run: nothing changed.")


if __name__ == "__main__":
    main()
