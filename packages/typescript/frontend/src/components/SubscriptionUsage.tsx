'use client'

import React, { useEffect, useState, useMemo } from 'react';
import { DocRouterAccountApi } from '@/utils/api';
import { UsageData, SubscriptionResponse } from '@/types/index';
import SubscriptionSPUUsageChart from './SubscriptionSPUUsageChart';
import { formatLocalDate } from '@/utils/date';

interface SubscriptionUsageProps {
  organizationId: string;
  refreshKey?: number;
}

const SubscriptionUsage: React.FC<SubscriptionUsageProps> = ({ organizationId, refreshKey }) => {
  const [usageData, setUsageData] = useState<UsageData | null>(null);
  const [subscriptionData, setSubscriptionData] = useState<SubscriptionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Fetch both usage and subscription data in parallel
        const [usageResponse, subscriptionResponse] = await Promise.all([
          docRouterAccountApi.getCurrentUsage(organizationId),
          docRouterAccountApi.getSubscription(organizationId)
        ]);
        
        if (usageResponse.data) {
          setUsageData(usageResponse.data);
        }
        
        setSubscriptionData(subscriptionResponse);
      } catch (error) {
        console.error('Error fetching usage and subscription data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [organizationId, refreshKey, docRouterAccountApi]);

  // Helper function to convert UTC timestamp to local date string (YYYY-MM-DD format)
  const convertUtcTimestampToLocalDateString = (timestamp: number): string => {
    const date = new Date(timestamp * 1000);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  // Get billing period from subscription data, fallback to usage data, then to current month
  const getBillingPeriod = () => {
    // First try to get from subscription data (most accurate)
    if (subscriptionData?.current_period_start && subscriptionData?.current_period_end) {
      return {
        start: convertUtcTimestampToLocalDateString(subscriptionData.current_period_start),
        end: convertUtcTimestampToLocalDateString(subscriptionData.current_period_end)
      };
    }
    
    // Fallback to usage data
    if (usageData?.period_start && usageData?.period_end) {
      return {
        start: convertUtcTimestampToLocalDateString(usageData.period_start),
        end: convertUtcTimestampToLocalDateString(usageData.period_end)
      };
    }
    
    // Final fallback to current month
    const now = new Date();
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
    const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    
    const localDate = (date: Date) => {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    };
    
    return {
      start: localDate(startOfMonth),
      end: localDate(endOfMonth)
    };
  };


  if (loading) {
    return (
      <div className="flex justify-center items-center h-20">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (!usageData) {
    return (
      <div className="text-gray-500 text-sm">
        No usage data available
      </div>
    );
  }

  const usageUnit = usageData.usage_unit || 'pages';
  const usageUnitDisplay = usageUnit === 'spu' ? 'SPUs' : 'pages';

  // Calculate total credits for display
  const totalCreditsRemaining = usageData.purchased_credits_remaining + usageData.granted_credits_remaining;

  return (
    <div className="space-y-6">
      {/* SPU Usage Chart */}
      <SubscriptionSPUUsageChart 
        organizationId={organizationId} 
        refreshKey={refreshKey}
        defaultBillingPeriod={getBillingPeriod()}
      />
      
      {/* Credits Section */}
      <div className="bg-white p-6 rounded-lg shadow">

        {/* Total Credits Summary */}
        <div className="mt-4 p-3 bg-gray-50 rounded-md">
          <div className="text-sm font-medium text-gray-700 mb-1">Total SPU Credits</div>
          <div className="text-lg font-bold text-gray-800">
            {totalCreditsRemaining} credits remaining
          </div>
          <div className="text-xs text-gray-500">
            {usageData.purchased_credits_remaining} purchased + {usageData.granted_credits_remaining} granted
          </div>
        </div>
      </div>

      {/* Compact Grid - Original Info */}
      <div className={`grid ${usageData.subscription_type ? 'lg:grid-cols-3' : 'lg:grid-cols-2'} gap-2 text-sm text-gray-700 bg-gray-50 border border-gray-100 rounded-md px-4 py-2 mb-4`}>
        
        {usageData.subscription_type ? (
          <div>
            <div className="text-gray-500">Period Metered SPUs</div>
            <div className="font-medium">{usageData.period_metered_usage} {usageUnitDisplay}</div>
          </div>
        ) : (
          <div>
            <div className="text-gray-500">Total Metered SPUs</div>
            <div className="font-medium">{usageData.total_metered_usage} {usageUnitDisplay}</div>
          </div>
        )}
        <div>
          <div className="text-gray-500">Plan</div>
          <div className="font-medium capitalize">
            {usageData.subscription_type || <span className="text-gray-400">No Active Subscription</span>}
          </div>
        </div>
        {usageData.subscription_type && (
          <div>
            <div className="text-gray-500">Billing Period</div>
            {usageData.period_start && usageData.period_end ? (
              <div className="font-medium">{formatLocalDate(new Date(usageData.period_start * 1000))} - {formatLocalDate(new Date(usageData.period_end * 1000))}</div>
            ) : (
              <div className="font-medium text-gray-400">No Active Subscription</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default SubscriptionUsage; 