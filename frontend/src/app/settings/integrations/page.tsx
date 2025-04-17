'use client'

import React, { useState, useEffect } from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import { 
  Button, 
  Typography, 
  Card, 
  Box, 
  Grid, 
  TextField, 
  Dialog, 
  DialogTitle, 
  DialogContent, 
  DialogActions,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  LinearProgress,
  IconButton,
  Chip
} from '@mui/material';
import { 
  Add as AddIcon, 
  Delete as DeleteIcon, 
  Edit as EditIcon, 
  Check as CheckIcon,
  Api as ApiIcon, 
  Storage as DatabaseIcon,
  Description as DocumentIcon,
  Sync as SyncIcon
} from '@mui/icons-material';

type Integration = {
  id: string;
  name: string;
  type: 'api' | 'erp' | 'webhook' | 'custom';
  status: 'active' | 'inactive' | 'pending';
  details: {
    url?: string;
    apiKey?: string;
    system?: string;
    lastSync?: string;
  };
};

const INTEGRATION_TYPES = [
  { value: 'api', label: 'API Connection', icon: ApiIcon },
  { value: 'erp', label: 'ERP System', icon: DatabaseIcon },
  { value: 'webhook', label: 'Webhook', icon: SyncIcon },
  { value: 'custom', label: 'Custom Integration', icon: DocumentIcon },
];

// Example mock data - in a real app, this would come from an API call
const MOCK_INTEGRATIONS: Integration[] = [
  {
    id: '1',
    name: 'SAP ERP Integration',
    type: 'erp',
    status: 'active',
    details: {
      system: 'SAP',
      url: 'https://sap-instance.example.com',
      lastSync: '2024-06-15T10:30:00Z'
    }
  },
  {
    id: '2',
    name: 'Webhook Notification',
    type: 'webhook',
    status: 'active',
    details: {
      url: 'https://example.com/webhook/docrouter',
    }
  }
];

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [currentIntegration, setCurrentIntegration] = useState<Integration | null>(null);
  
  const [formValues, setFormValues] = useState({
    name: '',
    type: 'api',
    url: '',
    apiKey: '',
    system: '',
  });

  // Simulate loading integrations from an API
  useEffect(() => {
    // In a real app, this would be an API call
    setTimeout(() => {
      setIntegrations(MOCK_INTEGRATIONS);
      setLoading(false);
    }, 800);
  }, []);

  const handleOpenDialog = (integration?: Integration) => {
    if (integration) {
      setCurrentIntegration(integration);
      setFormValues({
        name: integration.name,
        type: integration.type,
        url: integration.details.url || '',
        apiKey: integration.details.apiKey || '',
        system: integration.details.system || '',
      });
    } else {
      setCurrentIntegration(null);
      setFormValues({
        name: '',
        type: 'api',
        url: '',
        apiKey: '',
        system: '',
      });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
  };

  const handleDeleteDialog = (integration: Integration) => {
    setCurrentIntegration(integration);
    setDeleteDialogOpen(true);
  };

  const handleCloseDeleteDialog = () => {
    setDeleteDialogOpen(false);
  };

  const handleSubmit = () => {
    if (currentIntegration) {
      // Update existing integration
      const updatedIntegrations = integrations.map(i => 
        i.id === currentIntegration.id 
          ? {
              ...i,
              name: formValues.name,
              type: formValues.type as any,
              details: {
                ...i.details,
                url: formValues.url,
                apiKey: formValues.apiKey,
                system: formValues.system,
              }
            }
          : i
      );
      setIntegrations(updatedIntegrations);
    } else {
      // Add new integration
      const newIntegration: Integration = {
        id: Date.now().toString(),
        name: formValues.name,
        type: formValues.type as any,
        status: 'active',
        details: {
          url: formValues.url,
          apiKey: formValues.apiKey,
          system: formValues.system,
        }
      };
      setIntegrations([...integrations, newIntegration]);
    }
    
    handleCloseDialog();
  };

  const handleDelete = () => {
    if (currentIntegration) {
      const filteredIntegrations = integrations.filter(i => i.id !== currentIntegration.id);
      setIntegrations(filteredIntegrations);
    }
    handleCloseDeleteDialog();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'success';
      case 'inactive': return 'error';
      case 'pending': return 'warning';
      default: return 'default';
    }
  };

  const getIntegrationIcon = (type: string) => {
    const integType = INTEGRATION_TYPES.find(t => t.value === type);
    if (integType) {
      const Icon = integType.icon;
      return <Icon />;
    }
    return <ApiIcon />;
  };

  return (
    <SettingsLayout selectedMenu="integrations">
      <div>
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h5" component="h1">
            Integrations
          </Typography>
          <Button 
            variant="contained" 
            startIcon={<AddIcon />}
            onClick={() => handleOpenDialog()}
            color="primary"
          >
            Add Integration
          </Button>
        </Box>

        <Box sx={{ mb: 4 }}>
          <Typography variant="body1" color="text.secondary">
            Connect DocRouter to your applications, ERPs, or other systems. Manage your existing integrations and set up webhooks for real-time data processing.
          </Typography>
        </Box>

        {loading ? (
          <Box sx={{ width: '100%' }}>
            <LinearProgress />
          </Box>
        ) : (
          <>
            {integrations.length === 0 ? (
              <Card sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="h6" color="text.secondary" gutterBottom>
                  No integrations found
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Get started by adding your first integration to connect DocRouter to your systems.
                </Typography>
                <Button 
                  variant="outlined" 
                  startIcon={<AddIcon />}
                  onClick={() => handleOpenDialog()}
                >
                  Add Integration
                </Button>
              </Card>
            ) : (
              <Grid container spacing={3}>
                {integrations.map((integration) => (
                  <Grid item xs={12} md={6} key={integration.id}>
                    <Card sx={{ p: 3, position: 'relative' }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                        <Box sx={{ 
                          backgroundColor: 'action.hover', 
                          borderRadius: '50%', 
                          width: 40, 
                          height: 40, 
                          display: 'flex', 
                          alignItems: 'center', 
                          justifyContent: 'center',
                          mr: 2
                        }}>
                          {getIntegrationIcon(integration.type)}
                        </Box>
                        <Box sx={{ flexGrow: 1 }}>
                          <Typography variant="h6">{integration.name}</Typography>
                          <Typography variant="body2" color="text.secondary">
                            {INTEGRATION_TYPES.find(t => t.value === integration.type)?.label}
                          </Typography>
                        </Box>
                        <Chip 
                          label={integration.status} 
                          size="small" 
                          color={getStatusColor(integration.status) as any}
                        />
                      </Box>
                      
                      {integration.details.url && (
                        <Box sx={{ mt: 1 }}>
                          <Typography variant="body2" color="text.secondary">
                            URL: {integration.details.url}
                          </Typography>
                        </Box>
                      )}
                      
                      {integration.details.system && (
                        <Box sx={{ mt: 1 }}>
                          <Typography variant="body2" color="text.secondary">
                            System: {integration.details.system}
                          </Typography>
                        </Box>
                      )}
                      
                      {integration.details.lastSync && (
                        <Box sx={{ mt: 1 }}>
                          <Typography variant="body2" color="text.secondary">
                            Last Sync: {new Date(integration.details.lastSync).toLocaleString()}
                          </Typography>
                        </Box>
                      )}
                      
                      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
                        <IconButton 
                          size="small" 
                          onClick={() => handleOpenDialog(integration)}
                          sx={{ mr: 1 }}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                        <IconButton 
                          size="small" 
                          color="error"
                          onClick={() => handleDeleteDialog(integration)}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            )}
          </>
        )}
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {currentIntegration ? 'Edit Integration' : 'Add New Integration'}
        </DialogTitle>
        <DialogContent>
          <Box component="form" sx={{ mt: 2 }}>
            <TextField
              fullWidth
              label="Integration Name"
              margin="normal"
              value={formValues.name}
              onChange={(e) => setFormValues({ ...formValues, name: e.target.value })}
              required
            />
            
            <FormControl fullWidth margin="normal">
              <InputLabel>Integration Type</InputLabel>
              <Select
                value={formValues.type}
                label="Integration Type"
                onChange={(e) => setFormValues({ ...formValues, type: e.target.value })}
              >
                {INTEGRATION_TYPES.map((type) => (
                  <MenuItem key={type.value} value={type.value}>
                    {type.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            
            <TextField
              fullWidth
              label="URL"
              margin="normal"
              value={formValues.url}
              onChange={(e) => setFormValues({ ...formValues, url: e.target.value })}
            />
            
            {formValues.type === 'api' && (
              <TextField
                fullWidth
                label="API Key"
                margin="normal"
                value={formValues.apiKey}
                onChange={(e) => setFormValues({ ...formValues, apiKey: e.target.value })}
                type="password"
              />
            )}
            
            {formValues.type === 'erp' && (
              <TextField
                fullWidth
                label="ERP System"
                margin="normal"
                value={formValues.system}
                onChange={(e) => setFormValues({ ...formValues, system: e.target.value })}
                placeholder="e.g., SAP, Oracle, NetSuite"
              />
            )}
            
            {formValues.type === 'custom' && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                For custom integrations, additional configuration may be required. 
                Contact support for assistance with setting up complex integrations.
              </Typography>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button 
            onClick={handleSubmit} 
            variant="contained" 
            startIcon={<CheckIcon />}
            disabled={!formValues.name}
          >
            {currentIntegration ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={handleCloseDeleteDialog}>
        <DialogTitle>Confirm Deletion</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete the integration "{currentIntegration?.name}"? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDeleteDialog}>Cancel</Button>
          <Button onClick={handleDelete} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </SettingsLayout>
  );
}
