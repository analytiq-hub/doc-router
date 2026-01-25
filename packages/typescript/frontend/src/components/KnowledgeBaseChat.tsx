"use client";

import React, { useState, useMemo, useRef, useEffect } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { KBChatRequest, LLMMessage, KBChatStreamChunk, KBChatStreamError } from '@docrouter/sdk';
import { toast } from 'react-toastify';
import SendIcon from '@mui/icons-material/Send';
import ClearIcon from '@mui/icons-material/Clear';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import SearchIcon from '@mui/icons-material/Search';
import { CircularProgress } from '@mui/material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface KnowledgeBaseChatProps {
  organizationId: string;
  kbId: string;
}

interface ToolCallInfo {
  id: string;
  toolName: string;
  arguments: Record<string, unknown>;
  iteration: number;
  resultsCount?: number;
  error?: string;
  status: 'pending' | 'completed' | 'error';
  timestamp: Date;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCallInfo[];
}

const KnowledgeBaseChat: React.FC<KnowledgeBaseChatProps> = ({ organizationId, kbId }) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentInput, setCurrentInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('');
  const [currentToolCalls, setCurrentToolCalls] = useState<ToolCallInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [abortController, setAbortController] = useState<AbortController | null>(null);
  const [expandedToolCalls, setExpandedToolCalls] = useState<Set<string>>(new Set());
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // Load available models
  useEffect(() => {
    const loadModels = async () => {
      try {
        const response = await docRouterOrgApi.listLLMModels();
        setAvailableModels(response.models);
        if (response.models.length > 0 && !selectedModel) {
          setSelectedModel(response.models[0]);
        }
      } catch (error) {
        const errorMsg = getApiErrorMsg(error) || 'Error loading models';
        toast.error('Error: ' + errorMsg);
      }
    };
    loadModels();
  }, [docRouterOrgApi, selectedModel]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentStreamingMessage, currentToolCalls]);

  const handleSend = async () => {
    if (!currentInput.trim() || !selectedModel || isStreaming) return;

    const userMessage: Message = {
      role: 'user',
      content: currentInput.trim()
    };

    setMessages(prev => [...prev, userMessage]);
    setCurrentInput('');
    setError(null);
    setCurrentStreamingMessage('');
    setCurrentToolCalls([]);
    setIsStreaming(true);

    const controller = new AbortController();
    setAbortController(controller);

    try {
      // Build conversation history
      const conversationMessages: LLMMessage[] = messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }));
      conversationMessages.push({
        role: 'user',
        content: userMessage.content
      });

      const request: KBChatRequest = {
        model: selectedModel,
        messages: conversationMessages,
        temperature: 0.7,
        stream: true
      };

      let assistantContent = '';
      const toolCalls: ToolCallInfo[] = [];

      await docRouterOrgApi.runKBChatStream(
        kbId,
        request,
        (chunk: KBChatStreamChunk | KBChatStreamError) => {
          if ('error' in chunk) {
            setError(chunk.error || 'An error occurred');
            setIsStreaming(false);
            return;
          }

          // Handle text chunks
          if (chunk.chunk) {
            assistantContent += chunk.chunk;
            setCurrentStreamingMessage(assistantContent);
          }

          // Handle tool call events
          if (chunk.type === 'tool_call' && chunk.tool_name) {
            const toolCallId = `${chunk.iteration}-${chunk.tool_name}-${Date.now()}`;
            const toolCall: ToolCallInfo = {
              id: toolCallId,
              toolName: chunk.tool_name,
              arguments: chunk.arguments || {},
              iteration: chunk.iteration || 1,
              status: 'pending',
              timestamp: new Date()
            };
            toolCalls.push(toolCall);
            setCurrentToolCalls([...toolCalls]);
          }

          // Handle tool result events
          if (chunk.type === 'tool_result' && chunk.tool_name) {
            // Find the most recent pending tool call for this tool name and iteration
            for (let i = toolCalls.length - 1; i >= 0; i--) {
              if (
                toolCalls[i].toolName === chunk.tool_name &&
                toolCalls[i].iteration === chunk.iteration &&
                toolCalls[i].status === 'pending'
              ) {
                toolCalls[i] = {
                  ...toolCalls[i],
                  resultsCount: chunk.results_count,
                  error: chunk.error,
                  status: chunk.error ? 'error' : 'completed'
                };
                setCurrentToolCalls([...toolCalls]);
                break;
              }
            }
          }

          // Handle done signal
          if (chunk.done) {
            setIsStreaming(false);
            // Add final assistant message with tool calls
            if (assistantContent || toolCalls.length > 0) {
              setMessages(prev => {
                const newMessages = [...prev];
                newMessages.push({
                  role: 'assistant',
                  content: assistantContent,
                  toolCalls: toolCalls.length > 0 ? [...toolCalls] : undefined
                });
                return newMessages;
              });
            }
            setCurrentStreamingMessage('');
            setCurrentToolCalls([]);
          }
        },
        (error) => {
          if (error.name === 'AbortError') {
            setError('Request was cancelled');
          } else {
            setError(error.message);
          }
          setIsStreaming(false);
        },
        controller.signal
      );
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        setError('Request was cancelled');
      } else {
        const errorMsg = getApiErrorMsg(error) || 'An error occurred';
        setError(errorMsg);
        toast.error('Error: ' + errorMsg);
      }
      setIsStreaming(false);
    } finally {
      setAbortController(null);
    }
  };

  const handleCancel = () => {
    if (abortController) {
      abortController.abort();
    }
  };

  const handleClear = () => {
    if (isStreaming) {
      handleCancel();
    }
    setMessages([]);
    setCurrentStreamingMessage('');
    setCurrentToolCalls([]);
    setError(null);
  };

  const toggleToolCallExpansion = (toolCallId: string) => {
    setExpandedToolCalls(prev => {
      const newSet = new Set(prev);
      if (newSet.has(toolCallId)) {
        newSet.delete(toolCallId);
      } else {
        newSet.add(toolCallId);
      }
      return newSet;
    });
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full max-w-6xl mx-auto bg-white rounded-lg shadow-lg">
      {/* Header */}
      <div className="bg-gradient-to-r bg-blue-600 px-6 py-4 rounded-t-lg">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-white">Chat with Knowledge Base</h2>
          <div className="flex items-center gap-4">
            {availableModels.length > 0 && (
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                disabled={isStreaming}
                className="px-3 py-1 bg-white text-gray-800 rounded border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-300"
              >
                {availableModels.map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            )}
            <button
              onClick={handleClear}
              disabled={isStreaming}
              className="text-white hover:text-gray-200 transition-colors p-1 rounded-full hover:bg-white hover:bg-opacity-20 disabled:opacity-50"
              title="Clear conversation"
            >
              <ClearIcon />
            </button>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-6 space-y-4 bg-gray-50"
        style={{ minHeight: '400px', maxHeight: '600px' }}
      >
        {messages.length === 0 && !currentStreamingMessage && (
          <div className="text-center py-12 text-gray-500">
            <p className="text-lg mb-2">Start a conversation with your knowledge base</p>
            <p className="text-sm">Ask questions and the AI will search the knowledge base to provide answers.</p>
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[80%] rounded-lg px-4 py-3 ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-800 border border-gray-200'
              }`}
            >
              {message.role === 'user' ? (
                <div className="whitespace-pre-wrap">{message.content}</div>
              ) : (
                <div className="[&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0 [&_h1]:text-xl [&_h1]:font-semibold [&_h1]:mt-4 [&_h1]:mb-2 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:mt-3 [&_h2]:mb-2 [&_h3]:text-base [&_h3]:font-semibold [&_h3]:mt-2 [&_h3]:mb-1 [&_ul]:list-disc [&_ul]:ml-6 [&_ul]:my-2 [&_ol]:list-decimal [&_ol]:ml-6 [&_ol]:my-2 [&_li]:my-1 [&_code]:bg-gray-100 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-sm [&_code]:font-mono [&_pre]:bg-gray-100 [&_pre]:p-3 [&_pre]:rounded [&_pre]:overflow-x-auto [&_pre]:my-2 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_blockquote]:border-l-4 [&_blockquote]:border-gray-300 [&_blockquote]:pl-4 [&_blockquote]:my-2 [&_blockquote]:text-gray-600 [&_a]:text-blue-600 [&_a]:underline [&_a:hover]:text-blue-800 [&_table]:w-full [&_table]:my-2 [&_table]:border-collapse [&_th]:border [&_th]:border-gray-300 [&_th]:px-2 [&_th]:py-1 [&_th]:bg-gray-50 [&_th]:font-semibold [&_td]:border [&_td]:border-gray-300 [&_td]:px-2 [&_td]:py-1 [&_hr]:border-t [&_hr]:border-gray-300 [&_hr]:my-4">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                  </ReactMarkdown>
                </div>
              )}
              
              {/* Tool Calls */}
              {message.toolCalls && message.toolCalls.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-300">
                  <div className="text-xs font-semibold text-gray-600 mb-2">Tool Usage:</div>
                  {message.toolCalls.map((toolCall) => (
                    <div key={toolCall.id} className="mb-2 text-xs">
                      <button
                        onClick={() => toggleToolCallExpansion(toolCall.id)}
                        className="flex items-center gap-1 text-blue-600 hover:text-blue-800"
                      >
                        {expandedToolCalls.has(toolCall.id) ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                        <SearchIcon fontSize="small" />
                        <span className="font-medium">
                          {toolCall.toolName} (Iteration {toolCall.iteration})
                        </span>
                        {toolCall.status === 'pending' && (
                          <CircularProgress size={12} className="ml-2" />
                        )}
                        {toolCall.status === 'completed' && toolCall.resultsCount !== undefined && (
                          <span className="ml-2 text-green-600">✓ {toolCall.resultsCount} results</span>
                        )}
                        {toolCall.status === 'error' && (
                          <span className="ml-2 text-red-600">✗ Error</span>
                        )}
                      </button>
                      {expandedToolCalls.has(toolCall.id) && (
                        <div className="mt-1 ml-6 p-2 bg-gray-100 rounded text-xs">
                          <div className="font-medium mb-1">Query:</div>
                          <div className="text-gray-700 mb-2">
                            {(toolCall.arguments?.query as string) || 'N/A'}
                          </div>
                          {toolCall.arguments?.top_k !== undefined && (
                            <div className="text-gray-600">Top K: {String(toolCall.arguments.top_k)}</div>
                          )}
                          {toolCall.error && (
                            <div className="text-red-600 mt-1">Error: {toolCall.error}</div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Streaming Message */}
        {currentStreamingMessage && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg px-4 py-3 bg-white text-gray-800 border border-gray-200">
              <div className="[&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0 [&_h1]:text-xl [&_h1]:font-semibold [&_h1]:mt-4 [&_h1]:mb-2 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:mt-3 [&_h2]:mb-2 [&_h3]:text-base [&_h3]:font-semibold [&_h3]:mt-2 [&_h3]:mb-1 [&_ul]:list-disc [&_ul]:ml-6 [&_ul]:my-2 [&_ol]:list-decimal [&_ol]:ml-6 [&_ol]:my-2 [&_li]:my-1 [&_code]:bg-gray-100 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-sm [&_code]:font-mono [&_pre]:bg-gray-100 [&_pre]:p-3 [&_pre]:rounded [&_pre]:overflow-x-auto [&_pre]:my-2 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_blockquote]:border-l-4 [&_blockquote]:border-gray-300 [&_blockquote]:pl-4 [&_blockquote]:my-2 [&_blockquote]:text-gray-600 [&_a]:text-blue-600 [&_a]:underline [&_a:hover]:text-blue-800 [&_table]:w-full [&_table]:my-2 [&_table]:border-collapse [&_th]:border [&_th]:border-gray-300 [&_th]:px-2 [&_th]:py-1 [&_th]:bg-gray-50 [&_th]:font-semibold [&_td]:border [&_td]:border-gray-300 [&_td]:px-2 [&_td]:py-1 [&_hr]:border-t [&_hr]:border-gray-300 [&_hr]:my-4">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {currentStreamingMessage}
                </ReactMarkdown>
              </div>
              {isStreaming && (
                <span className="inline-block w-2 h-4 bg-blue-600 ml-1 animate-pulse" />
              )}
            </div>
          </div>
        )}

        {/* Current Tool Calls (during streaming) */}
        {currentToolCalls.length > 0 && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg px-4 py-3 bg-yellow-50 border border-yellow-200">
              <div className="text-xs font-semibold text-gray-700 mb-2">Active Tool Calls:</div>
              {currentToolCalls.map((toolCall) => (
                <div key={toolCall.id} className="mb-2 text-xs">
                  <div className="flex items-center gap-2">
                    <SearchIcon fontSize="small" className="text-blue-600" />
                    <span className="font-medium">{toolCall.toolName}</span>
                    {toolCall.status === 'pending' && (
                      <>
                        <CircularProgress size={12} />
                        <span className="text-gray-600">Searching...</span>
                      </>
                    )}
                    {toolCall.status === 'completed' && toolCall.resultsCount !== undefined && (
                      <span className="text-green-600">✓ {toolCall.resultsCount} results</span>
                    )}
                    {toolCall.status === 'error' && (
                      <span className="text-red-600">✗ Error</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="flex justify-center">
            <div className="max-w-[80%] rounded-lg px-4 py-3 bg-red-50 border border-red-200 text-red-800">
              <div className="flex items-start gap-2">
                <span className="font-medium">Error:</span>
                <span>{error}</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 p-4 bg-white rounded-b-lg">
        <div className="flex gap-2">
          <textarea
            value={currentInput}
            onChange={(e) => setCurrentInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            disabled={isStreaming || !selectedModel}
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none disabled:bg-gray-100 disabled:cursor-not-allowed"
            rows={2}
          />
          <div className="flex flex-col gap-2">
            {isStreaming ? (
              <button
                onClick={handleCancel}
                className="px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium flex items-center justify-center gap-2"
              >
                <span>Cancel</span>
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!currentInput.trim() || !selectedModel || isStreaming}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium flex items-center justify-center gap-2 disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                <SendIcon />
                <span>Send</span>
              </button>
            )}
          </div>
        </div>
        {!selectedModel && availableModels.length === 0 && (
          <div className="text-xs text-gray-500 mt-2">Loading models...</div>
        )}
      </div>
    </div>
  );
};

export default KnowledgeBaseChat;
