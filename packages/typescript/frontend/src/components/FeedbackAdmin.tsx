'use client'

import React, { useEffect, useState } from 'react';
import { Delete as DeleteIcon, Search as SearchIcon } from '@mui/icons-material';
import { formatLocalDateWithTZ } from '@/utils/date';

interface FeedbackItem {
  _id: string;
  content: string;
  email: string;
  userName: string | null;
  createdAt: string;
  status: string;
}

const FeedbackAdmin: React.FC = () => {
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);
  const [filteredFeedback, setFilteredFeedback] = useState<FeedbackItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchEmail, setSearchEmail] = useState('');
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;
  const [totalPages, setTotalPages] = useState(1);
  
  // Delete confirmation
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    fetchFeedback();
  }, []);
  
  // Filter feedback based on search and update pagination
  useEffect(() => {
    const filtered = feedback.filter(item => 
      !searchEmail || item.email.toLowerCase().includes(searchEmail.toLowerCase())
    );
    
    setFilteredFeedback(filtered);
    setTotalPages(Math.max(1, Math.ceil(filtered.length / itemsPerPage)));
    
    // Reset to first page when search changes
    if (currentPage !== 1) {
      setCurrentPage(1);
    }
  }, [feedback, searchEmail, currentPage]);

  const fetchFeedback = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/admin/feedback');
      
      if (!response.ok) {
        throw new Error('Failed to fetch feedback');
      }
      
      const data = await response.json();
      setFeedback(data.feedback);
      setFilteredFeedback(data.feedback);
      setTotalPages(Math.max(1, Math.ceil(data.feedback.length / itemsPerPage)));
    } catch (err) {
      setError('Error loading feedback. Please try again later.');
      console.error('Error fetching feedback:', err);
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleDelete = async (id: string) => {
    setDeleteId(id);
  };
  
  const confirmDelete = async () => {
    if (!deleteId) return;
    
    setIsDeleting(true);
    try {
      const response = await fetch(`/api/admin/feedback/${deleteId}`, {
        method: 'DELETE',
      });
      
      if (!response.ok) {
        throw new Error('Failed to delete feedback');
      }
      
      // Remove the deleted item from the list
      setFeedback(feedback.filter(item => item._id !== deleteId));
      setDeleteId(null);
    } catch (err) {
      setError('Error deleting feedback. Please try again later.');
      console.error('Error deleting feedback:', err);
    } finally {
      setIsDeleting(false);
    }
  };
  
  const cancelDelete = () => {
    setDeleteId(null);
  };
  
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };
  
  // Get current page items
  const getCurrentItems = () => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return filteredFeedback.slice(startIndex, endIndex);
  };

  if (isLoading) {
    return <div className="text-center py-8">Loading feedback...</div>;
  }

  if (error) {
    return <div className="text-center py-8 text-red-500">{error}</div>;
  }

  if (feedback.length === 0) {
    return <div className="text-center py-8">No feedback submissions yet.</div>;
  }

  return (
    <div className="space-y-6">
      {/* Search and controls */}
      <div className="bg-white rounded-lg shadow p-4 mb-4">
        <div className="flex flex-col sm:flex-row items-center gap-4">
          <div className="relative flex-grow">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <SearchIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="text"
              placeholder="Search by email..."
              className="pl-10 pr-4 py-2 border border-gray-300 rounded-md w-full focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={searchEmail}
              onChange={(e) => setSearchEmail(e.target.value)}
            />
          </div>
          <div className="text-sm text-gray-600">
            Showing {filteredFeedback.length} results
          </div>
        </div>
      </div>
      
      {/* Feedback items */}
      {getCurrentItems().map((item) => (
        <div key={item._id} className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="font-medium text-gray-900">
                {item.userName || 'Anonymous User'}
              </h3>
              <p className="text-sm text-gray-500">{item.email}</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-sm text-gray-500">
                {formatLocalDateWithTZ(item.createdAt)}
              </div>
              <button 
                onClick={() => handleDelete(item._id)}
                className="text-red-500 hover:text-red-700 transition-colors"
              >
                <DeleteIcon />
              </button>
            </div>
          </div>
          
          <p className="text-gray-700 whitespace-pre-wrap">{item.content}</p>
          
          <div className="mt-4 pt-4 border-t border-gray-100 flex justify-between">
            <span className={`px-2 py-1 text-xs rounded-full ${
              item.status === 'new' 
                ? 'bg-blue-100 text-blue-800' 
                : item.status === 'reviewed' 
                ? 'bg-green-100 text-green-800'
                : 'bg-gray-100 text-gray-800'
            }`}>
              {item.status}
            </span>
          </div>
        </div>
      ))}
      
      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center mt-6">
          <nav className="flex items-center space-x-1">
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1}
              className="px-3 py-1 rounded-md bg-gray-100 text-gray-800 disabled:opacity-50"
            >
              Previous
            </button>
            
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
              <button
                key={page}
                onClick={() => handlePageChange(page)}
                className={`px-3 py-1 rounded-md ${
                  currentPage === page
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-800'
                }`}
              >
                {page}
              </button>
            ))}
            
            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
              className="px-3 py-1 rounded-md bg-gray-100 text-gray-800 disabled:opacity-50"
            >
              Next
            </button>
          </nav>
        </div>
      )}
      
      {/* Delete confirmation modal */}
      {deleteId && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-md w-full">
            <h2 className="text-xl font-semibold mb-4">Confirm Deletion</h2>
            <p className="text-gray-700 mb-6">
              Are you sure you want to delete this feedback? This action cannot be undone.
            </p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={cancelDelete}
                className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                className="px-4 py-2 bg-red-500 text-white rounded-md hover:bg-red-600"
                disabled={isDeleting}
              >
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FeedbackAdmin;