'use client'

import React, { useState, useEffect } from 'react';
import { Button, TextField } from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { formatLocalDate } from '@/utils/date';

interface AccessToken {
  id: string;
  name: string;
  token: string;
  created_at: string;
}

export default function AccessTokenManager() {
  const [tokens, setTokens] = useState<AccessToken[]>([]);
  const [newTokenName, setNewTokenName] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTokens();
  }, []);

  const fetchTokens = async () => {
    try {
      const response = await fetch('/api/access-tokens');
      if (response.ok) {
        const data = await response.json();
        setTokens(data);
      }
    } catch (error) {
      console.error('Error fetching tokens:', error);
    } finally {
      setLoading(false);
    }
  };

  const createToken = async () => {
    if (!newTokenName.trim()) return;

    try {
      const response = await fetch('/api/access-tokens', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newTokenName }),
      });

      if (response.ok) {
        const newToken = await response.json();
        setTokens([...tokens, newToken]);
        setNewTokenName('');
      }
    } catch (error) {
      console.error('Error creating token:', error);
    }
  };

  const deleteToken = async (tokenId: string) => {
    try {
      const response = await fetch(`/api/access-tokens/${tokenId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        setTokens(tokens.filter(token => token.id !== tokenId));
      }
    } catch (error) {
      console.error('Error deleting token:', error);
    }
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-4 items-center">
        <TextField
          label="Token Name"
          value={newTokenName}
          onChange={(e) => setNewTokenName(e.target.value)}
          size="small"
          className="flex-grow"
        />
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={createToken}
          disabled={!newTokenName.trim()}
        >
          Create Token
        </Button>
      </div>

      <div className="space-y-2">
        {tokens.map((token) => (
          <div
            key={token.id}
            className="flex items-center justify-between p-4 bg-white rounded-lg shadow"
          >
            <div>
              <h3 className="font-medium">{token.name}</h3>
              <p className="text-sm text-gray-500">
                Created: {formatLocalDate(token.created_at)}
              </p>
              {token.token && (
                <p className="mt-1 text-sm font-mono bg-gray-100 p-2 rounded">
                  {token.token}
                </p>
              )}
            </div>
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={() => deleteToken(token.id)}
            >
              Delete
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
} 