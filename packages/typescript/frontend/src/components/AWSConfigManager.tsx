import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterAccountApi } from '@/utils/api';
import { getApiErrorMsg } from '@/utils/api';
import { AWSConfig } from '@docrouter/sdk';
import { FormDialog } from '@/components/FormDialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';

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
    setError(null);
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

  const configured = Boolean(config?.access_key_id);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0">
          <CardTitle className="text-lg">AWS configuration</CardTitle>
          <Button type="button" onClick={handleEditCredentials}>
            {config ? 'Edit configuration' : 'Add configuration'}
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">

        <p className="text-sm text-gray-600 mb-3">
          IAM user access keys and an S3 bucket used for document storage. The user needs{' '}
          <code>bedrock:InvokeModel</code> and <code>sts:AssumeRole</code> on an app role granted{' '}
          <b>AmazonTextractFullAccess</b>, <b>AmazonSESFullAccess</b>, and read/write access to the S3 bucket
          (<code>s3:GetObject</code>, <code>s3:PutObject</code>, <code>s3:ListBucket</code>,{' '}
          <code>s3:DeleteObject</code>).
        </p>

        <p className="text-sm">
          <b>Status:</b>{' '}
          {configured ? (
            <span className="text-green-600">Configured</span>
          ) : (
            <span className="text-yellow-600">Not configured</span>
          )}
        </p>
        {configured && config && (
          <div className="mt-4 text-sm space-y-1 font-mono text-gray-800">
            <div className="break-all">
              <span className="text-gray-500">Access Key ID:</span> {config.access_key_id}
            </div>
            <div>
              <span className="text-gray-500">Secret Access Key:</span>{' '}
              <span>{config.secret_access_key || '•'.repeat(40)}</span>
            </div>
            <div className="break-all">
              <span className="text-gray-500">S3 Bucket Name:</span> {config.s3_bucket_name}
            </div>
          </div>
        )}
        </CardContent>
      </Card>

      <Card className="border-primary/30 bg-primary-soft">
        <CardContent className="pt-6 text-sm text-foreground">
          Change AWS configuration for on-prem installs only.
        </CardContent>
      </Card>

      {editModalOpen ? (
        <FormDialog
          title="Edit AWS configuration"
          description="Required fields are marked with *."
          submitLabel="Save"
          submitDisabled={!accessKeyId || !secretAccessKey || !s3BucketName}
          error={error}
          onSubmit={() => void handleSaveConfig()}
          onClose={() => {
            setEditModalOpen(false)
            setError(null)
          }}
        >
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="accessKeyId">Access key ID *</FieldLabel>
              <Input
                id="accessKeyId"
                type="text"
                value={accessKeyId}
                onChange={(e) => setAccessKeyId(e.target.value)}
                autoFocus
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="secretKey">Secret access key *</FieldLabel>
              <Input
                id="secretKey"
                type="password"
                value={secretAccessKey}
                onChange={(e) => setSecretAccessKey(e.target.value)}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="s3BucketName">S3 bucket name *</FieldLabel>
              <Input
                id="s3BucketName"
                type="text"
                value={s3BucketName}
                onChange={(e) => setS3BucketName(e.target.value)}
                placeholder="my-s3-bucket"
              />
            </Field>
          </FieldGroup>
        </FormDialog>
      ) : null}
    </div>
  );
};

export default AWSConfigManager;
