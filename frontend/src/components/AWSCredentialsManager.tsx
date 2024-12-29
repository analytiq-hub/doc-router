import React, { useState, useEffect } from 'react';
import { Delete as DeleteIcon, Edit as EditIcon } from '@mui/icons-material';
import { getAWSCredentialsApi, createAWSCredentialsApi, deleteAWSCredentialsApi, AWSCredentials } from '@/utils/api';
import { getApiErrorMsg } from '@/utils/api';

const AWSCredentialsManager: React.FC = () => {
  const [credentials, setCredentials] = useState<AWSCredentials | null>(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [accessKeyId, setAccessKeyId] = useState('');
  const [secretAccessKey, setSecretAccessKey] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const getCredentials = async () => {
      try {
        const response = await getAWSCredentialsApi();
        setCredentials(response);
      } catch (error) {
        console.error('Error fetching AWS credentials:', error);
      }
    };

    getCredentials();
  }, []);

  const handleEditCredentials = () => {
    setAccessKeyId('');
    setSecretAccessKey('');
    setEditModalOpen(true);
  };

  const handleSaveCredentials = async () => {
    try {
      await createAWSCredentialsApi({
        access_key_id: accessKeyId,
        secret_access_key: secretAccessKey,
      });
      setEditModalOpen(false);
      // Refresh the credentials
      const response = await getAWSCredentialsApi();
      setCredentials(response);
    } catch (error: unknown) {
      const apiErrorMessage = getApiErrorMsg(error);
      const errorMessage = apiErrorMessage || 'An error occurred while saving the AWS credentials. Please try again.';

      setError(errorMessage);
    }
  };

  const handleDeleteCredentials = async () => {
    try {
      await deleteAWSCredentialsApi();
      setCredentials(null);
    } catch (error: unknown) {
      const apiErrorMessage = getApiErrorMsg(error);
      const errorMessage = apiErrorMessage || 'An error occurred while deleting the AWS credentials. Please try again.';

      setError(errorMessage);
    }
  };

  return (
    <div>
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="mb-2">
              <strong>Access Key ID: </strong>
              {credentials ? (
                <span>{credentials.access_key_id}</span>
              ) : (
                <span className="text-gray-400">Not set</span>
              )}
            </div>
            <div>
              <strong>Secret Access Key: </strong>
              {credentials ? (
                <span>••••••••••••••••</span>
              ) : (
                <span className="text-gray-400">Not set</span>
              )}
            </div>
          </div>
          <div className="flex space-x-2">
            <button
              onClick={handleEditCredentials}
              className="p-2 text-gray-600 hover:text-gray-900 rounded-full hover:bg-gray-100"
              aria-label="edit"
            >
              <EditIcon className="w-5 h-5" />
            </button>
            {credentials && (
              <button
                onClick={handleDeleteCredentials}
                className="p-2 text-gray-600 hover:text-red-600 rounded-full hover:bg-gray-100"
                aria-label="delete"
              >
                <DeleteIcon className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Edit Credentials Modal */}
      {editModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Edit AWS Credentials</h2>
              <button
                onClick={() => setEditModalOpen(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label htmlFor="accessKeyId" className="block text-sm font-medium text-gray-700 mb-1">
                  Access Key ID
                </label>
                <input
                  id="accessKeyId"
                  type="text"
                  value={accessKeyId}
                  onChange={(e) => setAccessKeyId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  autoFocus
                />
              </div>
              
              <div>
                <label htmlFor="secretKey" className="block text-sm font-medium text-gray-700 mb-1">
                  Secret Access Key
                </label>
                <input
                  id="secretKey"
                  type="password"
                  value={secretAccessKey}
                  onChange={(e) => setSecretAccessKey(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="flex justify-end space-x-2 mt-6">
              <button
                onClick={() => setEditModalOpen(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveCredentials}
                disabled={!accessKeyId || !secretAccessKey}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96 bg-white border-l-4 border-red-500 shadow-lg rounded-lg p-4 animate-slide-up">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="ml-3 w-full">
              <p className="text-sm text-gray-800">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="ml-auto flex-shrink-0 text-gray-400 hover:text-gray-500"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default AWSCredentialsManager;
