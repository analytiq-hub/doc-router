'use client'

import React, { useEffect, useState, useMemo } from 'react';
import { DocRouterAccountApi } from '@/utils/api';
import { toast } from 'react-toastify';
import { useAppSession } from '@/utils/useAppSession';
import { isSysAdmin } from '@/utils/roles';
import type { SubscriptionPlan } from '@/types/payments';
import { formatLocalDateWithTZ } from '@/utils/date';

interface SubscriptionPlansProps {
  organizationId: string;
  onPaymentMethodStatusChange?: (hasPaymentMethod: boolean) => void;
  onSubscriptionStatusChange?: (subscriptionStatus: string | null) => void;
  onCancellationInfoChange?: (cancelAtPeriodEnd: boolean, currentPeriodEnd: number | null) => void;
  onStripePaymentsPortalChange?: (stripePaymentsPortal: boolean) => void;
  onCurrentPlanChange?: (currentPlan: string | null) => void;
  onCancelSubscription?: () => void;
  cancelAtPeriodEnd?: boolean;
  currentPeriodEnd?: number | null;
}

const SubscriptionPlans: React.FC<SubscriptionPlansProps> = ({ 
  organizationId, 
  onSubscriptionStatusChange,
  onCancellationInfoChange,
  onStripePaymentsPortalChange,
  onCurrentPlanChange,
  onCancelSubscription,
  currentPeriodEnd
}) => {
  const { session } = useAppSession();
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [currentPlan, setCurrentPlan] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [subscriptionStatus, setSubscriptionStatus] = useState<string | null>(null);
  const [stripeEnabled, setStripeEnabled] = useState<boolean>(true);
  const [organizationType, setOrganizationType] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Fetch organization data to get the organization type
        const organizationData = await docRouterAccountApi.getOrganization(organizationId);
        setOrganizationType(organizationData.type);
        
        // Fetch subscription data
        const subscriptionData = await docRouterAccountApi.getSubscription(organizationId);
        
        setPlans(subscriptionData.plans);
        
        // When Stripe is disabled, use organization type as current plan
        const effectiveCurrentPlan = subscriptionData.stripe_enabled 
          ? subscriptionData.current_plan 
          : organizationData.type;
        
        setCurrentPlan(effectiveCurrentPlan);
        setSelectedPlan(effectiveCurrentPlan || 'individual');
        setSubscriptionStatus(subscriptionData.subscription_status);
        setStripeEnabled(subscriptionData.stripe_enabled);
        
        // Notify parent component about subscription status
        if (onSubscriptionStatusChange) {
          onSubscriptionStatusChange(subscriptionData.subscription_status);
        }
        
        // Notify parent component about cancellation info
        if (onCancellationInfoChange) {
          onCancellationInfoChange(subscriptionData.cancel_at_period_end, subscriptionData.current_period_end);
        }
        
        // Notify parent component about stripe payments portal flag
        if (onStripePaymentsPortalChange) {
          onStripePaymentsPortalChange(subscriptionData.stripe_payments_portal_enabled);
        }
        
        // Notify parent component about current plan
        if (onCurrentPlanChange) {
          onCurrentPlanChange(effectiveCurrentPlan);
        }
      } catch (error) {
        console.error('Error fetching subscription plans:', error);
        
        // Check if this is a 404 error (Stripe disabled)
        if (error instanceof Error && error.message.includes('Not Found')) {
          setStripeEnabled(false);
          console.info('Stripe endpoints not available - billing disabled');
        } else {
          toast.error(`Failed to load subscription plans: ${error}`);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [organizationId, onSubscriptionStatusChange, onCancellationInfoChange, onCurrentPlanChange, onStripePaymentsPortalChange, docRouterAccountApi]);

  const canChangeToPlan = (currentPlan: string | null, targetPlan: string): boolean => {
    if (!currentPlan) return true; // No current plan, can select any
    
    const planHierarchy = ['individual', 'team', 'enterprise'];
    const currentIndex = planHierarchy.indexOf(currentPlan);
    const targetIndex = planHierarchy.indexOf(targetPlan);
    
    return targetIndex >= currentIndex; // Can only upgrade or stay same
  };

  const getPlanChangeReason = (organizationType: string | null, targetPlan: string): string | null => {
    if (canChangeToPlan(organizationType, targetPlan)) return null;
    
    return `Cannot downgrade from ${organizationType} to ${targetPlan}`;
  };

  const handlePlanChange = async (planId: string) => {
    // Check if user is trying to select Enterprise plan without admin privileges
    if (planId === 'enterprise' && !isSysAdmin(session)) {
      toast.error('Enterprise plan requires admin privileges');
      return;
    }

    // If Stripe is disabled, simply update organization type
    if (!stripeEnabled) {
      try {
        setLoading(true);
        setSelectedPlan(planId);
        
        // Update the organization type
        await docRouterAccountApi.updateOrganization(organizationId, { type: planId as 'individual' | 'team' | 'enterprise' });
        
        // Update local state
        setCurrentPlan(planId);
        setOrganizationType(planId);
        
        // Notify parent components
        if (onCurrentPlanChange) {
          onCurrentPlanChange(planId);
        }
        
        toast.success(`Organization plan updated to ${planId}`);
        
      } catch (error) {
        console.error('Error updating organization plan:', error);
        toast.error(`Failed to update organization plan: ${error}`);
        setSelectedPlan(currentPlan || 'individual');
      } finally {
        setLoading(false);
      }
      return;
    }

    // Stripe-enabled logic (existing functionality)
    // Check if this is a reactivation (same plan, cancelling status)
    if (currentPlan === planId && subscriptionStatus === 'cancelling') {
      try {
        setLoading(true);
        
        // Reactivate the subscription
        await docRouterAccountApi.activateSubscription(organizationId);
        
        // Refresh the subscription plans data
        const subscriptionResponse = await docRouterAccountApi.getSubscription(organizationId);
        setSubscriptionStatus(subscriptionResponse.subscription_status);
        
        // Notify parent components
        if (onSubscriptionStatusChange) {
          onSubscriptionStatusChange(subscriptionResponse.subscription_status);
        }
        if (onCancellationInfoChange) {
          onCancellationInfoChange(subscriptionResponse.cancel_at_period_end, subscriptionResponse.current_period_end);
        }
        if (onStripePaymentsPortalChange) {
          onStripePaymentsPortalChange(subscriptionResponse.stripe_payments_portal_enabled);
        }
        if (onCurrentPlanChange) {
          onCurrentPlanChange(subscriptionResponse.current_plan);
        }
        
        return;
      } catch (error) {
        console.error('Error reactivating subscription:', error);
        toast.error(`Failed to reactivate subscription: ${error}`);
        return;
      } finally {
        setLoading(false);
      }
    }

    try {
      setLoading(true);
      setSelectedPlan(planId);
      
      // Step 1: Update the organization type
      await docRouterAccountApi.updateOrganization(organizationId, { type: planId as 'individual' | 'team' | 'enterprise' });

      // Step 2: Create checkout session and redirect
      const checkoutResponse = await docRouterAccountApi.createCheckoutSession(organizationId, planId);
      
      // Redirect to Stripe Checkout
      window.location.href = checkoutResponse.payment_portal_url;
      
    } catch (error) {
      console.error('Error changing plan:', error);
      toast.error(`Failed to create checkout session: ${error}`);
      setSelectedPlan(currentPlan || 'individual');
    } finally {
      setLoading(false);
    }
  };

  // Check if user can select a specific plan
  const canSelectPlan = (planId: string): boolean => {
    // Enterprise plan requires admin privileges
    if (planId === 'enterprise') {
      return isSysAdmin(session);
    }
    
    // Use organization type as the minimum allowed plan level
    // Organizations cannot downgrade below their organization type
    return canChangeToPlan(organizationType, planId);
  };

  const getGridColsClass = (num: number) => {
    if (num === 1) return 'md:grid-cols-1';
    if (num === 2) return 'md:grid-cols-2';
    if (num >= 3) return 'md:grid-cols-3';
    return 'md:grid-cols-1';
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-40">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500"></div>
      </div>
    );
  }


  return (
    <div className="w-full">
      {/* Stripe Disabled Notice */}
      {!stripeEnabled && (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-md">
          <div className="flex items-center">
            <svg className="h-5 w-5 text-blue-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h4 className="text-sm font-medium text-blue-900">Organization Plan Selection</h4>
          </div>
          <p className="text-sm text-blue-800 mt-1">
            Billing is disabled. Selecting a plan will change your organization type and available features, but no payment processing will occur.
          </p>
        </div>
      )}
      
      {/* Plans Display */}
      <div className="flex justify-center">
        <div className={`grid grid-cols-1 ${getGridColsClass(plans.length)} gap-8`}>
          {plans.map((plan) => (
            <div
              key={plan.plan_id}
              className={`bg-white rounded-lg shadow-lg p-6 flex flex-col max-w-xs mx-auto ${
                selectedPlan === plan.plan_id ? 'ring-2 ring-blue-500' : ''
              }`}
            >
              <div className="flex-grow">
                <h3 className="text-xl font-bold mb-4">{plan.name}</h3>
                <div className="text-3xl font-bold mb-4">
                  {plan.plan_id === 'enterprise' ? (
                    <div className="text-blue-600 text-2xl font-semibold">Contact Sales</div>
                  ) : (
                    <>
                      ${plan.base_price}
                      <span className="text-sm font-normal text-gray-500">
                        /{plan.interval}
                      </span>
                    </>
                  )}
                </div>
                <ul className="space-y-2 mb-6">
                  {plan.features.map((feature, index) => (
                    <li key={index} className="flex items-start">
                      <svg
                        className="h-5 w-5 text-green-500 mr-2 mt-0 flex-shrink-0"
                        fill="none"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path d="M5 13l4 4L19 7"></path>
                      </svg>
                      {feature}
                    </li>
                  ))}
                </ul>
                {/* Show cancellation warning for current plan if cancelling */}
                {currentPlan === plan.plan_id && subscriptionStatus === 'cancelling' && currentPeriodEnd && (
                  <div className="mb-3 p-2 bg-orange-50 border border-orange-200 rounded-md">
                    <p className="text-xs text-orange-700">
                      Cancels {formatLocalDateWithTZ(new Date(currentPeriodEnd * 1000))}
                    </p>
                  </div>
                )}
              </div>
              <button
                onClick={() => {
                  // When Stripe is disabled, current plans cannot be changed
                  if (!stripeEnabled && currentPlan === plan.plan_id) {
                    return; // Do nothing for current plan when Stripe is disabled
                  }
                  
                  if (currentPlan === plan.plan_id && subscriptionStatus === 'active' && onCancelSubscription) {
                    // Check if user is trying to cancel Enterprise plan without admin privileges
                    if (plan.plan_id === 'enterprise' && !isSysAdmin(session)) {
                      toast.error('Enterprise plan cancellation requires admin privileges');
                      return;
                    }
                    onCancelSubscription();
                  } else {
                    handlePlanChange(plan.plan_id);
                  }
                }}
                disabled={
                  (!canSelectPlan(plan.plan_id) && !(currentPlan === plan.plan_id && subscriptionStatus === 'active')) ||
                  (!stripeEnabled && currentPlan === plan.plan_id) ||
                  (currentPlan === plan.plan_id && subscriptionStatus === 'active' && plan.plan_id === 'enterprise' && !isSysAdmin(session))
                }
                title={
                  !stripeEnabled && currentPlan === plan.plan_id
                    ? 'Current plan'
                    : currentPlan === plan.plan_id && subscriptionStatus === 'active' && plan.plan_id === 'enterprise' && !isSysAdmin(session)
                    ? 'Enterprise plan cancellation requires admin privileges'
                    : plan.plan_id === 'enterprise' && !isSysAdmin(session)
                    ? 'Enterprise plan requires admin privileges'
                    : getPlanChangeReason(organizationType, plan.plan_id) || ''
                }
                className={`w-full py-2 px-4 rounded-md ${
                  currentPlan === plan.plan_id
                    ? !stripeEnabled
                      ? 'bg-gray-300 cursor-not-allowed text-gray-700'
                      : subscriptionStatus === 'cancelling' 
                      ? 'bg-green-600 hover:bg-green-700 text-white'
                      : subscriptionStatus === 'active'
                      ? 'bg-white hover:bg-red-50 text-red-600 border border-red-300'
                      : 'bg-gray-300 cursor-not-allowed'
                    : !canSelectPlan(plan.plan_id)
                    ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                    : selectedPlan === plan.plan_id
                    ? 'bg-green-600 hover:bg-green-700 text-white'
                    : 'bg-blue-600 hover:bg-blue-700 text-white'
                }`}
              >
                {currentPlan === plan.plan_id 
                  ? !stripeEnabled
                    ? 'Current Plan'
                    : subscriptionStatus === 'cancelling' 
                    ? 'Reactivate Plan' 
                    : subscriptionStatus === 'active'
                    ? 'Cancel Subscription'
                    : 'Current Plan'
                  : !canSelectPlan(plan.plan_id)
                  ? plan.plan_id === 'enterprise' ? 'Admin Only' : 'Not Available'
                  : (selectedPlan === plan.plan_id && subscriptionStatus !== 'canceled' && subscriptionStatus !== 'no_subscription')
                    ? 'Selected Plan'
                    : 'Select Plan'
                }
              </button>
            </div>
          ))}
        </div>
      </div>
      
      {/* SPU Information */}
      <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-md">
        <h4 className="text-sm font-medium text-blue-900 mb-2">About SPU (Service Processing Unit)</h4>
        <p className="text-sm text-blue-800">
          SPU is our flexible billing unit that allows for different pricing based on the complexity of document processing. 
        </p>
      </div>
    </div>
  );
};

export default SubscriptionPlans; 