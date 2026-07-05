'use client'

import React, { useEffect, useState, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { DocRouterAccountApi } from '@/utils/api';
import SubscriptionPlans from './SubscriptionPlans';
import SubscriptionUsage from './SubscriptionUsage';
import SubscriptionCredits from './SubscriptionCredits';
import SubscriptionPurchase from './SubscriptionPurchase';
import BarChartIcon from '@mui/icons-material/BarChart';
import CreditCardIcon from '@mui/icons-material/CreditCard';
import AttachMoneyIcon from '@mui/icons-material/AttachMoney';
import { toast } from 'react-toastify';

interface SubscriptionProps {
  organizationId: string;
}

const SubscriptionManager: React.FC<SubscriptionProps> = ({ organizationId }) => {
  const searchParams = useSearchParams();
  const [customerPortalUrl, setCustomerPortalUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasPaymentMethod, setHasPaymentMethod] = useState<boolean | null>(null);
  const [subscriptionStatus, setSubscriptionStatus] = useState<string | null>(null);
  const [currentPeriodEnd, setCurrentPeriodEnd] = useState<number | null>(null);
  const [stripePaymentsPortal, setStripePaymentsPortal] = useState<boolean>(false);
  const [currentPlan, setCurrentPlan] = useState<string | null>(null);
  const [stripeEnabled, setStripeEnabled] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'credits' | 'plans' | 'usage'>('credits');
  const [userSelectedTab, setUserSelectedTab] = useState<boolean>(false);
  const [creditsRefreshKey, setCreditsRefreshKey] = useState<number>(0);
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);

  // Handle URL parameters for tab navigation
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    if (tabParam && ['credits', 'plans', 'usage'].includes(tabParam)) {
      setActiveTab(tabParam as 'credits' | 'plans' | 'usage');
      setUserSelectedTab(true);
    } else {
      // No tab parameter or invalid tab - use default logic
      setUserSelectedTab(false);
    }
  }, [searchParams]);

  useEffect(() => {
    const fetchPortalUrl = async () => {
      try {
        setLoading(true);
        const response = await docRouterAccountApi.getCustomerPortal(organizationId);
        // Set URL only if it's not empty, otherwise leave as null
        setCustomerPortalUrl(response.payment_portal_url || null);
        // Set Stripe enabled status
        setStripeEnabled(response.stripe_enabled);
      } catch (error) {
        console.error('Error fetching customer portal URL:', error);
        setCustomerPortalUrl(null);
      } finally {
        setLoading(false);
      }
    };

    fetchPortalUrl();
  }, [organizationId, docRouterAccountApi]);

  useEffect(() => {
    // Check for success/cancel parameters in URL
    const urlParams = new URLSearchParams(window.location.search);
    const success = urlParams.get('success');
    const canceled = urlParams.get('canceled');
    
    if (success === 'true') {
      toast.success('Subscription activated successfully!');
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (canceled === 'true') {
      toast.info('Subscription setup was canceled.');
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const handlePaymentMethodStatusChange = (hasPaymentMethod: boolean) => {
    setHasPaymentMethod(hasPaymentMethod);
  };

  const handleSubscriptionStatusChange = (subscriptionStatus: string | null) => {
    setSubscriptionStatus(subscriptionStatus);
  };

  const handleCancellationInfoChange = (cancelAtPeriodEnd: boolean, currentPeriodEnd: number | null) => {
    setCurrentPeriodEnd(currentPeriodEnd);
  };

  const handleStripePaymentsPortalChange = (stripePaymentsPortal: boolean) => {
    setStripePaymentsPortal(stripePaymentsPortal);
  };

  const handleCurrentPlanChange = (currentPlan: string | null) => {
    setCurrentPlan(currentPlan);
    
    // Smart defaults: Set initial tab based on user state (only if user hasn't manually selected a tab)
    if (!userSelectedTab) {
      if (currentPlan && subscriptionStatus === 'active') {
        setActiveTab('plans'); // Existing subscribers see plans first
      } else {
        setActiveTab('credits'); // New users or no subscription see credits first
      }
    }
  };

  const updateUrlTab = (tab: 'credits' | 'plans' | 'usage') => {
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tab);
    window.history.replaceState({}, '', url.toString());
  };

  const handleTabChange = (tab: 'credits' | 'plans' | 'usage') => {
    setActiveTab(tab);
    setUserSelectedTab(true);
    updateUrlTab(tab);
  };



  const handleCancelSubscription = async () => {
    if (!organizationId) return;
    const confirmed = confirm(
      'Are you sure you want to cancel your subscription? You will continue to have access until the end of your current billing period.'
    );
    if (!confirmed) return;
    setLoading(true);
    try {
      await docRouterAccountApi.cancelSubscription(organizationId);
      setSubscriptionStatus('cancelling');
    } catch (e) {
      console.error('Error cancelling subscription:', e);
    } finally {
      setLoading(false);
    }
  };



  if (loading) {
    return (
      <div className="flex justify-center items-center h-40">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="bg-white p-4 rounded-lg shadow">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Billing</h2>
        {stripePaymentsPortal && customerPortalUrl && (
          <a 
            href={customerPortalUrl} 
            target="_blank" 
            rel="noopener noreferrer"
            className="flex items-center px-3 py-2 text-sm bg-green-600 hover:bg-green-700 text-white rounded-md transition-colors"
          >
            <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
            </svg>
            {currentPlan === 'enterprise' ? 'Previous Plan Billing' : 'Manage Billing'}
          </a>
        )}
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 mb-4">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => handleTabChange('credits')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'credits'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <AttachMoneyIcon className="mr-2 mb-1" fontSize="small" />
            Credits
          </button>
          <button
            onClick={() => handleTabChange('plans')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'plans'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <CreditCardIcon className="mr-2 mb-1" fontSize="small" />
            Plans
          </button>
          <button
            onClick={() => handleTabChange('usage')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'usage'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <BarChartIcon className="mr-2 mb-1" fontSize="small" />
            Usage
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'credits' && (
        <div className="space-y-4">
          {/* Side-by-Side Credits and Purchase/Grant Widgets */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SubscriptionCredits 
              organizationId={organizationId}
              currentPlan={currentPlan}
              subscriptionStatus={subscriptionStatus}
              refreshKey={creditsRefreshKey}
            />
            <SubscriptionPurchase 
              organizationId={organizationId}
              currentPlan={currentPlan}
              subscriptionStatus={subscriptionStatus}
              refreshKey={creditsRefreshKey}
              onCreditsUpdated={() => setCreditsRefreshKey(prev => prev + 1)}
              disabled={!stripeEnabled}
            />
          </div>
          
          {/* Credits Explanation */}
          {stripeEnabled && (
            <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
              <h4 className="text-sm font-medium text-blue-900 mb-1">When to use Credits</h4>
              <ul className="text-sm text-blue-800 space-y-0.5">
                <li>• Perfect for testing and getting started</li>
                <li>• Ideal for occasional or one-off document processing</li>
                <li>• No monthly commitment required</li>
                <li>• Pay only for what you use</li>
              </ul>
            </div>
          )}

          {/* Consider Plans Suggestion */}
          {stripeEnabled && currentPlan && (
            <div className="bg-green-50 border border-green-200 rounded-md p-3">
              <h4 className="text-sm font-medium text-green-900 mb-1">💡 Consider a Monthly Plan</h4>
              <p className="text-sm text-green-800 mb-2">
                Using more than 5,000 SPUs per month? Monthly plans offer better value with included SPUs and lower per-unit pricing.
              </p>
              <button
                onClick={() => handleTabChange('plans')}
                className="text-sm bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded-md transition-colors"
              >
                View Plans →
              </button>
            </div>
          )}
        </div>
      )}

      {activeTab === 'plans' && (
        <div className="space-y-4">
          {/* Plans Explanation */}
          {stripeEnabled && (
            <div className="bg-green-50 border border-green-200 rounded-md p-3">
              <h4 className="text-sm font-medium text-green-900 mb-1">When to use Monthly Plans</h4>
              <ul className="text-sm text-green-800 space-y-0.5">
                <li>• Best for regular document processing</li>
                <li>• Includes SPUs with better per-unit pricing</li>
                <li>• Collaboration features in the Team plan</li>
                <li>• Predictable monthly costs</li>
              </ul>
            </div>
          )}

          {/* Subscription Plans */}
          <SubscriptionPlans 
            organizationId={organizationId}
            onPaymentMethodStatusChange={handlePaymentMethodStatusChange}
            onSubscriptionStatusChange={handleSubscriptionStatusChange}
            onCancellationInfoChange={handleCancellationInfoChange}
            onStripePaymentsPortalChange={handleStripePaymentsPortalChange}
            onCurrentPlanChange={handleCurrentPlanChange}
            onCancelSubscription={handleCancelSubscription}
            cancelAtPeriodEnd={subscriptionStatus === 'cancelling'}
            currentPeriodEnd={currentPeriodEnd}
          />


          {/* Need Credits Instead */}
          {stripeEnabled && (
            <div className="bg-gray-50 border border-gray-200 rounded-md p-3">
              <h4 className="text-sm font-medium text-gray-900 mb-1">Need Credits Instead?</h4>
              <p className="text-sm text-gray-700 mb-2">
                For occasional use or testing, credits might be more cost-effective.
              </p>
              <button
                onClick={() => handleTabChange('credits')}
                className="text-sm bg-gray-600 hover:bg-gray-700 text-white px-3 py-1 rounded-md transition-colors"
              >
                View Credits →
              </button>
            </div>
          )}

          {/* Special status messages */}
          {subscriptionStatus === 'canceled' && (
            <div className="p-3 bg-gray-50 border border-gray-200 rounded-md text-center">
              <p className="text-sm text-gray-600">
                Your subscription has been cancelled. You can reactivate it by selecting a plan above.
              </p>
            </div>
          )}
          {subscriptionStatus === 'past_due' && (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md text-center">
              <p className="text-sm text-yellow-700">
                Your payment is past due. Please update your payment method to continue service.
              </p>
            </div>
          )}
          {hasPaymentMethod === false && (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md">
              <p className="text-yellow-800 text-sm flex items-center">
                <svg className="h-4 w-4 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
                No payment method configured. Please set up a payment method to manage your subscription.
              </p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'usage' && (
        <div className="space-y-4">
          <SubscriptionUsage 
            organizationId={organizationId} 
          />
        </div>
      )}
    </div>
  );
};

export default SubscriptionManager; 