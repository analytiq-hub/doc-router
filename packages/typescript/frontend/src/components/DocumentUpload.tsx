'use client'

import React, { useCallback, useState, useEffect, useMemo } from 'react';
import { useDropzone } from 'react-dropzone';
import { Button, Typography, CircularProgress, IconButton } from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import DescriptionIcon from '@mui/icons-material/Description';
import TableChartIcon from '@mui/icons-material/TableChart';
import ArticleIcon from '@mui/icons-material/Article';
import ImageIcon from '@mui/icons-material/Image';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import { 
  DocRouterOrgApi
} from '@/utils/api';
import { UploadDocument, Tag } from '@docrouter/sdk';
import { isColorLight } from '@/utils/colors';
import InfoTooltip from '@/components/InfoTooltip';
import TagSelector from './TagSelector';

interface DocumentUploadProps {
  organizationId: string;
}

const DocumentUpload: React.FC<DocumentUploadProps> = ({ organizationId }) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [files, setFiles] = useState<UploadDocument[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [metadataFields, setMetadataFields] = useState<Array<{id: string, key: string, value: string}>>([]);
  const [autoCreateEnabled, setAutoCreateEnabled] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState(0);

  // Fetch available tags on component mount
  useEffect(() => {
    const fetchTags = async () => {
      try {
        const response = await docRouterOrgApi.listTags({ limit: 100 });
        setAvailableTags(response.tags);
      } catch (error) {
        console.error('Error fetching tags:', error);
      }
    };
    fetchTags();
  }, [organizationId, docRouterOrgApi]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const readFiles = acceptedFiles.map(file => 
      new Promise<UploadDocument>((resolve) => {
        const reader = new FileReader();
        reader.onload = () => {
          resolve({
            name: file.name,
            content: reader.result as string,
            tag_ids: selectedTags, // Include selected tags with each file
            metadata: Object.fromEntries(
              metadataFields
                .filter(field => field.key.trim() !== '')
                .map(field => [field.key, field.value])
            ) // Include metadata with each file
          });
        };
        reader.readAsDataURL(file);
      })
    );

    Promise.all(readFiles).then(newFiles => {
      setFiles(prevFiles => [...prevFiles, ...newFiles]);
    });
  }, [selectedTags, metadataFields]); // Add selectedTags and metadataFields as dependencies

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/gif': ['.gif'],
      'image/webp': ['.webp'],
      'image/bmp': ['.bmp'],
      'image/tiff': ['.tiff', '.tif']
    },
    multiple: true
  });

  const handleUpload = async () => {
    if (files.length === 0) return;

    // Add selected tags and metadata to each file before upload
    const filesWithTagsAndMetadata = files.map(file => ({
      name: file.name,
      content: file.content, // SDK now accepts base64 strings directly (including data URLs)
      tag_ids: selectedTags, // SDK now supports tag_ids directly
      metadata: Object.fromEntries(
        metadataFields
          .filter(field => field.key.trim() !== '')
          .map(field => [field.key, field.value])
      )
    }));

    setUploading(true);
    setUploadStatus(null);

    try {
      const response = await docRouterOrgApi.uploadDocuments({
        documents: filesWithTagsAndMetadata,
        auto_create_enabled: autoCreateEnabled,
      });
      
      // Create a more detailed success message
      const fileNames = files.map(file => file.name).join(", ");
      const tagNames = selectedTags.length > 0 
        ? availableTags
            .filter(tag => selectedTags.includes(tag.id))
            .map(tag => tag.name)
            .join(", ")
        : "no tags";
      
      setUploadStatus(`Successfully uploaded ${response.documents.length} file(s): ${fileNames} with ${tagNames}`);
      
      setFiles([]);
      setSelectedTags([]); // Reset selected tags after successful upload
      setMetadataFields([]); // Reset metadata after successful upload
      setAutoCreateEnabled(false); // Reset auto-create option
      setActiveStep(0); // Reset to first step
    } catch (error) {
      console.error('Error uploading files:', error);
      setUploadStatus('Error uploading files. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const handleAddMetadata = () => {
    const newId = `field_${Date.now()}`
    setMetadataFields(prev => [...prev, { id: newId, key: '', value: '' }])
  }

  const handleRemoveMetadata = (id: string) => {
    setMetadataFields(prev => prev.filter(field => field.id !== id))
  }

  const handleMetadataKeyChange = (id: string, newKey: string) => {
    setMetadataFields(prev => 
      prev.map(field => 
        field.id === id ? { ...field, key: newKey } : field
      )
    )
    // Clear validation error when user makes changes
    setValidationError(null)
  }

  const handleMetadataValueChange = (id: string, newValue: string) => {
    setMetadataFields(prev => 
      prev.map(field => 
        field.id === id ? { ...field, value: newValue } : field
      )
    )
    // Clear validation error when user makes changes
    setValidationError(null)
  }

  const handleNextStep = useCallback(() => {
    // If moving from step 2 (tags & metadata) to step 3 (upload), validate metadata
    if (activeStep === 1) {
      // Filter out empty keys and check for duplicates
      const nonEmptyFields = metadataFields.filter(field => field.key.trim() !== '')
      const keys = nonEmptyFields.map(field => field.key)
      const duplicateKeys = keys.filter((key, index) => keys.indexOf(key) !== index)
      
      if (duplicateKeys.length > 0) {
        setValidationError(`Duplicate keys found: ${duplicateKeys.join(', ')}. Please remove or rename duplicate keys.`)
        return
      }
    }
    
    setActiveStep((prev) => Math.min(prev + 1, 2));
    // Clear upload status when moving between steps
    if (uploadStatus) {
      setUploadStatus(null);
    }
    // Clear validation error when successfully moving to next step
    setValidationError(null)
  }, [uploadStatus, activeStep, metadataFields]);

  const handlePrevStep = useCallback(() => {
    setActiveStep((prev) => Math.max(prev - 1, 0));
    // Clear upload status when moving between steps
    if (uploadStatus) {
      setUploadStatus(null);
    }
    // Clear validation error when going back
    setValidationError(null)
  }, [uploadStatus]);

  const handleDeleteFile = useCallback((fileName: string) => {
    setFiles(prevFiles => prevFiles.filter(file => file.name !== fileName));
    
    // If no files left, go back to step 1
    if (files.length === 1) {
      setActiveStep(0);
      // Clear upload status when returning to step 1
      if (uploadStatus) {
        setUploadStatus(null);
      }
    }
  }, [files.length, uploadStatus]);

  return (
    <div className="max-w-3xl mx-auto">
      <div className="hidden md:flex items-center gap-2 mb-4">
        <h2 className="text-xl font-bold">Upload Documents</h2>
        <InfoTooltip 
          title="Document Upload"
          content={
            <>
              <p className="mb-2">
                Upload documents to be processed by AI prompts. Supported file formats:
              </p>
              <ul className="list-disc list-inside space-y-1 mb-2">
                <li><strong>PDF files</strong> (.pdf)</li>
                <li><strong>Word documents</strong> (.doc, .docx)</li>
                <li><strong>Excel files</strong> (.xls, .xlsx)</li>
                <li><strong>CSV files</strong> (.csv)</li>
                <li><strong>Text files</strong> (.txt, .md)</li>
                <li><strong>Image files</strong> (.jpg, .jpeg, .png, .gif, .webp, .bmp, .tiff, .tif)</li>
              </ul>
              <p className="mb-2">
                <strong>Note:</strong> Select appropriate tags for your documents to control which prompts are run. Images will be processed using OCR to extract text.
              </p>
            </>
          }
        />
      </div>
      
      {/* Progress Indicator */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div 
            className={`flex flex-col items-center ${activeStep >= 0 ? 'text-blue-600' : 'text-gray-400'}`}
            onClick={() => setActiveStep(0)}
          >
            <div className={`w-8 h-8 rounded-full flex items-center justify-center mb-1 ${activeStep >= 0 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'}`}>
              1
            </div>
            <span className="text-sm">Select Files</span>
          </div>
          <div className={`flex-1 h-1 mx-2 ${activeStep >= 1 ? 'bg-blue-600' : 'bg-gray-200'}`}></div>
          <div 
            className={`flex flex-col items-center ${activeStep >= 1 ? 'text-blue-600' : 'text-gray-400'}`}
            onClick={() => files.length > 0 && setActiveStep(1)}
          >
            <div className={`w-8 h-8 rounded-full flex items-center justify-center mb-1 ${activeStep >= 1 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'}`}>
              2
            </div>
            <span className="text-sm">Tags & Metadata</span>
          </div>
          <div className={`flex-1 h-1 mx-2 ${activeStep >= 2 ? 'bg-blue-600' : 'bg-gray-200'}`}></div>
          <div 
            className={`flex flex-col items-center ${activeStep >= 2 ? 'text-blue-600' : 'text-gray-400'}`}
            onClick={() => files.length > 0 && setActiveStep(2)}
          >
            <div className={`w-8 h-8 rounded-full flex items-center justify-center mb-1 ${activeStep >= 2 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'}`}>
              3
            </div>
            <span className="text-sm">Upload</span>
          </div>
        </div>
      </div>
      
      <div className="bg-white rounded-lg shadow p-6">
        {/* Step 1: Select Files */}
        {activeStep === 0 && (
          <div>
            <h3 className="text-lg font-medium mb-4">Select Files</h3>
            
            <div className="flex items-center mb-3">
              <span className="mr-2">Supported formats:</span>
              <div className="flex items-center bg-gray-100 rounded-full px-3 py-1 mr-2">
                <PictureAsPdfIcon className="text-red-600 mr-1" fontSize="small" />
                <span className="text-sm">PDF</span>
              </div>
              <div className="flex items-center bg-gray-100 rounded-full px-3 py-1 mr-2">
                <DescriptionIcon className="text-blue-700 mr-1" fontSize="small" />
                <span className="text-sm">DOC</span>
              </div>
              <div className="flex items-center bg-gray-100 rounded-full px-3 py-1 mr-2">
                <TableChartIcon className="text-green-700 mr-1" fontSize="small" />
                <span className="text-sm">CSV,XLS</span>
              </div>
              <div className="flex items-center bg-gray-100 rounded-full px-3 py-1 mr-2">
                <ArticleIcon className="text-gray-700 mr-1" fontSize="small" />
                <span className="text-sm">TXT,MD</span>
              </div>
              <div className="flex items-center bg-gray-100 rounded-full px-3 py-1 mr-2">
                <ImageIcon className="text-purple-700 mr-1" fontSize="small" />
                <span className="text-sm">JPG,PNG,GIF</span>
              </div>
            </div>
            
            <div
              {...getRootProps()}
              className="border-2 border-dashed border-gray-300 rounded-lg p-6 cursor-pointer hover:bg-gray-50 transition-colors"
            >
              <input {...getInputProps()} />
              <CloudUploadIcon sx={{ fontSize: 48, mb: 2, color: '#4B5563' }} />
              {isDragActive ? (
                <Typography>Drop files here ...</Typography>
              ) : (
                <Typography>Drag files here, or click to select files</Typography>
              )}
            </div>
            
            {files.length > 0 && (
              <div className="mt-4">
                <Typography variant="subtitle1" className="text-left mb-2">Selected files:</Typography>
                <div className="max-h-40 overflow-y-auto border rounded-md">
                  {files.map((file) => (
                    <div key={file.name} className="text-left py-1 px-2 odd:bg-gray-50 flex justify-between items-center">
                      <span>{file.name}</span>
                      <IconButton 
                        size="small" 
                        onClick={() => handleDeleteFile(file.name)}
                        className="text-red-500 hover:bg-red-50"
                      >
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            <div className="mt-6 flex justify-end">
              <Button
                variant="contained"
                color="primary"
                onClick={handleNextStep}
                disabled={files.length === 0}
              >
                Continue
              </Button>
            </div>
          </div>
        )}
        
        {/* Step 2: Tags & Metadata */}
        {activeStep === 1 && (
          <div>
            <h3 className="text-lg font-medium mb-4">Tags & Metadata (Optional)</h3>
            
            <div className="mb-6 bg-gray-50 p-3 rounded-lg">
              <h4 className="font-medium mb-2">Selected Files:</h4>
              <div className="max-h-32 overflow-y-auto text-sm text-gray-600">
                {files.map((file) => (
                  <div key={file.name} className="mb-1 flex justify-between items-center">
                    <span>{file.name}</span>
                    <IconButton 
                      size="small" 
                      onClick={() => handleDeleteFile(file.name)}
                      className="text-red-500 hover:bg-red-50"
                    >
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="space-y-6">
              {/* Tags Section */}
              <div>
                <h4 className="text-md font-medium mb-3">Tags</h4>
                <p className="text-gray-600 mb-3 text-sm">
                  Select appropriate tags for your documents to ensure they&apos;re processed by the right prompts.
                </p>
                <TagSelector
                  availableTags={availableTags}
                  selectedTagIds={selectedTags}
                  onChange={setSelectedTags}
                />
              </div>

              {/* Metadata Section */}
              {/* Auto-create option */}
              <div>
                <h4 className="text-md font-medium mb-3">Auto-create</h4>
                <label className="flex items-start gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoCreateEnabled}
                    onChange={(e) => setAutoCreateEnabled(e.target.checked)}
                    className="mt-1 rounded"
                  />
                  <span className="text-sm text-gray-600">
                    After OCR, run the agent to automatically propose a schema and prompt for this document. You can review and accept or reject the proposal in the Agent tab.
                  </span>
                </label>
              </div>

              {/* Metadata Section */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-md font-medium">Metadata</h4>
                  <button
                    type="button"
                    onClick={handleAddMetadata}
                    className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-blue-600 hover:text-blue-500 border border-blue-300 rounded-md hover:bg-blue-50"
                  >
                    <AddIcon fontSize="small" className="mr-1" />
                    Add Field
                  </button>
                </div>
                <p className="text-gray-600 mb-3 text-sm">
                  Add key-value pairs that will be attached to all uploaded documents.
                </p>
                
                <div className="space-y-2">
                  {metadataFields.map((field) => (
                    <div key={field.id} className="flex gap-2 items-center">
                      <input
                        type="text"
                        placeholder="Key"
                        value={field.key}
                        onChange={(e) => handleMetadataKeyChange(field.id, e.target.value)}
                        className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
                      />
                      <input
                        type="text"
                        placeholder="Value"
                        value={field.value}
                        onChange={(e) => handleMetadataValueChange(field.id, e.target.value)}
                        className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
                      />
                      <IconButton
                        size="small"
                        onClick={() => handleRemoveMetadata(field.id)}
                        className="text-red-500 hover:text-red-700 hover:bg-red-50"
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </div>
                  ))}
                  {metadataFields.length === 0 && (
                    <p className="text-sm text-gray-500 italic">No metadata fields. Click &quot;Add Field&quot; to add some.</p>
                  )}
                </div>
                
                {/* Validation Error Display */}
                {validationError && (
                  <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
                    <p className="text-sm text-red-600">{validationError}</p>
                  </div>
                )}
              </div>
            </div>
            
            <div className="mt-6 flex justify-between">
              <Button
                variant="outlined"
                onClick={handlePrevStep}
              >
                Back
              </Button>
              <Button
                variant="contained"
                color="primary"
                onClick={handleNextStep}
              >
                Continue
              </Button>
            </div>
          </div>
        )}
        
        {/* Step 3: Upload */}
        {activeStep === 2 && (
          <div>
            <h3 className="text-lg font-medium mb-4">Upload Files</h3>
            
            <div className="bg-gray-50 p-4 rounded-lg mb-6">
              <div className="mb-4">
                <h4 className="font-medium mb-2">Selected Files:</h4>
                <div className="text-sm text-gray-600">
                  {files.map((file) => (
                    <div key={file.name} className="mb-1 flex justify-between items-center">
                      <span>{file.name}</span>
                      <IconButton 
                        size="small" 
                        onClick={() => handleDeleteFile(file.name)}
                        className="text-red-500 hover:bg-red-50"
                      >
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </div>
                  ))}
                </div>
              </div>
              
              <div className="mb-4">
                <h4 className="font-medium mb-2">Selected Tags:</h4>
                <div className="flex flex-wrap gap-1">
                  {selectedTags.length > 0 ? (
                    availableTags
                      .filter(tag => selectedTags.includes(tag.id))
                      .map(tag => (
                        <div
                          key={tag.id}
                          className={`px-2 py-1 rounded text-xs ${
                            isColorLight(tag.color) ? 'text-gray-800' : 'text-white'
                          }`}
                          style={{ backgroundColor: tag.color }}
                        >
                          {tag.name}
                        </div>
                      ))
                  ) : (
                    <span className="text-gray-500 text-sm italic">No tags selected</span>
                  )}
                </div>
              </div>
              
              <div>
                <h4 className="font-medium mb-2">Metadata:</h4>
                <div className="space-y-1">
                  {metadataFields.length > 0 ? (
                    metadataFields
                      .filter(field => field.key.trim() !== '')
                      .map(field => (
                        <div key={field.id} className="flex items-center text-sm">
                          <span className="font-medium text-gray-600 mr-2">{field.key}:</span>
                          <span className="text-gray-800">{field.value || '(empty)'}</span>
                        </div>
                      ))
                  ) : (
                    <span className="text-gray-500 text-sm italic">No metadata fields</span>
                  )}
                </div>
              </div>
            </div>
            
            <div className="mt-6 flex justify-between">
              <Button
                variant="outlined"
                onClick={handlePrevStep}
              >
                Back
              </Button>
              <Button
                variant="contained"
                color="primary"
                onClick={handleUpload}
                disabled={uploading}
                startIcon={uploading ? <CircularProgress size={20} color="inherit" /> : <CloudUploadIcon />}
              >
                {uploading ? 'Uploading...' : 'Upload Files'}
              </Button>
            </div>
          </div>
        )}
      </div>
      
      {uploadStatus && (
        <div className={`mt-4 p-4 rounded-lg ${uploadStatus.includes('Error') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
          {uploadStatus}
        </div>
      )}
    </div>
  );
};

export default DocumentUpload;