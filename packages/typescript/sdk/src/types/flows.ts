// Flow engine types (v1)

export interface FlowNodeType {
  key: string;
  label: string;
  description: string;
  category: string;
  is_trigger: boolean;
  min_inputs: number;
  max_inputs: number | null;
  outputs: number;
  output_labels: string[];
  parameter_schema: Record<string, unknown>;
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
}

export interface FlowNodeConnection {
  dest_node_id: string;
  connection_type: 'main';
  index: number;
}

export type FlowConnections = Record<string, { main: Array<FlowNodeConnection[] | null> }>;

export interface FlowRevision extends FlowRevisionSummary {
  flow_id: string;
  nodes: FlowNode[];
  connections: FlowConnections;
  settings: Record<string, unknown>;
  pin_data: Record<string, unknown> | null;
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
  pin_data?: Record<string, unknown> | null;
}

export interface RunFlowParams {
  flow_revid?: string;
  document_id?: string;
}

