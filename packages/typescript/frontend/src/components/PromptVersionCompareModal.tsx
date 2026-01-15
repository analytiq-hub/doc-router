import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import { Prompt } from '@docrouter/sdk';
import { getApiErrorMsg } from '@/utils/api';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';

interface PromptVersionCompareModalProps {
  isOpen: boolean;
  onClose: () => void;
  organizationId: string;
  promptId: string;
  currentPrompt: Prompt;
  onCompare: (leftPrompt: Prompt, rightPrompt: Prompt) => void;
}

const PromptVersionCompareModal: React.FC<PromptVersionCompareModalProps> = ({
  isOpen,
  onClose,
  organizationId,
  promptId,
  currentPrompt,
  onCompare
}) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [versions, setVersions] = useState<Prompt[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [leftVersion, setLeftVersion] = useState<number>(currentPrompt.prompt_version);
  const [rightVersion, setRightVersion] = useState<number>(currentPrompt.prompt_version);
  const [leftDropdownOpen, setLeftDropdownOpen] = useState(false);
  const [rightDropdownOpen, setRightDropdownOpen] = useState(false);

  useEffect(() => {
    const loadVersions = async () => {
      if (!isOpen || !promptId) return;
      
      setIsLoading(true);
      setError(null);
      try {
        const response = await docRouterOrgApi.listPromptVersions({ promptId });
        const sorted = response.prompts.sort((a, b) => b.prompt_version - a.prompt_version);
        setVersions(sorted);
        // Set defaults: left = oldest, right = current
        if (sorted.length > 0) {
          setLeftVersion(sorted[sorted.length - 1].prompt_version);
          setRightVersion(currentPrompt.prompt_version);
        }
      } catch (err) {
        const errorMsg = getApiErrorMsg(err) || 'Failed to load prompt versions';
        setError(errorMsg);
        console.error('Error loading prompt versions:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadVersions();
  }, [isOpen, promptId, docRouterOrgApi, currentPrompt.prompt_version]);

  const handleCompare = () => {
    const leftPrompt = versions.find(v => v.prompt_version === leftVersion);
    const rightPrompt = versions.find(v => v.prompt_version === rightVersion);
    
    if (leftPrompt && rightPrompt) {
      // Ensure left is older than right
      if (leftPrompt.prompt_version > rightPrompt.prompt_version) {
        onCompare(rightPrompt, leftPrompt);
      } else {
        onCompare(leftPrompt, rightPrompt);
      }
      onClose();
    }
  };

  if (!isOpen) return null;

  const leftPrompt = versions.find(v => v.prompt_version === leftVersion);
  const rightPrompt = versions.find(v => v.prompt_version === rightVersion);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white p-6 rounded-lg shadow-xl max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold mb-4">Compare Prompt Versions</h3>
        
        {error && (
          <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded-md text-red-800 text-sm">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              {/* Left Version Dropdown */}
              <div className="flex-1 relative">
                <label className="block text-sm font-medium text-gray-700 mb-1">From Version</label>
                <button
                  onClick={() => {
                    setLeftDropdownOpen(!leftDropdownOpen);
                    setRightDropdownOpen(false);
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <span>v{leftVersion}</span>
                  <svg
                    className={`w-4 h-4 text-gray-500 transition-transform ${leftDropdownOpen ? 'transform rotate-180' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {leftDropdownOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setLeftDropdownOpen(false)}
                    ></div>
                    <div className="absolute z-20 mt-1 w-full bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
                      {versions.map((version) => (
                        <button
                          key={version.prompt_revid}
                          onClick={() => {
                            setLeftVersion(version.prompt_version);
                            setLeftDropdownOpen(false);
                          }}
                          className={`w-full px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors ${
                            version.prompt_version === leftVersion ? 'bg-blue-50' : ''
                          }`}
                        >
                          v{version.prompt_version}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>

              <div className="pt-6">
                <CompareArrowsIcon className="text-gray-400" />
              </div>

              {/* Right Version Dropdown */}
              <div className="flex-1 relative">
                <label className="block text-sm font-medium text-gray-700 mb-1">To Version</label>
                <button
                  onClick={() => {
                    setRightDropdownOpen(!rightDropdownOpen);
                    setLeftDropdownOpen(false);
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <span>v{rightVersion}</span>
                  <svg
                    className={`w-4 h-4 text-gray-500 transition-transform ${rightDropdownOpen ? 'transform rotate-180' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {rightDropdownOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setRightDropdownOpen(false)}
                    ></div>
                    <div className="absolute z-20 mt-1 w-full bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
                      {versions.map((version) => (
                        <button
                          key={version.prompt_revid}
                          onClick={() => {
                            setRightVersion(version.prompt_version);
                            setRightDropdownOpen(false);
                          }}
                          className={`w-full px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors ${
                            version.prompt_version === rightVersion ? 'bg-blue-50' : ''
                          }`}
                        >
                          v{version.prompt_version}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 text-gray-700"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCompare}
                disabled={leftVersion === rightVersion}
                className={`px-4 py-2 rounded-md text-white ${
                  leftVersion === rightVersion
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-700'
                }`}
              >
                Compare
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PromptVersionCompareModal;
