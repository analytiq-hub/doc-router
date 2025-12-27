import React, { useState, useEffect, useMemo } from 'react';
import { Button, TextField, IconButton, Dialog, DialogTitle, DialogContent, DialogActions, Table, TableBody, TableContainer, TableHead, Paper, TableRow, TableCell, Alert, Snackbar } from '@mui/material';
import { Delete as DeleteIcon, ContentCopy as ContentCopyIcon } from '@mui/icons-material';
import { DocRouterAccountApi } from '@/utils/api';
import { CreateTokenRequest, AccessToken } from '@docrouter/sdk';
import { copyToClipboard } from '@/utils/clipboard';

const AccountTokenManager: React.FC = () => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [tokens, setTokens] = useState<AccessToken[]>([]);
  const [openModal, setOpenModal] = useState(false);
  const [newTokenName, setNewTokenName] = useState('');
  const [tokenLifetime, setTokenLifetime] = useState('90');
  const [newToken, setNewToken] = useState<AccessToken | null>(null);
  const [showTokenModal, setShowTokenModal] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const getTokensData = async () => {
      try {
        const tokensData = await docRouterAccountApi.getAccountTokens();
        setTokens(tokensData);
      } catch (error) {
        console.error('Error fetching tokens:', error);
      }
    };

    getTokensData();
  }, [docRouterAccountApi]);

  const createToken = async () => {
    try {
      const trimmedName = newTokenName.trim();
      if (tokens.some(token => token.name === trimmedName)) {
        setError('A token with this name already exists. Please choose a different name.');
        return;
      }

      const lifetime = tokenLifetime.trim() === '' ? 0 : parseInt(tokenLifetime);

      const request: CreateTokenRequest = {
        name: trimmedName,
        lifetime: lifetime
      }
      const response = await docRouterAccountApi.createAccountToken(request)

      setNewToken(response);
      setShowTokenModal(true);
      setOpenModal(false);
      setNewTokenName('');
      setTokenLifetime('90');
    } catch (error) {
      console.error('Error creating token:', error);
      setError('An error occurred while creating the token. Please try again.');
    }
  };

  const saveToken = async () => {
    if (newToken) {
      setNewToken(null);
      setShowTokenModal(false);
      // Refetch tokens to get the preview instead of full token
      try {
        const tokensData = await docRouterAccountApi.getAccountTokens();
        setTokens(tokensData);
      } catch (error) {
        console.error('Error fetching tokens:', error);
      }
    }
  };


  const handleDeleteToken = async (tokenId: string) => {
    try {
      await docRouterAccountApi.deleteAccountToken(tokenId);
      setTokens(tokens.filter(token => token.id !== tokenId));
    } catch (error) {
      console.error('Error deleting token:', error);
      setError('An error occurred while deleting the token. Please try again.');
    }
  };

  return (
    <div>
      <Button
        variant="outlined"
        color="primary"
        className="mb-4"
        onClick={() => setOpenModal(true)}
      >
        Generate Account Token
      </Button>
      <div className="mb-6"></div>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Comment</TableCell>
              <TableCell>Token</TableCell>
              <TableCell>Creation</TableCell>
              <TableCell>Expiration</TableCell>
              <TableCell></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {tokens.map((token, index) => (
              <TableRow 
                key={token.id} 
                sx={{ 
                  '&:last-child td, &:last-child th': { border: 0 }, 
                  height: '30px',
                  backgroundColor: index % 2 === 1 ? 'inherit' : 'rgba(0, 0, 0, 0.04)'  // Add zebra striping
                }}
              >
                <TableCell sx={{ py: 0.5 }}>{token.name}</TableCell>
                <TableCell sx={{ py: 0.5, fontFamily: 'monospace' }}>
                  {token.token ? `${token.token}...` : '-'}
                </TableCell>
                <TableCell sx={{ py: 0.5 }}>{new Date(token.created_at).toLocaleString()}</TableCell>
                <TableCell sx={{ py: 0.5 }}>
                  {token.lifetime
                    ? new Date(new Date(token.created_at).getTime() + token.lifetime * 24 * 60 * 60 * 1000).toLocaleString()
                    : 'None'}
                </TableCell>
                <TableCell sx={{ py: 0.5 }} align="right">
                  <IconButton aria-label="delete" onClick={() => handleDeleteToken(token.id)}>
                    <DeleteIcon />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={openModal} onClose={() => setOpenModal(false)}>
        <DialogTitle>Generate Account Token</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Comment"
            fullWidth
            variant="outlined"
            value={newTokenName}
            onChange={(e) => setNewTokenName(e.target.value)}
            placeholder="What's this token for?"
          />
          <TextField
            margin="dense"
            label="Lifetime (days)"
            type="number"
            fullWidth
            variant="outlined"
            value={tokenLifetime}
            onChange={(e) => setTokenLifetime(e.target.value)}
            placeholder="Leave empty for no expiration"
          />
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" color="primary"
            onClick={() => setOpenModal(false)}>Cancel</Button>
          <Button variant="contained" color="primary" onClick={createToken} disabled={!newTokenName.trim()}>Generate</Button>
        </DialogActions>
      </Dialog>

      {/* New Token Modal */}
      <Dialog open={showTokenModal} onClose={saveToken}>
        <DialogTitle>New Token Created</DialogTitle>
        <DialogContent>
          <p>Copy your new token. It is displayed only once.</p>
          <div className="flex items-center justify-between mt-2 p-2 bg-gray-100 rounded">
            <span className="font-mono">{newToken?.token}</span>
            <IconButton onClick={() => newToken?.token && copyToClipboard(newToken.token)}>
              <ContentCopyIcon />
            </IconButton>
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="contained" color="primary" onClick={saveToken}>Save token</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)}>
        <Alert onClose={() => setError(null)} severity="error" sx={{ width: '100%' }}>
          {error}
        </Alert>
      </Snackbar>
    </div>
  );
};

export default AccountTokenManager;