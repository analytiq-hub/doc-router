'use client'

import { toastActionError } from '@/utils/toastActionError';
import React, { useState, useMemo } from 'react';
import { DocRouterAccountApi } from '@/utils/api';
import { toast } from 'react-toastify';

interface SubscriptionAdminCreditProps {
  organizationId: string;
  onCreditsAdded?: () => void;
}

const SubscriptionAdminCredit: React.FC<SubscriptionAdminCreditProps> = ({ 
  organizationId, 
  onCreditsAdded 
}) => {
  const [amount, setAmount] = useState<number>(100);
  const [loading, setLoading] = useState(false);
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);

  const handleAddCredits = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (amount <= 0) {
      toast.error('Please enter a positive amount');
      return;
    }

    setLoading(true);
    try {
      await docRouterAccountApi.addCredits(organizationId, amount);
      setAmount(100); // Reset to default
      if (onCreditsAdded) {
        onCreditsAdded();
      }
    } catch (error) {
      console.error('Error adding credits:', error);
      toastActionError('Failed to add credits', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
      <h4 className="text-lg font-medium text-yellow-800 mb-3">
        <svg className="inline-block w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
        Admin: Add SPU Credits
      </h4>
      
      <form onSubmit={handleAddCredits} className="space-y-3">
        <div>
          <label htmlFor="credit-amount" className="block text-sm font-medium text-yellow-700 mb-1">
            Amount to Add
          </label>
          <div className="flex items-center space-x-2">
            <input
              type="number"
              id="credit-amount"
              value={amount}
              onChange={(e) => setAmount(parseInt(e.target.value) || 0)}
              min="1"
              className="flex-1 px-3 py-2 border border-yellow-300 rounded-md focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500"
              placeholder="Enter amount"
            />
            <span className="text-sm text-yellow-600 font-medium">SPUs</span>
          </div>
        </div>
        
        <button
          type="submit"
          disabled={loading || amount <= 0}
          className="w-full bg-yellow-600 hover:bg-yellow-700 disabled:bg-yellow-300 text-white font-medium py-2 px-4 rounded-md transition-colors duration-200 disabled:cursor-not-allowed"
        >
          {loading ? (
            <div className="flex items-center justify-center">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              Adding Credits...
            </div>
          ) : (
            `Add ${amount} Credits`
          )}
        </button>
      </form>
      
      <p className="text-xs text-yellow-600 mt-2">
        This will add SPU credits to the organization&apos;s account. Credits are used before paid usage.
      </p>
    </div>
  );
};

export default SubscriptionAdminCredit;
