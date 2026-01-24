import React, { useState, useMemo } from 'react';
import { DocRouterAccountApi } from '@/utils/api';

interface LLMEmbeddingTestModalProps {
  open: boolean;
  onClose: () => void;
  modelName: string;
}

const LLMEmbeddingTestModal: React.FC<LLMEmbeddingTestModalProps> = ({ open, onClose, modelName }) => {
  const [testInput, setTestInput] = useState<string>('Sample text to embed');
  const [isTesting, setIsTesting] = useState(false);
  const [testResponse, setTestResponse] = useState<{
    dimensions: number;
    embedding: number[];
    usage?: { prompt_tokens?: number; total_tokens?: number } | null;
  } | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);

  const handleRunTest = async () => {
    if (!modelName || !testInput.trim()) return;

    setIsTesting(true);
    setTestResponse(null);
    setTestError(null);

    try {
      const response = await docRouterAccountApi.testEmbeddingModel({
        model: modelName,
        input: testInput.trim()
      });

      setTestResponse({
        dimensions: response.dimensions,
        embedding: response.embedding,
        usage: response.usage
      });
    } catch (error) {
      setTestError(error instanceof Error ? error.message : 'An error occurred during testing');
    } finally {
      setIsTesting(false);
    }
  };

  const handleClose = () => {
    setTestInput('Sample text to embed');
    setTestResponse(null);
    setTestError(null);
    setIsTesting(false);
    onClose();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={handleClose}
      />
      
      {/* Modal */}
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-3xl mx-4 max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r bg-blue-600 px-6 py-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-white">
              Test Embedding Model: {modelName}
            </h2>
            <button
              onClick={handleClose}
              className="text-white hover:text-gray-200 transition-colors p-1 rounded-full hover:bg-white hover:bg-opacity-20"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(90vh-180px)]">
          {/* Input Text */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Input Text
            </label>
            <textarea
              value={testInput}
              onChange={(e) => setTestInput(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors resize-none"
              rows={3}
              placeholder="Enter text to embed..."
            />
          </div>

          {/* Response Section */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Embedding Result
            </label>
            <div className="border border-gray-200 rounded-lg bg-gray-50 min-h-[200px] max-h-[400px] overflow-auto">
              <div className="p-4">
                {isTesting && !testResponse && (
                  <div className="flex items-center gap-2 text-gray-600">
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-500 border-t-transparent"></div>
                    <span>Testing...</span>
                  </div>
                )}
                
                {testResponse && (
                  <div className="space-y-4">
                    <div>
                      <div className="text-sm font-semibold text-gray-700 mb-2">Dimensions: {testResponse.dimensions}</div>
                      {testResponse.usage && (
                        <div className="text-sm text-gray-600 mb-2">
                          Tokens: {testResponse.usage.total_tokens || testResponse.usage.prompt_tokens || 'N/A'}
                        </div>
                      )}
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-gray-700 mb-2">Embedding Vector (first 20 values):</div>
                      <div className="font-mono text-xs text-gray-800 bg-white p-3 rounded border border-gray-200">
                        [{testResponse.embedding.slice(0, 20).map((v, i) => (
                          <span key={i}>
                            {v.toFixed(6)}
                            {i < Math.min(19, testResponse.embedding.length - 1) ? ', ' : ''}
                          </span>
                        ))}...]
                        <div className="mt-2 text-gray-500 italic">
                          (Showing first 20 of {testResponse.embedding.length} dimensions)
                        </div>
                      </div>
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-gray-700 mb-2">Full Embedding Vector:</div>
                      <div className="font-mono text-xs text-gray-800 bg-white p-3 rounded border border-gray-200 max-h-[200px] overflow-auto">
                        [{testResponse.embedding.map((v, i) => (
                          <span key={i}>
                            {v.toFixed(6)}
                            {i < testResponse.embedding.length - 1 ? ', ' : ''}
                          </span>
                        ))}]
                      </div>
                    </div>
                  </div>
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
                  <div className="text-gray-500 italic">Embedding result will appear here...</div>
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
          
          <button
            onClick={handleRunTest}
            disabled={isTesting || !testInput.trim()}
            className={`px-6 py-2 rounded-lg font-medium transition-all transform ${
              isTesting || !testInput.trim()
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-gradient-to-r bg-blue-600 text-white hover:bg-blue-700 hover:shadow-lg hover:scale-105 active:scale-95'
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

export default LLMEmbeddingTestModal;
