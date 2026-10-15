'use client'

import React, { useState } from 'react';
import { useAppSession } from '@/contexts/AppSessionContext';
import { isSysAdmin } from '@/utils/roles';
import { Feedback as FeedbackIcon, AdminPanelSettings as AdminIcon } from '@mui/icons-material';
import Link from 'next/link';

interface FeedbackFormProps {
  onClose?: () => void;
  isModal?: boolean;
}

const FeedbackForm: React.FC<FeedbackFormProps> = ({ onClose, isModal = false }) => {
  const { session } = useAppSession();
  const [feedback, setFeedback] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  
  // Check if the user is an admin
  const isAdmin = isSysAdmin(session);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!feedback.trim()) {
      setSubmitStatus('error');
      setErrorMessage('Please provide feedback before submitting.');
      return;
    }
    
    setIsSubmitting(true);
    setSubmitStatus('idle');
    
    try {
      const response = await fetch('/api/feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          feedback,
          userId: session?.user?.id,
          userName: session?.user?.name,
          createdAt: new Date().toISOString(),
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to submit feedback');
      }
      
      setSubmitStatus('success');
      setFeedback('');
      
      // If this is a modal, close it after successful submission
      if (isModal && onClose) {
        setTimeout(() => {
          onClose();
        }, 2000);
      }
    } catch (error) {
      console.error('Error submitting feedback:', error);
      setSubmitStatus('error');
      setErrorMessage('Failed to submit feedback. Please try again later.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className={`bg-white rounded-lg shadow-md ${isModal ? 'p-6' : 'p-8 max-w-2xl mx-auto my-8'}`}>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <FeedbackIcon className="text-blue-500 mr-2" />
          <h2 className="text-2xl font-semibold text-gray-800">Product Feedback</h2>
        </div>
        
        {/* Admin link - only visible to admins */}
        {isAdmin && (
          <Link 
            href="/admin/feedback" 
            className="flex items-center text-blue-600 hover:text-blue-800 transition-colors"
          >
            <AdminIcon className="mr-1" />
            <span>View All Feedback</span>
          </Link>
        )}
      </div>
      
      <p className="text-gray-600 mb-6">
        We value your feedback! Use this form to report bugs, share suggestions, or send kudos.
      </p>
      
      <form onSubmit={handleSubmit}>
        <div className="mb-4">
          <label htmlFor="feedback" className="block text-sm font-medium text-gray-700 mb-1">
            Your Feedback <span className="text-red-500">*</span>
          </label>
          <textarea
            id="feedback"
            rows={5}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Describe your issue, suggestion, or appreciation here..."
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            required
          />
        </div>
        
        {session?.user?.email && (
          <p className="text-sm text-gray-500 mb-4">
            Feedback will be submitted using your account email: {session.user.email}
          </p>
        )}
        
        {submitStatus === 'success' && (
          <div className="mb-4 p-3 bg-green-100 text-green-700 rounded-md">
            Thank you for your feedback! We appreciate your input.
          </div>
        )}
        
        {submitStatus === 'error' && (
          <div className="mb-4 p-3 bg-red-100 text-red-700 rounded-md">
            {errorMessage}
          </div>
        )}
        
        <button
          type="submit"
          className="w-full py-2 px-4 bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
        </button>
      </form>
    </div>
  );
};

export default FeedbackForm;