import React, { useCallback, useState, useEffect } from 'react';
import ReactFlow, {
  Controls,
  Background,
  Connection,
  Edge,
  addEdge,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';

import FileInputNode from '@/components/flow-nodes/FileInputNode';
import PromptNode from '@/components/flow-nodes/PromptNode';
import LLMOutputNode from '@/components/flow-nodes/LLMOutputNode';
import { FlowNodeType, NodeData } from '@/types/flows';
import { Prompt } from '@/types/prompts';
import { useFlowContext } from '@/contexts/FlowContext';
import { getPromptsApi, runLLMAnalysisApi } from '@/utils/api';

const initialNodes = [
  {
    id: 'file-1',
    type: 'fileInput',
    position: { x: 100, y: 100 },
    data: { 
      label: 'Contract Excel',
      accept: ['.xlsx', '.xls'],
      required: true 
    },
  },
  {
    id: 'prompt-1',
    type: 'prompt',
    position: { x: 400, y: 100 },
    data: { label: 'Validation Prompt' },
  },
  {
    id: 'output-1',
    type: 'llmOutput',
    position: { x: 700, y: 100 },
    data: { label: 'Validation Results' },
  },
];

const initialEdges = [
  { id: 'e1-2', source: 'file-1', target: 'prompt-1' },
  { id: 'e2-3', source: 'prompt-1', target: 'output-1' },
];

const Flows: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [isExecuting, setIsExecuting] = useState(false);
  const { nodeData, updateNodeData, clearNodeData } = useFlowContext();
  const [prompts, setPrompts] = useState<Prompt[]>([]);

  useEffect(() => {
    // Load available prompts
    const loadPrompts = async () => {
      try {
        const response = await getPromptsApi();
        setPrompts(response.prompts);
      } catch (error) {
        console.error('Error loading prompts:', error);
      }
    };
    loadPrompts();
  }, []);

  const onConnect = useCallback(
    (params: Connection) => {
      // Validate connection
      const sourceNode = nodes.find(n => n.id === params.source);
      const targetNode = nodes.find(n => n.id === params.target);
      
      if (!sourceNode || !targetNode) return;
      
      // Prevent cycles
      if (hasPath(edges, params.target, params.source)) {
        alert('Cannot create cyclic dependencies');
        return;
      }
      
      setEdges((eds) => addEdge(params, eds));
    },
    [setEdges, nodes, edges]
  );

  const hasPath = (edges: Edge[], from: string, to: string, visited = new Set<string>()): boolean => {
    if (from === to) return true;
    if (visited.has(from)) return false;
    
    visited.add(from);
    return edges.some(edge => 
      edge.source === from && hasPath(edges, edge.target, to, visited)
    );
  };

  const executeFlow = async () => {
    setIsExecuting(true);
    try {
      const sortedNodes = topologicalSort(nodes, edges);
      
      // Execute nodes in order
      for (const node of sortedNodes) {
        await executeNode(node);
      }
    } catch (error) {
      console.error('Flow execution failed:', error);
      alert('Flow execution failed: ' + (error as Error).message);
    } finally {
      setIsExecuting(false);
    }
  };

  const executeNode = async (node: { id: string; type: string; data: NodeData }) => {
    try {
      // Get input nodes for this node
      const inputEdges = edges.filter(e => e.target === node.id);
      const inputData = inputEdges.map(edge => nodeData[edge.source]);

      switch (node.type) {
        case 'fileInput': {
          if (!node.data.file) {
            throw new Error(`File not selected for node ${node.data.label}`);
          }
          
          // Read file content
          const content = await readFileContent(node.data.file);
          updateNodeData(node.id, {
            content,
            type: node.data.file.type,
            name: node.data.file.name
          });
          break;
        }

        case 'prompt': {
          if (!node.data.promptId) {
            throw new Error(`Prompt not selected for node ${node.data.label}`);
          }

          // Combine all input data into context
          const context = inputData.reduce((acc, input) => ({
            ...acc,
            ...input
          }), {});

          // Run LLM analysis with context
          const result = await runLLMAnalysisApi(
            context.documentId, 
            node.data.promptId,
            true,
            context
          );

          updateNodeData(node.id, result);
          break;
        }

        case 'llmOutput': {
          // Combine all input results
          const result = inputData.reduce((acc, input) => ({
            ...acc,
            ...input
          }), {});

          // Update node display
          setNodes(nds => 
            nds.map(n => 
              n.id === node.id 
                ? { ...n, data: { ...n.data, result } }
                : n
            )
          );

          updateNodeData(node.id, result);
          break;
        }
      }
    } catch (error) {
      console.error(`Error executing node ${node.id}:`, error);
      throw error;
    }
  };

  const readFileContent = async (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onload = (e) => {
        resolve(e.target?.result as string);
      };
      
      reader.onerror = (e) => {
        reject(new Error('Error reading file'));
      };

      if (file.type === 'application/json') {
        reader.readAsText(file);
      } else if (file.type.includes('spreadsheet') || file.type.includes('excel')) {
        // For Excel files, we'll need to use a library like xlsx
        // This is a placeholder for now
        reader.readAsArrayBuffer(file);
      } else {
        reader.readAsDataURL(file);
      }
    });
  };

  const handlePromptSelect = useCallback((nodeId: string, promptId: string) => {
    const selectedPrompt = prompts.find(p => p.id === promptId);
    setNodes(nds => 
      nds.map(n => 
        n.id === nodeId 
          ? { 
              ...n, 
              data: { 
                ...n.data, 
                promptId,
                promptName: selectedPrompt?.name 
              } 
            }
          : n
      )
    );
  }, [setNodes, prompts]);

  const handleFileSelect = useCallback((nodeId: string, file: File) => {
    setNodes(nds => 
      nds.map(n => 
        n.id === nodeId 
          ? { ...n, data: { ...n.data, file } }
          : n
      )
    );
  }, [setNodes]);

  const nodeTypes = {
    fileInput: (props: any) => <FileInputNode {...props} handleFileSelect={handleFileSelect} />,
    prompt: (props: any) => <PromptNode {...props} prompts={prompts} handlePromptSelect={handlePromptSelect} />,
    llmOutput: LLMOutputNode,
  };

  const topologicalSort = (nodes: any[], edges: Edge[]) => {
    const sorted: any[] = [];
    const visited = new Set<string>();
    const temp = new Set<string>();

    const visit = (nodeId: string) => {
      if (temp.has(nodeId)) throw new Error('Cyclic dependency detected');
      if (visited.has(nodeId)) return;

      temp.add(nodeId);
      const outgoingEdges = edges.filter(e => e.source === nodeId);
      for (const edge of outgoingEdges) {
        visit(edge.target);
      }
      temp.delete(nodeId);
      visited.add(nodeId);
      sorted.unshift(nodes.find(n => n.id === nodeId));
    };

    nodes.forEach(node => {
      if (!visited.has(node.id)) {
        visit(node.id);
      }
    });

    return sorted;
  };

  return (
    <div className="h-[800px]">
      <div className="mb-4 flex gap-2">
        <button
          onClick={executeFlow}
          disabled={isExecuting}
          className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
        >
          {isExecuting ? 'Executing...' : 'Execute Flow'}
        </button>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
};

export default Flows;
