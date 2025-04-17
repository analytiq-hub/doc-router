'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import { 
  Typography, 
  Box, 
  Paper, 
  Tabs,
  Tab,
  Card,
  Divider,
} from '@mui/material';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

export default function ApiDocsPage() {
  const [value, setValue] = React.useState(0);

  const handleChange = (event: React.SyntheticEvent, newValue: number) => {
    setValue(newValue);
  };

  const pythonCode = `import requests

# Replace with your actual API key
API_KEY = "your_api_key"
BASE_URL = "https://docrouter.ai/api/v1"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Upload a document
def upload_document(file_path, tags=None):
    if tags is None:
        tags = []
    
    with open(file_path, "rb") as file:
        files = {"file": file}
        data = {"tags": tags}
        response = requests.post(
            f"{BASE_URL}/documents", 
            headers={"Authorization": f"Bearer {API_KEY}"}, 
            files=files,
            data=data
        )
    
    return response.json()

# Get document processing status
def get_document_status(document_id):
    response = requests.get(
        f"{BASE_URL}/documents/{document_id}",
        headers=headers
    )
    
    return response.json()

# Get extracted data
def get_document_extractions(document_id):
    response = requests.get(
        f"{BASE_URL}/documents/{document_id}/extractions",
        headers=headers
    )
    
    return response.json()
`;

  const nodeJsCode = `const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

// Replace with your actual API key
const API_KEY = 'your_api_key';
const BASE_URL = 'https://docrouter.ai/api/v1';

const headers = {
  'Authorization': \`Bearer \${API_KEY}\`,
  'Content-Type': 'application/json'
};

// Upload a document
async function uploadDocument(filePath, tags = []) {
  const form = new FormData();
  form.append('file', fs.createReadStream(filePath));
  form.append('tags', JSON.stringify(tags));
  
  const response = await axios.post(
    \`\${BASE_URL}/documents\`, 
    form, 
    {
      headers: {
        ...form.getHeaders(),
        'Authorization': \`Bearer \${API_KEY}\`
      }
    }
  );
  
  return response.data;
}

// Get document processing status
async function getDocumentStatus(documentId) {
  const response = await axios.get(
    \`\${BASE_URL}/documents/\${documentId}\`,
    { headers }
  );
  
  return response.data;
}

// Get extracted data
async function getDocumentExtractions(documentId) {
  const response = await axios.get(
    \`\${BASE_URL}/documents/\${documentId}/extractions\`,
    { headers }
  );
  
  return response.data;
}`;

  const cSharpCode = `using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

class DocRouterClient
{
    private readonly HttpClient _client;
    private readonly string _baseUrl;
    
    public DocRouterClient(string apiKey, string baseUrl = "https://docrouter.ai/api/v1")
    {
        _baseUrl = baseUrl;
        _client = new HttpClient();
        _client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);
    }
    
    // Upload a document
    public async Task<string> UploadDocumentAsync(string filePath, string[] tags = null)
    {
        using var form = new MultipartFormDataContent();
        using var fileContent = new StreamContent(File.OpenRead(filePath));
        
        fileContent.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");
        form.Add(fileContent, "file", Path.GetFileName(filePath));
        
        if (tags != null)
        {
            form.Add(new StringContent(JsonSerializer.Serialize(tags)), "tags");
        }
        
        var response = await _client.PostAsync($"{_baseUrl}/documents", form);
        response.EnsureSuccessStatusCode();
        
        var content = await response.Content.ReadAsStringAsync();
        return content;
    }
    
    // Get document processing status
    public async Task<string> GetDocumentStatusAsync(string documentId)
    {
        var response = await _client.GetAsync($"{_baseUrl}/documents/{documentId}");
        response.EnsureSuccessStatusCode();
        
        var content = await response.Content.ReadAsStringAsync();
        return content;
    }
    
    // Get extracted data
    public async Task<string> GetDocumentExtractionsAsync(string documentId)
    {
        var response = await _client.GetAsync($"{_baseUrl}/documents/{documentId}/extractions");
        response.EnsureSuccessStatusCode();
        
        var content = await response.Content.ReadAsStringAsync();
        return content;
    }
}`;

  return (
    <SettingsLayout selectedMenu="integrations_api">
      <Box sx={{ maxWidth: '100%' }}>
        <Typography variant="h5" component="h1" gutterBottom>
          API Documentation
        </Typography>
        
        <Typography variant="body1" color="text.secondary" paragraph>
          Integrate DocRouter.AI with your applications using our REST API. Below you'll find code examples in
          various programming languages to help you get started.
        </Typography>
        
        <Paper sx={{ mt: 4 }}>
          <Tabs
            value={value}
            onChange={handleChange}
            indicatorColor="primary"
            textColor="primary"
          >
            <Tab label="Python" />
            <Tab label="Node.js" />
            <Tab label="C#" />
            <Tab label="API Reference" />
          </Tabs>
          
          <TabPanel value={value} index={0}>
            <Typography variant="h6" gutterBottom>Python Example</Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              This example shows how to upload documents, check processing status, and retrieve extracted data using Python.
            </Typography>
            
            <Box sx={{ mt: 2, border: '1px solid rgba(0, 0, 0, 0.12)', borderRadius: 1 }}>
              <pre className="bg-gray-50 p-4 rounded-lg overflow-x-auto">
                <code className="language-python">{pythonCode}</code>
              </pre>
            </Box>
          </TabPanel>
          
          <TabPanel value={value} index={1}>
            <Typography variant="h6" gutterBottom>Node.js Example</Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Use this example to integrate with DocRouter using Node.js and axios.
            </Typography>
            
            <Box sx={{ mt: 2, border: '1px solid rgba(0, 0, 0, 0.12)', borderRadius: 1 }}>
              <pre className="bg-gray-50 p-4 rounded-lg overflow-x-auto">
                <code className="language-javascript">{nodeJsCode}</code>
              </pre>
            </Box>
          </TabPanel>
          
          <TabPanel value={value} index={2}>
            <Typography variant="h6" gutterBottom>C# Example</Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              This C# example demonstrates how to interact with the DocRouter API from .NET applications.
            </Typography>
            
            <Box sx={{ mt: 2, border: '1px solid rgba(0, 0, 0, 0.12)', borderRadius: 1 }}>
              <pre className="bg-gray-50 p-4 rounded-lg overflow-x-auto">
                <code className="language-csharp">{cSharpCode}</code>
              </pre>
            </Box>
          </TabPanel>
          
          <TabPanel value={value} index={3}>
            <Typography variant="h6" gutterBottom>API Reference</Typography>
            
            <Box sx={{ mt: 2 }}>
              <Card sx={{ p: 3, mb: 3 }}>
                <Typography variant="h6" gutterBottom>Authentication</Typography>
                <Typography variant="body2" paragraph>
                  All API requests require authentication using an API key. Include your API key in the Authorization header:
                </Typography>
                <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                  <Typography variant="body2" component="code" sx={{ fontFamily: 'monospace' }}>
                    Authorization: Bearer your_api_key
                  </Typography>
                </Paper>
                <Typography variant="body2" sx={{ mt: 2 }}>
                  You can generate API keys in the Developer section of your DocRouter settings.
                </Typography>
              </Card>
              
              <Card sx={{ p: 3, mb: 3 }}>
                <Typography variant="h6" gutterBottom>Endpoints</Typography>
                
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle1" gutterBottom>Documents</Typography>
                  <Divider sx={{ mb: 2 }} />
                  <Typography variant="body2" paragraph>
                    <strong>POST /api/v1/documents</strong> - Upload a new document
                  </Typography>
                  <Typography variant="body2" paragraph>
                    <strong>GET /api/v1/documents</strong> - List all documents
                  </Typography>
                  <Typography variant="body2" paragraph>
                    <strong>GET /api/v1/documents/:id</strong> - Get a specific document
                  </Typography>
                  <Typography variant="body2" paragraph>
                    <strong>DELETE /api/v1/documents/:id</strong> - Delete a document
                  </Typography>
                </Box>
                
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle1" gutterBottom>Extractions</Typography>
                  <Divider sx={{ mb: 2 }} />
                  <Typography variant="body2" paragraph>
                    <strong>GET /api/v1/documents/:id/extractions</strong> - Get extractions for a document
                  </Typography>
                  <Typography variant="body2" paragraph>
                    <strong>PUT /api/v1/documents/:id/extractions</strong> - Update extractions for a document
                  </Typography>
                </Box>
                
                <Box>
                  <Typography variant="subtitle1" gutterBottom>Webhooks</Typography>
                  <Divider sx={{ mb: 2 }} />
                  <Typography variant="body2" paragraph>
                    <strong>POST /api/v1/webhooks</strong> - Register a new webhook
                  </Typography>
                  <Typography variant="body2" paragraph>
                    <strong>GET /api/v1/webhooks</strong> - List all webhooks
                  </Typography>
                  <Typography variant="body2" paragraph>
                    <strong>DELETE /api/v1/webhooks/:id</strong> - Delete a webhook
                  </Typography>
                </Box>
              </Card>
              
              <Typography variant="body2" color="text.secondary">
                For complete API documentation, visit our <a href="https://doc-router.analytiqhub.com/fastapi/docs#/" className="text-blue-600 hover:text-blue-800">interactive API docs</a>.
              </Typography>
            </Box>
          </TabPanel>
        </Paper>
      </Box>
    </SettingsLayout>
  );
}
