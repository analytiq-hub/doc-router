"""SharePoint REST v2.0 operations for ``flows.microsoft_sharepoint``."""

from __future__ import annotations

from typing import Any

import analytiq_data as ad

from analytiq_data.flows.integrations.microsoft import (
    graph_request,
    graph_request_all_items,
    graph_request_with_response,
    sharepoint_rest_api_base,
    sharepoint_tenant_rest_api_base,
    site_encoded_drive_item_content_path,
    site_search_query_path,
)

from .api import resolve_oauth_access_token, resolve_sharepoint_subdomain
from .helpers import (
    sharepoint_item_id,
    sharepoint_site_id,
    validate_resource_operation,
)


async def _site_base(
    context: "ad.flows.ExecutionContext",
    node: dict[str, Any],
    params: dict[str, Any],
) -> str:
    subdomain = await resolve_sharepoint_subdomain(context, node)
    return sharepoint_rest_api_base(subdomain, sharepoint_site_id(params))


async def _graph(
    context: "ad.flows.ExecutionContext",
    token: str,
    site_base: str,
    method: str,
    path: str,
    **kwargs: Any,
) -> Any:
    return await graph_request(
        token,
        method,
        path,
        mailbox_base=site_base,
        context=context,
        trace_node_id=context.active_trace_node_id,
        **kwargs,
    )


async def execute_microsoft_sharepoint_item(
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
    site_base = await _site_base(context, node, params)

    if resource == "file":
        data = await _run_file(
            context, token, site_base, operation, params, item, item_index=item_index
        )
    elif resource == "folder":
        data = await _run_folder(context, token, site_base, operation, params)
    elif resource == "list":
        data = await _run_list(context, token, site_base, operation, params)
    else:
        data = await _run_site(context, node, token, site_base, operation, params)

    if isinstance(data, ad.flows.FlowItem):
        return data
    return ad.flows.FlowItem(
        json=data if isinstance(data, dict) else {"data": data},
        binary=dict(item.binary),
        meta=dict(item.meta),
    )


async def _run_site(
    context: "ad.flows.ExecutionContext",
    node: dict[str, Any],
    token: str,
    site_base: str,
    operation: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    if operation == "get":
        return await graph_request(
            token,
            "GET",
            "",
            url=site_base,
            context=context,
            trace_node_id=context.active_trace_node_id,
        )

    if operation == "search":
        query = str(params.get("query") or "")
        subdomain = await resolve_sharepoint_subdomain(context, node)
        tenant_base = sharepoint_tenant_rest_api_base(subdomain)
        items = await graph_request_all_items(
            context,
            token,
            "GET",
            "/sites",
            query={"search": query},
            mailbox_base=tenant_base,
            trace_node_id=context.active_trace_node_id,
        )
        return {"value": items}

    raise ValueError(f"Unsupported site operation: {operation}")


async def _run_list(
    context: "ad.flows.ExecutionContext",
    token: str,
    site_base: str,
    operation: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    list_id = str(params.get("listId") or "").strip()

    if operation == "getMany":
        items = await graph_request_all_items(
            context,
            token,
            "GET",
            "/lists",
            mailbox_base=site_base,
            trace_node_id=context.active_trace_node_id,
        )
        return {"value": items}

    if not list_id:
        raise RuntimeError("listId is required for this list operation.")

    if operation == "get":
        return await _graph(context, token, site_base, "GET", f"/lists/{list_id}")

    if operation == "getItems":
        items = await graph_request_all_items(
            context,
            token,
            "GET",
            f"/lists/{list_id}/items",
            mailbox_base=site_base,
            trace_node_id=context.active_trace_node_id,
        )
        return {"value": items}

    raise ValueError(f"Unsupported list operation: {operation}")


async def _run_file(
    context: "ad.flows.ExecutionContext",
    token: str,
    site_base: str,
    operation: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    *,
    item_index: int,
) -> dict[str, Any] | "ad.flows.FlowItem":
    if operation == "copy":
        file_id = sharepoint_item_id(params, "fileId")
        additional = (
            params.get("additionalFields")
            if isinstance(params.get("additionalFields"), dict)
            else {}
        )
        parent_ref = (
            params.get("parentReference")
            if isinstance(params.get("parentReference"), dict)
            else {}
        )
        body: dict[str, Any] = {}
        if parent_ref:
            body["parentReference"] = dict(parent_ref)
        if additional.get("name"):
            body["name"] = additional["name"]
        resp = await graph_request_with_response(
            token,
            "POST",
            f"/drive/items/{file_id}/copy",
            body=body,
            mailbox_base=site_base,
            context=context,
            trace_node_id=context.active_trace_node_id,
        )
        location = resp.headers.get("location") or resp.headers.get("Location")
        return {"location": location}

    if operation == "delete":
        file_id = sharepoint_item_id(params, "fileId")
        await _graph(context, token, site_base, "DELETE", f"/drive/items/{file_id}")
        return {"success": True}

    if operation == "download":
        return await _file_download(context, token, site_base, params, item)

    if operation == "get":
        file_id = sharepoint_item_id(params, "fileId")
        return await _graph(context, token, site_base, "GET", f"/drive/items/{file_id}")

    if operation == "search":
        query = str(params.get("query") or "")
        items = await graph_request_all_items(
            context,
            token,
            "GET",
            site_search_query_path(query),
            mailbox_base=site_base,
            trace_node_id=context.active_trace_node_id,
        )
        return {"value": [x for x in items if x.get("file")]}

    if operation == "share":
        file_id = sharepoint_item_id(params, "fileId")
        body = {
            "type": str(params.get("type") or "view"),
            "scope": str(params.get("scope") or "anonymous"),
        }
        return await _graph(
            context,
            token,
            site_base,
            "POST",
            f"/drive/items/{file_id}/createLink",
            body=body,
        )

    if operation == "upload":
        return await _file_upload(
            context, token, site_base, params, item, item_index=item_index
        )

    if operation == "rename":
        return await _rename_item(context, token, site_base, params)

    raise ValueError(f"Unsupported file operation: {operation}")


async def _run_folder(
    context: "ad.flows.ExecutionContext",
    token: str,
    site_base: str,
    operation: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    if operation == "create":
        names = [s for s in str(params.get("name") or "").split("/") if s.strip()]
        options = params.get("options") if isinstance(params.get("options"), dict) else {}
        parent_folder_id = sharepoint_item_id(options, "parentFolderId") or None
        last: dict[str, Any] = {}
        for name in names:
            body: dict[str, Any] = {"name": name, "folder": {}}
            endpoint = "/drive/root/children"
            if parent_folder_id:
                endpoint = f"/drive/items/{parent_folder_id}/children"
            last = await _graph(context, token, site_base, "POST", endpoint, body=body)
            if not last.get("id"):
                break
            parent_folder_id = last.get("id")
        return last

    if operation == "delete":
        folder_id = sharepoint_item_id(params, "folderId")
        await _graph(context, token, site_base, "DELETE", f"/drive/items/{folder_id}")
        return {"success": True}

    if operation == "getChildren":
        folder_id = sharepoint_item_id(params, "folderId")
        endpoint = (
            f"/drive/items/{folder_id}/children"
            if folder_id
            else "/drive/root/children"
        )
        items = await graph_request_all_items(
            context,
            token,
            "GET",
            endpoint,
            mailbox_base=site_base,
            trace_node_id=context.active_trace_node_id,
        )
        return {"value": items}

    if operation == "search":
        query = str(params.get("query") or "")
        items = await graph_request_all_items(
            context,
            token,
            "GET",
            site_search_query_path(query),
            mailbox_base=site_base,
            trace_node_id=context.active_trace_node_id,
        )
        return {"value": [x for x in items if x.get("folder")]}

    if operation == "share":
        folder_id = sharepoint_item_id(params, "folderId")
        body = {
            "type": str(params.get("type") or "view"),
            "scope": str(params.get("scope") or "anonymous"),
        }
        return await _graph(
            context,
            token,
            site_base,
            "POST",
            f"/drive/items/{folder_id}/createLink",
            body=body,
        )

    if operation == "rename":
        return await _rename_item(context, token, site_base, params)

    raise ValueError(f"Unsupported folder operation: {operation}")


async def _rename_item(
    context: "ad.flows.ExecutionContext",
    token: str,
    site_base: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    item_id = sharepoint_item_id(params, "itemId")
    new_name = str(params.get("newName") or "")
    return await _graph(
        context,
        token,
        site_base,
        "PATCH",
        f"/drive/items/{item_id}",
        body={"name": new_name},
    )


async def _file_download(
    context: "ad.flows.ExecutionContext",
    token: str,
    site_base: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
) -> "ad.flows.FlowItem":
    file_id = sharepoint_item_id(params, "fileId")
    prop = str(params.get("binaryPropertyName") or "data").strip() or "data"
    meta = await _graph(context, token, site_base, "GET", f"/drive/items/{file_id}")
    if not isinstance(meta, dict) or meta.get("file") is None:
        raise RuntimeError("The ID you provided does not belong to a file.")
    file_name = str(meta.get("name") or "file")
    mime_type = str((meta.get("file") or {}).get("mimeType") or "application/octet-stream")
    content = await _graph(
        context,
        token,
        site_base,
        "GET",
        f"/drive/items/{file_id}/content",
        expect_json=False,
    )
    if not isinstance(content, bytes):
        content = bytes(content) if content is not None else b""
    binary = dict(item.binary)
    binary[prop] = ad.flows.BinaryRef(
        mime_type=mime_type,
        file_name=file_name,
        data=content,
    )
    return ad.flows.FlowItem(json=dict(item.json), binary=binary, meta=dict(item.meta))


async def _file_upload(
    context: "ad.flows.ExecutionContext",
    token: str,
    site_base: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    *,
    item_index: int,
) -> dict[str, Any]:
    parent_id = sharepoint_item_id(params, "parentId")
    file_name = str(params.get("fileName") or "")
    use_binary = bool(params.get("binaryData"))

    if use_binary:
        prop = str(params.get("binaryPropertyName") or "data").strip() or "data"
        data, upload_name, mime_type = await _read_input_binary(
            context, item, prop, file_name, item_index=item_index
        )
    else:
        upload_name = file_name
        if not upload_name:
            raise RuntimeError("File name must be set when not using binary data.")
        data = str(params.get("fileContent") or "").encode("utf-8")
        mime_type = "text/plain"

    path = site_encoded_drive_item_content_path(parent_id, upload_name)
    headers = {
        "Content-Type": mime_type,
        "Content-Length": str(len(data)),
    }
    return await _graph(
        context,
        token,
        site_base,
        "PUT",
        path,
        body=data,
        headers=headers,
    )


async def _read_input_binary(
    context: "ad.flows.ExecutionContext",
    item: "ad.flows.FlowItem",
    prop: str,
    file_name: str,
    *,
    item_index: int,
) -> tuple[bytes, str, str]:
    ref = item.binary.get(prop)
    if ref is None:
        raise RuntimeError(
            f"Microsoft SharePoint expected item.binary[{prop!r}] but it was missing "
            f"(item index {item_index})."
        )
    if ref.data is not None:
        blob = ref.data if isinstance(ref.data, bytes) else bytes(ref.data)
    elif ref.storage_id and context.analytiq_client is not None:
        blob = await ad.flows.get_binary_stream(ref, context.analytiq_client)
    else:
        raise RuntimeError("Microsoft SharePoint binary upload requires item binary data.")
    upload_name = file_name or ref.file_name or "upload"
    mime_type = ref.mime_type or "application/octet-stream"
    return blob, upload_name, mime_type
