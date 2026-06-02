"""Microsoft Graph helpers shared by Outlook, OneDrive, Teams, Excel, etc."""

from .drive_helpers import (
    encoded_drive_item_content_path,
    normalize_drive_item_id,
    search_query_path,
    simplify_drive_item,
)
from .graph_api import (
    GRAPH_DRIVE_DELTA_LATEST,
    GRAPH_DRIVE_DELTA_ROOT,
    GRAPH_ME,
    GRAPH_ROOT,
    MicrosoftGraphApiError,
    format_graph_user_error,
    get_drive_folder_path,
    graph_mailbox_base_url,
    graph_request,
    graph_request_all_items,
    graph_request_all_items_delta,
    graph_request_with_response,
    graph_url_for_path,
    graph_user_hint,
    resolve_graph_oauth_token,
)

__all__ = [
    "GRAPH_DRIVE_DELTA_LATEST",
    "GRAPH_DRIVE_DELTA_ROOT",
    "GRAPH_ME",
    "GRAPH_ROOT",
    "MicrosoftGraphApiError",
    "graph_mailbox_base_url",
    "graph_url_for_path",
    "format_graph_user_error",
    "get_drive_folder_path",
    "graph_user_hint",
    "graph_request",
    "graph_request_all_items",
    "graph_request_all_items_delta",
    "graph_request_with_response",
    "encoded_drive_item_content_path",
    "normalize_drive_item_id",
    "resolve_graph_oauth_token",
    "search_query_path",
    "simplify_drive_item",
]
