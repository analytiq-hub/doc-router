// Flow engine types (v1)

/** Declares an optional credential binding slot on a node type (`GET .../flows/node-types`). */
export interface FlowCredentialSlot {
  slot: string;
  label: string;
  required?: boolean;
  docrouter_binding?: string;
}

export type FlowConnectionType = 'main' | 'docrouter.ocr' | 'flows.tool';

export interface FlowNodeType {
  key: string;
  label: string;
  description: string;
  category: string;
  /** Palette section in Flow editor: `docrouter` | `app` | `flow` | `core` | `trigger`. */
  palette_group?: string;
  /** Backend preset mapped to bundled Heroicons (`null`/omit → generic process/trigger glyph). */
  icon_key?: string | null;
  is_trigger: boolean;
  min_inputs: number;
  max_inputs: number | null;
  outputs: number;
  output_labels: string[];
  /** Connection type accepted by each input port (defaults to `main`). */
  input_port_types?: FlowConnectionType[];
  /** Connection type emitted by each output port (defaults to `main`). */
  output_port_types?: FlowConnectionType[];
  parameter_schema: Record<string, unknown>;
  credential_slots?: FlowCredentialSlot[];
  /** Requires organization `experimental_features` to list this node type. */
  experimental?: boolean;
  /** Poll trigger: platform calls poll() on schedule ticks. */
  polling?: boolean;
  /** When true, the engine passes all input items in one ``execute()`` call. */
  batch_execute_inputs?: boolean;
  /** When true, the node settings UI exposes per-node ``batch_size`` parallelism. */
  supports_batch_size?: boolean;
  /** Emits flows.tool connections; skipped on the main DAG. */
  tool_provider?: boolean;
  /** Accepts flows.tool wires (agent, tool executor). */
  tool_consumer?: boolean;
  is_merge?: boolean;
}

export interface ListNodeTypesResponse {
  items: FlowNodeType[];
  total: number;
}

export interface FlowHeader {
  flow_id: string;
  organization_id: string;
  name: string;
  active: boolean;
  active_flow_revid: string | null;
  flow_version: number;
  folder_id?: string | null;
  sort_order?: number;
  callable_as_tool?: boolean;
  tool_description?: string | null;
  tool_schema?: Record<string, unknown> | null;
  created_at: string;
  created_by: string;
  updated_at: string;
  updated_by: string;
}

export interface FlowRevisionSummary {
  flow_revid: string;
  flow_version: number;
  graph_hash: string;
  created_at?: string;
  created_by?: string;
}

export interface FlowNode {
  id: string;
  name: string;
  type: string;
  position: [number, number];
  parameters: Record<string, unknown>;
  disabled?: boolean;
  on_error?: 'stop' | 'continue';
  /** Max input items processed concurrently per node (default 1, range 1–256). */
  batch_size?: number;
  notes?: string | null;
  webhook_id?: string | null;
  /** Credential slot name → saved org credential id (see `FlowCredentialSlot`). */
  credentials?: Record<string, string>;
}

export interface FlowNodeConnection {
  dest_node_id: string;
  connection_type: FlowConnectionType;
  index: number;
}

export type FlowConnections = Record<string, { main: Array<FlowNodeConnection[] | null> }>;

export interface FlowBinaryRef {
  mime_type: string;
  file_name?: string | null;
  storage_id?: string | null;
  file_size?: number | null;
}

export type FlowPinItem = { json: unknown; binary?: Record<string, FlowBinaryRef> };

/** Pinned output for a single node, keyed like engine `data.main`. */
export type FlowPinNodeOutput = {
  main: Array<FlowPinItem[] | null>;
};

/** Revision-level pin data, keyed by **node id**. */
export type FlowPinData = Record<string, FlowPinNodeOutput>;

export interface FlowRevision extends FlowRevisionSummary {
  flow_id: string;
  nodes: FlowNode[];
  connections: FlowConnections;
  settings: Record<string, unknown>;
  pin_data: FlowPinData | null;
  engine_version: number;
}

export interface FlowListItem {
  flow: FlowHeader;
  latest_revision: FlowRevisionSummary | null;
  /** Present when listing flows with ``document_id`` filter. */
  event_type?: string | null;
  /** Present when listing flows with ``document_id`` filter. */
  has_captured_result?: boolean;
}

export interface FlowDocumentResult {
  flow_id: string;
  flow_name: string;
  flow_revid?: string | null;
  /** Revision version that produced the captured result (from the execution's flow_revid). */
  flow_version?: number | null;
  document_id: string;
  execution_id?: string;
  event_type?: string | null;
  result?: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ListFlowsResponse {
  items: FlowListItem[];
  total: number;
}

export interface ListRevisionsResponse {
  items: FlowRevisionSummary[];
  total: number;
}

export type FlowExecutionStatus = 'queued' | 'running' | 'success' | 'error' | 'stopped' | 'interrupted';

export interface FlowExecution {
  execution_id: string;
  flow_id: string;
  flow_revid: string;
  organization_id: string;
  mode: string;
  status: FlowExecutionStatus;
  started_at: string | null;
  finished_at: string | null;
  last_heartbeat_at: string | null;
  stop_requested: boolean;
  last_node_executed: string | null;
  run_data: Record<string, unknown>;
  error: Record<string, unknown> | null;
  trigger: Record<string, unknown>;
  /** Populated on org-wide execution list responses when the flow header exists. */
  flow_name?: string | null;
  /** Trigger node that seeded the run (multi-trigger graphs and webhooks). */
  start_trigger_node_id?: string | null;
  /** Set for execute-step / partial manual runs. */
  target_node_id?: string | null;
  /** Client-supplied seed snapshot at queue time (optional). */
  initial_run_data?: Record<string, unknown> | null;
  /** Node ids with persisted checkpoints (resume skips these). */
  completed_nodes?: string[];
  /** Source execution when this run resumed from a checkpoint. */
  resumed_from?: string | null;
  /** Child execution id when this run was resumed. */
  resumed_by?: string | null;
}

/** Per-node or execution-level failure envelope (`docs/docrouter_fulltrace.md`). */
export interface FlowNodeRunError {
  message: string;
  node_id?: string | null;
  node_name?: string | null;
  stack?: string | null;
  cause?: string | null;
  http_code?: number | null;
}

export interface FlowTraceEvent {
  ts?: string;
  level?: string;
  kind?: string;
  message?: string;
  detail?: Record<string, unknown>;
}

export interface FlowNodeRunData {
  status?: string;
  start_time?: string;
  execution_time_ms?: number;
  execution_index?: number;
  data?: Record<string, unknown>;
  error?: FlowNodeRunError | null;
  /** Per input slot: upstream provenance (outer index = slot). */
  source?: FlowSourceRef[][];
  logs?: string[];
  trace?: FlowTraceEvent[];
}

export interface FlowSourceRef {
  previous_node_id: string;
  previous_node_output?: number;
  previous_node_run?: number;
}

export interface ListExecutionsResponse {
  items: FlowExecution[];
  total: number;
}

export interface CreateFlowParams {
  name: string;
  /** When provided with the graph, persists the first revision in the same request as header creation. */
  nodes?: FlowNode[];
  connections?: FlowConnections;
  settings?: Record<string, unknown>;
  pin_data?: FlowPinData | null;
}

export interface SaveRevisionParams {
  base_flow_revid: string;
  name: string;
  nodes: FlowNode[];
  connections: FlowConnections;
  settings?: Record<string, unknown>;
  pin_data?: FlowPinData | null;
}

/** Graph sent with `POST .../run` to execute the editor state without saving (test run from editor). */
export type RevisionSnapshotPayload = Pick<SaveRevisionParams, 'nodes' | 'connections' | 'settings' | 'pin_data'>;

export interface RunFlowParams {
  flow_revid?: string;
  document_id?: string;
  /** When the graph has several triggers, selects which one seeds a full manual run. */
  start_trigger_node_id?: string;
  /** Run only upstream subgraph through this node id (execute step). */
  target_node_id?: string;
  /** Prior `run_data` entries to reuse (validated); requires `target_node_id`. */
  run_data?: Record<string, unknown>;
  /** Node ids to force re-run even if present in `run_data`. */
  dirty_node_ids?: string[];
  /** When set, this graph is executed; `flow_revid` is lineage only (expressions / UI), not the source of truth for the run. */
  revision_snapshot?: RevisionSnapshotPayload;
  /** Path B: execute-step on a tool_provider with synthetic Tool Executor rewire. */
  tool_test_request?: FlowToolTestRequest;
}

/** Arguments for Path B tool execute-step (`rewire_graph_for_tool_test`). */
export interface FlowToolTestRequest {
  tool_name: string;
  arguments: Record<string, unknown>;
}

/** POST body for editor Chat Trigger test (`…/flows/{id}/chat/test`). */
export interface FlowChatTestRequest {
  chatInput: string;
  sessionId?: string | null;
  flow_revid?: string | null;
  revision_snapshot: RevisionSnapshotPayload;
}

/** Buffered Chat Trigger response (`response_mode: last_node`). */
export interface FlowChatBufferedResponse {
  text: string;
  session_id: string;
  execution_id: string;
}

/** NDJSON stream events from Chat Trigger + agent (`response_mode: streaming`). */
export type FlowChatStreamEvent =
  | { type: 'meta'; execution_id: string; session_id?: string }
  | { type: 'begin'; round: number }
  | { type: 'content'; round: number; chunk: string }
  | { type: 'thinking'; round: number; chunk: string }
  | { type: 'tool_call'; round: number; tool: string; arguments?: Record<string, unknown> }
  | { type: 'tool_result'; round: number; tool: string; preview?: string; success?: boolean }
  | { type: 'end'; text: string; rounds_used?: number; execution_id?: string; session_id?: string }
  | { type: 'error'; message: string };

export interface PreviewFlowExpressionParams {
  expression: string;
  run_data?: Record<string, unknown>;
  /** Inbound slot 0 rows (plain objects), same shape as the editor INPUT tab. */
  input_items?: Record<string, unknown>[];
  preview_item_index?: number;
  execution_refs?: Record<string, string | undefined>;
  /** Revision nodes for name-keyed `_node` in expressions (same shape as flow revision `nodes`). */
  nodes?: Record<string, unknown>[];
}

export interface PreviewFlowExpressionResponse {
  skipped: boolean;
  ok: boolean;
  preview_text?: string | null;
  value?: unknown;
  error?: string | null;
}

/** One credential kind from `GET .../credential-kinds`. */
export interface FlowCredentialKindSummary {
  key: string;
  display_name: string;
  auth_mode: string;
  fields: Array<Record<string, unknown>>;
  /** True when the kind defines `test_request` (connection test in UI). */
  has_test_request?: boolean;
  /** OAuth2 authorization-code browser redirect (Connect in UI). */
  supports_oauth_browser_flow?: boolean;
  /** Redirect URI to register with the OAuth provider (when browser flow is supported). */
  oauth_redirect_uri?: string | null;
  /** Kind defines `pre_auth` (session bootstrap before inject). */
  has_pre_auth?: boolean;
  /** Requires organization `experimental_features` to list this kind. */
  experimental?: boolean;
}

/** Saved org credential metadata (no secrets) from `GET .../credentials`. */
export interface FlowCredentialHeader {
  credential_id: string;
  organization_id: string;
  kind_key: string;
  name: string;
  public_fields: Record<string, unknown>;
  /** Secret field names with a stored value (secrets are never returned). */
  secret_fields_set?: string[];
  created_at: string;
  created_by: string;
  updated_at: string;
  updated_by: string;
}

export interface ListFlowCredentialsResponse {
  items: FlowCredentialHeader[];
  total: number;
}

export interface CreateFlowCredentialParams {
  kind_key: string;
  name: string;
  fields: Record<string, unknown>;
}

export interface UpdateFlowCredentialParams {
  name: string;
  fields: Record<string, unknown>;
}

/** Response from `POST .../credentials/{id}/test`. */
export interface TestFlowCredentialResponse {
  ok: boolean;
  status_code?: number | null;
  error?: string | null;
}

