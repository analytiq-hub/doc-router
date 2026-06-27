"""Flow folder tree CRUD (organizational metadata)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

MAX_FOLDER_DEPTH = 8


class FlowFolderError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


async def list_folder_tree(db: Any, organization_id: str) -> list[dict[str, Any]]:
    folders = await db.flow_folders.find({"organization_id": organization_id}).sort("sort_order", 1).to_list(
        length=10_000
    )
    flow_counts: dict[str | None, int] = {}
    async for doc in db.flows.find({"organization_id": organization_id}, {"folder_id": 1}):
        fid = doc.get("folder_id")
        key = str(fid) if fid else None
        flow_counts[key] = flow_counts.get(key, 0) + 1

    by_parent: dict[str | None, list[dict[str, Any]]] = {}
    for f in folders:
        pid = f.get("parent_folder_id")
        parent_key = str(pid) if pid else None
        by_parent.setdefault(parent_key, []).append(f)

    def build(parent_id: str | None, depth: int) -> list[dict[str, Any]]:
        items = by_parent.get(parent_id, [])
        out: list[dict[str, Any]] = []
        for f in items:
            fid = str(f["_id"])
            out.append(
                {
                    "folder_id": fid,
                    "name": f.get("name") or "",
                    "parent_folder_id": str(f["parent_folder_id"]) if f.get("parent_folder_id") else None,
                    "sort_order": int(f.get("sort_order") or 0),
                    "flow_count": flow_counts.get(fid, 0),
                    "children": build(fid, depth + 1) if depth < MAX_FOLDER_DEPTH else [],
                }
            )
        return out

    return build(None, 0)


async def create_folder(
    db: Any,
    *,
    organization_id: str,
    name: str,
    parent_folder_id: str | None,
    sort_order: int,
    user_id: str,
) -> str:
    name = name.strip()
    if not name:
        raise FlowFolderError("Folder name is required")

    parent_oid = None
    depth = 0
    if parent_folder_id:
        try:
            parent_oid = ObjectId(parent_folder_id)
        except Exception as e:
            raise FlowFolderError("Invalid parent_folder_id") from e
        parent = await db.flow_folders.find_one({"_id": parent_oid, "organization_id": organization_id})
        if not parent:
            raise FlowFolderError("Parent folder not found")
        depth = int(parent.get("_depth") or 0) + 1
        if depth >= MAX_FOLDER_DEPTH:
            raise FlowFolderError("Maximum folder depth exceeded")

    sibling_filter: dict[str, Any] = {"organization_id": organization_id, "name": name}
    if parent_oid:
        sibling_filter["parent_folder_id"] = str(parent_oid)
    else:
        sibling_filter["parent_folder_id"] = None
    if await db.flow_folders.find_one(sibling_filter):
        raise FlowFolderError("Folder name must be unique among siblings")

    now = _now()
    res = await db.flow_folders.insert_one(
        {
            "organization_id": organization_id,
            "name": name,
            "parent_folder_id": str(parent_oid) if parent_oid else None,
            "sort_order": sort_order,
            "_depth": depth,
            "created_at": now,
            "created_by": user_id,
            "updated_at": now,
            "updated_by": user_id,
        }
    )
    return str(res.inserted_id)


async def delete_folder(db: Any, *, organization_id: str, folder_id: str) -> None:
    try:
        oid = ObjectId(folder_id)
    except Exception as e:
        raise FlowFolderError("Invalid folder_id") from e

    doc = await db.flow_folders.find_one({"_id": oid, "organization_id": organization_id})
    if not doc:
        raise FlowFolderError("Folder not found")

    child_count = await db.flow_folders.count_documents(
        {"organization_id": organization_id, "parent_folder_id": folder_id}
    )
    flow_count = await db.flows.count_documents({"organization_id": organization_id, "folder_id": folder_id})
    if child_count or flow_count:
        raise FlowFolderError(
            f"Folder is not empty ({flow_count} flows, {child_count} subfolders)"
        )

    await db.flow_folders.delete_one({"_id": oid})
