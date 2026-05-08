// Flow engine types (v1)

/** Declares an optional credential binding slot on a node type (`GET .../flows/node-types`). */
export interface FlowCredentialSlot {
  slot: string;
  label: string;
  required?: boolean;
  docrouter_binding?: string;
}

export interface FlowNodeType {
  key: string;
  label: string;
  description: string;
  category: string;
  /** Backend preset mapped to bundled Heroicons (`null`/omit → generic process/trigger glyph). */
  icon_key?: string | null;
  is_trigger: boolean;
  min_inputs: number;
  max_inputs: number | null;
  outputs: number;
  output_labels: string[];
  parameter_schema: Record<string, unknown>;
  credential_slots?: FlowCredentialSlot[];
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
  notes?: string | null;
  webhook_id?: string | null;
  /** Credential slot name → saved org credential id (see `FlowCredentialSlot`). */
  credentials?: Record<string, string>;
}

export interface FlowNodeConnection {
  dest_node_id: string;
  connection_type: 'main';
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
}

export interface ListFlowsResponse {
  items: FlowListItem[];
  total: number;
}

export interface ListRevisionsResponse {
  items: FlowRevisionSummary[];
  total: number;
}

export type FlowExecutionStatus = 'queued' | 'running' | 'success' | 'error' | 'stopped';

export interface FlowExecution {
  execution_id: string;
  flow_id: string;
  flow_revid: string;
  organization_id: string;
  mode: string;
  status: FlowExecutionStatus;
  started_at: string;
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
}

export interface ListExecutionsResponse {
  items: FlowExecution[];
  total: number;
}

export interface CreateFlowParams {
  name: string;
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
}

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
}

/** Saved org credential metadata (no secrets) from `GET .../credentials`. */
export interface FlowCredentialHeader {
  credential_id: string;
  organization_id: string;
  kind_key: string;
  name: string;
  public_fields: Record<string, unknown>;
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

