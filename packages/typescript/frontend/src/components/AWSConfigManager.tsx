import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterAccountApi } from '@/utils/api';
import { getApiErrorMsg } from '@/utils/api';
import { AWSConfig } from '@docrouter/sdk';

const AWSConfigManager: React.FC = () => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [config, setConfig] = useState<AWSConfig | null>(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [accessKeyId, setAccessKeyId] = useState('');
  const [secretAccessKey, setSecretAccessKey] = useState('');
  const [s3BucketName, setS3BucketName] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const getConfig = async () => {
      try {
        const response = await docRouterAccountApi.getAWSConfig();
        setConfig(response);
      } catch (error) {
        console.error('Error fetching AWS configuration:', error);
      }
    };

    getConfig();
  }, [docRouterAccountApi]);

  const handleEditCredentials = () => {
    setAccessKeyId('');
    setSecretAccessKey('');
    // Preserve existing S3 bucket name if available, otherwise leave empty for new config
    setS3BucketName(config?.s3_bucket_name || '');
    setEditModalOpen(true);
  };

  const handleSaveConfig = async () => {
    try {
      await docRouterAccountApi.createAWSConfig({
        access_key_id: accessKeyId,
        secret_access_key: secretAccessKey,
        s3_bucket_name: s3BucketName,
      });
      setEditModalOpen(false);
      // Refresh the configuration
      const response = await docRouterAccountApi.getAWSConfig();
      setConfig(response);
    } catch (error: unknown) {
      const apiErrorMessage = getApiErrorMsg(error);
      const errorMessage = apiErrorMessage || 'An error occurred while saving the AWS configuration. Please try again.';

      setError(errorMessage);
    }
  };



  return (
    <div className="space-y-4">
      {/* Configuration Section */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-medium text-gray-900">AWS Configuration</h2>
          <button
            onClick={handleEditCredentials}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {config ? 'Edit Configuration' : 'Add Configuration'}
          </button>
        </div>

        <p className="text-sm text-gray-600 mb-3">
          IAM user access keys and an S3 bucket used for document storage. The user needs{' '}
          <code>bedrock:InvokeModel</code> and <code>sts:AssumeRole</code> on an app role granted{' '}
          <b>AmazonTextractFullAccess</b>, <b>AmazonSESFullAccess</b>, and read/write access to the S3 bucket
          (<code>s3:GetObject</code>, <code>s3:PutObject</code>, <code>s3:ListBucket</code>,{' '}
          <code>s3:DeleteObject</code>).
        </p>

        <div className="overflow-hidden border border-gray-200 rounded-lg">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Setting
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Value
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              <tr className="bg-white hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  Access Key ID
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {config?.access_key_id || 'Not configured'}
                </td>
              </tr>
              
              <tr className="bg-gray-50 hover:bg-gray-100">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  Secret Access Key
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {config?.access_key_id ? '••••••••••••••••••••••••••••••••••••••••' : 'Not configured'}
                </td>
              </tr>
              
              <tr className="bg-white hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  S3 Bucket Name
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {config?.s3_bucket_name || 'Not configured'}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Help Section */}
      <div className="bg-blue-50 rounded-lg shadow p-4">
        <span className="list-decimal list-inside space-y-2 text-blue-900">
          Change AWS Configuration for on-prem installs only.
        </span>
      </div>

      {/* Edit Credentials Modal */}
      {editModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Edit AWS Configuration</h2>
              <p className="text-sm text-gray-500">* Required fields</p>
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
                  Access Key ID *
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
                  Secret Access Key *
                </label>
                <input
                  id="secretKey"
                  type="password"
                  value={secretAccessKey}
                  onChange={(e) => setSecretAccessKey(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <div>
                <label htmlFor="s3BucketName" className="block text-sm font-medium text-gray-700 mb-1">
                  S3 Bucket Name *
                </label>
                <input
                  id="s3BucketName"
                  type="text"
                  value={s3BucketName}
                  onChange={(e) => setS3BucketName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="my-s3-bucket"
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
                onClick={handleSaveConfig}
                disabled={!accessKeyId || !secretAccessKey || !s3BucketName}
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

export default AWSConfigManager;
