import React, { useState, useMemo } from 'react';
import { DocRouterAccountApi } from '@/utils/api';
import { LLMChatRequest, LLMMessage } from '@docrouter/sdk';

interface LLMTestModalProps {
  open: boolean;
  onClose: () => void;
  modelName: string;
}

const LLMTestModal: React.FC<LLMTestModalProps> = ({ open, onClose, modelName }) => {
  const [testPrompt, setTestPrompt] = useState<string>('Hello, how are you?');
  const [isTesting, setIsTesting] = useState(false);
  const [testResponse, setTestResponse] = useState<string>('');
  const [testError, setTestError] = useState<string | null>(null);
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);

  const handleRunTest = async () => {
    if (!modelName || !testPrompt.trim()) return;

    const controller = new AbortController();
    setAbortController(controller);
    setIsTesting(true);
    setTestResponse('');
    setTestError(null);

    try {
      const messages: LLMMessage[] = [
        { role: 'user', content: testPrompt.trim() }
      ];

      const request: LLMChatRequest = {
        model: modelName,
        messages,
        temperature: 0.7,
        stream: true
      };

      await docRouterAccountApi.runLLMChatStream(
        request,
        (chunk) => {
          if ('error' in chunk) {
            setTestError(chunk.error);
          } else {
            setTestResponse(prev => prev + chunk.chunk);
          }
        },
        (error) => {
          if (error.name === 'AbortError') {
            setTestError('Request was cancelled');
          } else {
            setTestError(error.message);
          }
        },
        controller.signal
      );
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        setTestError('Request was cancelled');
      } else {
        setTestError(error instanceof Error ? error.message : 'An error occurred during testing');
      }
    } finally {
      setIsTesting(false);
      setAbortController(null);
    }
  };

  const handleCancel = () => {
    if (abortController) {
      abortController.abort();
    }
  };

  const handleClose = () => {
    // Cancel any ongoing request
    if (abortController) {
      abortController.abort();
    }
    
    setTestPrompt('Hello, how are you?');
    setTestResponse('');
    setTestError(null);
    setAbortController(null);
    setIsTesting(false);
    onClose();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 transition-opacity"
        onClick={handleClose}
      />
      
      {/* Modal */}
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r bg-primary-600 px-6 py-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-white">
              Test LLM Model: {modelName}
            </h2>
            <button
              onClick={handleClose}
              className="text-white hover:text-gray-200 transition-colors p-1 rounded-full hover:bg-white/20"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Prompt Input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Test Prompt
            </label>
            <textarea
              value={testPrompt}
              onChange={(e) => setTestPrompt(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors resize-none"
              rows={3}
              placeholder="Enter your test prompt here..."
            />
          </div>

          {/* Response Section */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Response
            </label>
            <div className="border border-gray-200 rounded-lg bg-gray-50 min-h-[200px] max-h-[300px] overflow-auto">
              <div className="p-4 font-mono text-sm whitespace-pre-wrap">
                {isTesting && !testResponse && (
                  <div className="flex items-center gap-2 text-gray-600">
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-primary-500 border-t-transparent"></div>
                    <span>Testing...</span>
                  </div>
                )}
                
                {testResponse && (
                  <div className="text-gray-800">{testResponse}</div>
                )}
                
                {testError && (
                  <div className="text-red-600 bg-red-50 p-3 rounded-md border border-red-200">
                    <div className="flex items-start gap-2">
                      <svg className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                      </svg>
                      <span className="font-medium">Error: {testError}</span>
                    </div>
                  </div>
                )}
                
                {!isTesting && !testResponse && !testError && (
                  <div className="text-gray-500 italic">Response will appear here...</div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-6 py-4 flex items-center justify-end gap-3 border-t border-gray-200">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors font-medium"
          >
            Close
          </button>
          
          {isTesting && (
            <button
              onClick={handleCancel}
              className="px-4 py-2 text-red-700 bg-red-50 border border-red-300 rounded-lg hover:bg-red-100 transition-colors font-medium"
            >
              Cancel
            </button>
          )}
          
          <button
            onClick={handleRunTest}
            disabled={isTesting || !testPrompt.trim()}
            className={`px-6 py-2 rounded-lg font-medium transition-all transform ${
              isTesting || !testPrompt.trim()
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-gradient-to-r bg-primary-600 text-white hover:bg-primary-700 hover:shadow-lg hover:scale-105 active:scale-95'
            }`}
          >
            {isTesting ? (
              <div className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                Testing...
              </div>
            ) : (
              'Run Test'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default LLMTestModal;
