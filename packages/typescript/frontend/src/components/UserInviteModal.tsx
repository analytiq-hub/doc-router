'use client'

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button } from '@mui/material';
import { DocRouterAccountApi } from '@/utils/api';
import { Organization } from '@docrouter/sdk';
import { toast } from 'react-toastify';
import debounce from 'lodash/debounce';
import { isAxiosError } from 'axios';

interface UserInviteModalProps {
  open: boolean;
  onClose: () => void;
  onInvited: () => void;
}

const UserInviteModal: React.FC<UserInviteModalProps> = ({
  open,
  onClose,
  onInvited
}) => {
  const [email, setEmail] = useState('');
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Organization[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);

  // Debounced search function
  const searchOrganizations = useCallback((query: string) => {
    if (!query) {
      setSearchResults([]);
      return;
    }
    
    setIsSearching(true);
    docRouterAccountApi.listOrganizations({ nameSearch: query, limit: 20 })
      .then(response => {
        // Filter to only show team and enterprise organizations
        const filteredOrgs = response.organizations.filter(org => 
          org.type === 'team' || org.type === 'enterprise'
        );
        setSearchResults(filteredOrgs);
      })
      .catch(error => {
        console.error('Failed to search organizations:', error);
        toast.error('Failed to search organizations');
      })
      .finally(() => {
        setIsSearching(false);
      });
  }, [docRouterAccountApi]);

  // Use debounce when calling the function
  useEffect(() => {
    const debouncedSearch = debounce(searchOrganizations, 300);
    debouncedSearch(searchQuery);
    
    return () => {
      debouncedSearch.cancel();
    };
  }, [searchQuery, searchOrganizations]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      toast.error('Please enter an email address');
      return;
    }

    setIsSubmitting(true);
    try {
      // Send invitation with optional organization
      await docRouterAccountApi.createInvitation({
        email,
        organization_id: selectedOrg?.id,
      });
      
      toast.success('Invitation sent successfully');
      onInvited();
      onClose();
      setEmail('');
      setSelectedOrg(null);
      setSearchQuery('');
    } catch (error) {
      console.error('Invitation error:', error);
      if (isAxiosError(error)) {
        toast.error(error.response?.data?.detail || 'Failed to send invitation');
      } else {
        toast.error('An unexpected error occurred');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const selectOrganization = (org: Organization) => {
    setSelectedOrg(org);
    setSearchQuery(''); // Clear search after selection
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Invite User</DialogTitle>
      <form onSubmit={handleSubmit}>
        <DialogContent>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter email address"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Add to Organization (Optional)
              </label>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Search organizations..."
              />

              {/* Search Results */}
              {searchQuery && (
                <div className="mt-2 max-h-40 overflow-y-auto border rounded-md">
                  {isSearching ? (
                    <div className="p-2 text-gray-500">Searching...</div>
                  ) : searchResults.length > 0 ? (
                    <div className="divide-y">
                      {searchResults.map(org => (
                        <button
                          key={org.id}
                          type="button"
                          onClick={() => selectOrganization(org)}
                          className="w-full px-3 py-2 text-left hover:bg-gray-50 flex items-center justify-between"
                        >
                          <span>{org.name}</span>
                          <span className="text-sm text-gray-500">{org.type}</span>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="p-2 text-gray-500">No organizations found</div>
                  )}
                </div>
              )}

              {/* Selected Organization */}
              {selectedOrg && (
                <div className="mt-3">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Selected Organization:</h4>
                  <div className="flex items-center justify-between bg-gray-50 px-3 py-2 rounded-md">
                    <span>{selectedOrg.name}</span>
                    <button
                      type="button"
                      onClick={() => setSelectedOrg(null)}
                      className="text-red-600 hover:text-red-800"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </DialogContent>
        <DialogActions className="p-4">
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            variant="contained"
            disabled={isSubmitting || !email}
          >
            {isSubmitting ? 'Sending...' : 'Send Invitation'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default UserInviteModal; 