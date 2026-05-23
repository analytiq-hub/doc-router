"""Google Drive API v3 operations for ``flows.google_drive``."""

from __future__ import annotations

from typing import Any

import analytiq_data as ad

from .api import (
    google_api_request,
    google_api_request_all_items,
    google_export_file_bytes,
    new_drive_request_id,
    resolve_oauth_access_token,
    resumable_upload,
    upload_multipart_file,
)
from .helpers import (
    DRIVE_FOLDER_MIME,
    RLC_DRIVE_DEFAULT,
    RLC_FOLDER_DEFAULT,
    permissions_from_ui,
    prepare_query_fields,
    drive_file_id_from_param,
    rlc_value,
    set_file_properties,
    set_parent_folder,
    set_update_common_params,
    share_options_query,
    shared_drive_query_defaults,
    update_drive_scopes,
    validate_resource_operation,
)

async def execute_google_drive_item(
    context: "ad.flows.ExecutionContext",
    node: dict[str, Any],
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    *,
    item_index: int,
) -> "ad.flows.FlowItem":
    resource = str(params.get("resource") or "file")
    operation = str(params.get("operation") or "")
    validate_resource_operation(resource, operation)
    token = await resolve_oauth_access_token(context, node)

    if resource == "drive":
        data = await _run_drive(context, token, operation, params)
    elif resource == "file":
        data = await _run_file(context, token, operation, params, item, item_index=item_index)
    elif resource == "fileFolder":
        data = await _run_file_folder(token, operation, params)
    elif resource == "folder":
        data = await _run_folder(token, operation, params)
    else:
        raise ValueError(f"Unknown Google Drive resource: {resource}")

    if isinstance(data, ad.flows.FlowItem):
        return data
    return ad.flows.FlowItem(
        json=data if isinstance(data, dict) else {"data": data},
        binary=dict(item.binary),
        meta=dict(item.meta),
    )


# --- drive ---


async def _run_drive(
    context: "ad.flows.ExecutionContext",
    token: str,
    operation: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    options = params.get("options") if isinstance(params.get("options"), dict) else {}

    if operation == "create":
        body: dict[str, Any] = {"name": str(params.get("name") or "Untitled")}
        for key in ("capabilities", "colorRgb", "hidden", "restrictions"):
            if key in options and options[key] is not None:
                body[key] = options[key]
        return await google_api_request(
            token,
            "POST",
            "/drive/v3/drives",
            body=body,
            query={"requestId": new_drive_request_id()},
        )

    drive_id = rlc_value(params.get("driveId"))
    if operation == "get":
        qs: dict[str, Any] = {}
        if options.get("useDomainAdminAccess"):
            qs["useDomainAdminAccess"] = True
        return await google_api_request(token, "GET", f"/drive/v3/drives/{drive_id}", query=qs)

    if operation == "list":
        qs: dict[str, Any] = {}
        if options.get("q"):
            qs["q"] = options["q"]
        if options.get("useDomainAdminAccess"):
            qs["useDomainAdminAccess"] = True
        if params.get("returnAll"):
            drives = await google_api_request_all_items(
                token, "GET", "/drive/v3/drives", "drives", query=qs
            )
            return {"drives": drives}
        qs.setdefault("pageSize", int(params.get("limit") or 50))
        data = await google_api_request(token, "GET", "/drive/v3/drives", query=qs)
        return data if isinstance(data, dict) else {"drives": []}

    if operation == "update":
        body = {k: options[k] for k in ("name", "colorRgb", "restrictions") if k in options}
        return await google_api_request(token, "PATCH", f"/drive/v3/drives/{drive_id}", body=body)

    if operation == "deleteDrive":
        await google_api_request(token, "DELETE", f"/drive/v3/drives/{drive_id}")
        return {"success": True}

    raise ValueError(f"Unsupported drive operation: {operation}")


# --- folder ---


async def _run_folder(token: str, operation: str, params: dict[str, Any]) -> dict[str, Any]:
    options = params.get("options") if isinstance(params.get("options"), dict) else {}

    if operation == "create":
        drive_id = rlc_value(params.get("driveId"), default=RLC_DRIVE_DEFAULT)
        folder_id = rlc_value(params.get("folderId"), default=RLC_FOLDER_DEFAULT)
        body: dict[str, Any] = {
            "name": str(params.get("name") or "Untitled"),
            "mimeType": DRIVE_FOLDER_MIME,
            "parents": [set_parent_folder(folder_id, drive_id)],
        }
        if options.get("folderColorRgb"):
            body["folderColorRgb"] = options["folderColorRgb"]
        qs = {**shared_drive_query_defaults()}
        if not options.get("simplifyOutput", True):
            qs["fields"] = "*"
        return await google_api_request(token, "POST", "/drive/v3/files", body=body, query=qs)

    folder_id = rlc_value(params.get("folderNoRootId"))
    if operation == "deleteFolder":
        if options.get("deletePermanently"):
            await google_api_request(
                token,
                "DELETE",
                f"/drive/v3/files/{folder_id}",
                query={"supportsAllDrives": True},
            )
        else:
            await google_api_request(
                token,
                "PATCH",
                f"/drive/v3/files/{folder_id}",
                body={"trashed": True},
                query={"supportsAllDrives": True},
            )
        return {"fileId": folder_id, "success": True}

    if operation == "share":
        perms = permissions_from_ui(params.get("permissionsUi"))
        if not perms:
            raise ValueError("At least one permission is required to share a folder")
        qs = share_options_query(options)
        result = await google_api_request(
            token,
            "POST",
            f"/drive/v3/files/{folder_id}/permissions",
            body=perms[0],
            query=qs,
        )
        return result if isinstance(result, dict) else {"permission": result}

    raise ValueError(f"Unsupported folder operation: {operation}")


# --- fileFolder ---


async def _run_file_folder(token: str, operation: str, params: dict[str, Any]) -> dict[str, Any]:
    if operation != "search":
        raise ValueError(f"Unsupported fileFolder operation: {operation}")

    options = params.get("options") if isinstance(params.get("options"), dict) else {}
    filt = params.get("filter") if isinstance(params.get("filter"), dict) else {}
    drive_id = rlc_value(filt.get("driveId"), default=RLC_DRIVE_DEFAULT)
    folder_id = rlc_value(filt.get("folderId"), default=RLC_FOLDER_DEFAULT)
    what = str(filt.get("whatToSearch") or "all")
    include_trashed = bool(filt.get("includeTrashed"))

    q_parts: list[str] = []
    method = str(params.get("searchMethod") or "name")
    qstr = str(params.get("queryString") or "")
    if method == "name" and qstr:
        q_parts.append(f"name contains '{qstr.replace(chr(39), chr(92)+chr(39))}'")
    elif method == "query" and qstr:
        q_parts.append(qstr)

    if folder_id and folder_id != RLC_FOLDER_DEFAULT:
        q_parts.append(f"'{folder_id}' in parents")
    if what == "folders":
        q_parts.append(f"mimeType = '{DRIVE_FOLDER_MIME}'")
    elif what == "files":
        q_parts.append(f"mimeType != '{DRIVE_FOLDER_MIME}'")
        file_types = filt.get("fileTypes")
        if isinstance(file_types, list) and file_types:
            type_exprs = []
            for ft in file_types:
                if ft and ft != "*":
                    type_exprs.append(f"mimeType = '{ft}'")
            if type_exprs:
                q_parts.append(f"({' or '.join(type_exprs)})")
    if not include_trashed:
        q_parts.append("trashed = false")

    qs: dict[str, Any] = {
        "q": " and ".join(q_parts) if q_parts else "",
        "fields": f"nextPageToken, files({prepare_query_fields(options.get('fields'))})",
        **shared_drive_query_defaults(),
    }
    update_drive_scopes(qs, drive_id)
    if drive_id == RLC_DRIVE_DEFAULT and folder_id == RLC_FOLDER_DEFAULT:
        qs["corpora"] = "user"
        qs["includeItemsFromAllDrives"] = False
        qs["supportsAllDrives"] = False
        qs["spaces"] = "drive"

    if params.get("returnAll"):
        files = await google_api_request_all_items(
            token, "GET", "/drive/v3/files", "files", query=qs
        )
        return {"files": files}
    qs["pageSize"] = int(params.get("limit") or 50)
    data = await google_api_request(token, "GET", "/drive/v3/files", query=qs)
    return data if isinstance(data, dict) else {"files": []}


# --- file ---


async def _run_file(
    context: "ad.flows.ExecutionContext",
    token: str,
    operation: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    *,
    item_index: int,
) -> dict[str, Any] | "ad.flows.FlowItem":
    options = params.get("options") if isinstance(params.get("options"), dict) else {}
    file_id = drive_file_id_from_param(params.get("fileId"))

    if operation == "copy":
        drive_id = rlc_value(params.get("driveId"), default=RLC_DRIVE_DEFAULT)
        folder_id = rlc_value(params.get("folderId"), default=RLC_FOLDER_DEFAULT)
        parents = (
            []
            if params.get("sameFolder", True)
            else [set_parent_folder(folder_id, drive_id)]
        )
        body: dict[str, Any] = {
            "name": str(params.get("name") or ""),
            "parents": parents,
        }
        if options.get("copyRequiresWriterPermission") is not None:
            body["copyRequiresWriterPermission"] = options["copyRequiresWriterPermission"]
        if options.get("description"):
            body["description"] = options["description"]
        return await google_api_request(
            token,
            "POST",
            f"/drive/v3/files/{file_id}/copy",
            body=body,
            query=shared_drive_query_defaults(),
        )

    if operation == "deleteFile":
        if options.get("deletePermanently"):
            await google_api_request(
                token,
                "DELETE",
                f"/drive/v3/files/{file_id}",
                query={"supportsAllDrives": True},
            )
        else:
            await google_api_request(
                token,
                "PATCH",
                f"/drive/v3/files/{file_id}",
                body={"trashed": True},
                query={"supportsAllDrives": True},
            )
        return {"id": file_id, "success": True}

    if operation == "download":
        return await _file_download(context, token, file_id, params, item, options)

    if operation == "move":
        drive_id = rlc_value(params.get("driveId"), default=RLC_DRIVE_DEFAULT)
        folder_id = rlc_value(params.get("folderId"), default=RLC_FOLDER_DEFAULT)
        meta = await google_api_request(
            token,
            "GET",
            f"/drive/v3/files/{file_id}",
            query={**shared_drive_query_defaults(), "fields": "parents"},
        )
        parents = meta.get("parents") if isinstance(meta, dict) else []
        remove_parents = ",".join(str(p) for p in parents) if isinstance(parents, list) else ""
        qs = {
            **shared_drive_query_defaults(),
            "addParents": set_parent_folder(folder_id, drive_id),
        }
        if remove_parents:
            qs["removeParents"] = remove_parents
        return await google_api_request(
            token, "PATCH", f"/drive/v3/files/{file_id}", query=qs
        )

    if operation == "share":
        perms = permissions_from_ui(params.get("permissionsUi"))
        if not perms:
            raise ValueError("At least one permission is required to share a file")
        qs = share_options_query(options)
        return await google_api_request(
            token,
            "POST",
            f"/drive/v3/files/{file_id}/permissions",
            body=perms[0],
            query=qs,
        )

    if operation == "createFromText":
        return await _file_create_from_text(token, params, options)

    if operation == "upload":
        return await _file_upload(context, token, params, item, options)

    if operation == "update":
        return await _file_update(context, token, file_id, params, item, options)

    raise ValueError(f"Unsupported file operation: {operation}")


async def _file_download(
    context: "ad.flows.ExecutionContext",
    token: str,
    file_id: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    options: dict[str, Any],
) -> "ad.flows.FlowItem":
    meta = await google_api_request(
        token,
        "GET",
        f"/drive/v3/files/{file_id}",
        query={"fields": "mimeType,name", "supportsAllDrives": True},
    )
    mime = str(meta.get("mimeType") or "application/octet-stream")
    name = str(options.get("fileName") or meta.get("name") or "file")
    prop = str(options.get("binaryPropertyName") or "data").strip() or "data"

    if mime.startswith("application/vnd.google-apps."):
        content, out_mime = await google_export_file_bytes(token, file_id, mime, options)
    else:
        content = await google_api_request(
            token,
            "GET",
            f"/drive/v3/files/{file_id}",
            query={"alt": "media", "supportsAllDrives": True},
            expect_json=False,
        )
        out_mime = mime

    if not isinstance(content, bytes):
        content = bytes(content) if content is not None else b""

    binary = dict(item.binary)
    binary[prop] = ad.flows.BinaryRef(
        mime_type=out_mime,
        file_name=name,
        data=content,
    )
    return ad.flows.FlowItem(json=dict(item.json), binary=binary, meta=dict(item.meta))


async def _file_create_from_text(
    token: str, params: dict[str, Any], options: dict[str, Any]
) -> dict[str, Any]:
    content = str(params.get("content") or "")
    name = str(params.get("name") or "Untitled")
    drive_id = rlc_value(params.get("driveId"), default=RLC_DRIVE_DEFAULT)
    folder_id = rlc_value(params.get("folderId"), default=RLC_FOLDER_DEFAULT)
    parent = set_parent_folder(folder_id, drive_id)

    if options.get("convertToGoogleDocument"):
        body = {
            "name": name,
            "mimeType": "application/vnd.google-apps.document",
            "parents": [parent],
        }
        body = set_file_properties(body, options)
        created = await google_api_request(
            token,
            "POST",
            "/drive/v3/files",
            body=body,
            query=shared_drive_query_defaults(),
        )
        doc_id = str(created.get("id") or "")
        await google_api_request(
            token,
            "POST",
            "",
            body={
                "requests": [
                    {
                        "insertText": {
                            "text": content,
                            "endOfSegmentLocation": {"segmentId": ""},
                        }
                    }
                ]
            },
            url=f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
        )
        return {"id": doc_id}

    metadata = {
        "name": name,
        "parents": [parent],
    }
    upload = await upload_multipart_file(
        token,
        metadata,
        content.encode("utf-8"),
        "text/plain",
    )
    upload_id = str(upload.get("id") or "")
    patch_body = set_file_properties(
        {"mimeType": "text/plain", "name": name},
        options,
    )
    qs = {
        **shared_drive_query_defaults(),
        "addParents": parent,
    }
    qs = set_update_common_params(qs, options)
    await google_api_request(token, "PATCH", f"/drive/v3/files/{upload_id}", body=patch_body, query=qs)
    return {"id": upload_id}


async def _read_input_binary(
    context: "ad.flows.ExecutionContext",
    item: "ad.flows.FlowItem",
    field_name: str,
) -> tuple[bytes, str, str]:
    prop = field_name.strip() or "data"
    ref = item.binary.get(prop)
    if ref is None:
        raise RuntimeError(f"Google Drive expected item.binary[{prop!r}] but it was missing")
    if context.analytiq_client is None:
        if getattr(ref, "data", None) is not None:
            data = ref.data if isinstance(ref.data, bytes) else bytes(ref.data)
            return (
                data,
                str(getattr(ref, "file_name", None) or "file"),
                str(getattr(ref, "mime_type", None) or "application/octet-stream"),
            )
        raise RuntimeError("Google Drive binary upload requires analytiq_client on the execution context")
    blob = await ad.flows.get_binary_stream(ref, context.analytiq_client)
    return (
        blob,
        str(getattr(ref, "file_name", None) or "file"),
        str(getattr(ref, "mime_type", None) or "application/octet-stream"),
    )


async def _file_upload(
    context: "ad.flows.ExecutionContext",
    token: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    options: dict[str, Any],
) -> dict[str, Any]:
    field = str(params.get("inputDataFieldName") or "data")
    data, original_name, mime_type = await _read_input_binary(context, item, field)
    name = str(params.get("name") or "").strip() or original_name
    drive_id = rlc_value(params.get("driveId"), default=RLC_DRIVE_DEFAULT)
    folder_id = rlc_value(params.get("folderId"), default=RLC_FOLDER_DEFAULT)
    metadata = {"name": name, "parents": [set_parent_folder(folder_id, drive_id)]}

    if len(data) <= 5 * 1024 * 1024:
        upload = await upload_multipart_file(token, metadata, data, mime_type)
        upload_id = str(upload.get("id") or "")
    else:
        upload_id = await resumable_upload(token, metadata, data, mime_type)

    qs = {**shared_drive_query_defaults(), "addParents": set_parent_folder(folder_id, drive_id)}
    qs = set_update_common_params(qs, options)
    if not options.get("simplifyOutput", True):
        qs["fields"] = "*"
    patch_body = set_file_properties(
        {"mimeType": mime_type, "name": name, "originalFilename": original_name},
        options,
    )
    return await google_api_request(
        token, "PATCH", f"/drive/v3/files/{upload_id}", body=patch_body, query=qs
    )


async def _file_update(
    context: "ad.flows.ExecutionContext",
    token: str,
    file_id: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    options: dict[str, Any],
) -> dict[str, Any]:
    qs = {**shared_drive_query_defaults(), "supportsAllDrives": True}
    qs = set_update_common_params(qs, options)
    fields = options.get("fields")
    if fields:
        qs["fields"] = prepare_query_fields(fields)
    if options.get("trashed") is not None:
        qs["trashed"] = options["trashed"]

    if params.get("changeFileContent"):
        field = str(params.get("inputDataFieldName") or "data")
        data, original_name, mime_type = await _read_input_binary(context, item, field)
        await google_api_request(
            token,
            "PATCH",
            f"/upload/drive/v3/files/{file_id}",
            body=data,
            query={"uploadType": "media", "supportsAllDrives": True},
            headers={"Content-Type": mime_type},
        )
        new_name = str(params.get("newUpdatedFileName") or "").strip()
        body = set_file_properties(
            {
                "mimeType": mime_type,
                "name": new_name or original_name,
                "originalFilename": original_name,
            },
            options,
        )
    else:
        body = set_file_properties({}, options)
        new_name = str(params.get("newUpdatedFileName") or "").strip()
        if new_name:
            body["name"] = new_name

    return await google_api_request(token, "PATCH", f"/drive/v3/files/{file_id}", body=body, query=qs)
