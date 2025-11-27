import os
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta, UTC
from fastapi import APIRouter, Depends, HTTPException, Request, Body, BackgroundTasks
from pydantic import BaseModel, Field
import stripe
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from bson import ObjectId
import asyncio

import analytiq_data as ad

from app.auth import (
    get_current_user,
    get_org_admin_user,
    get_admin_or_org_user,
    is_organization_admin,
    is_system_admin,
    is_organization_member
)
from app.models import User

import asyncio
import stripe
from functools import partial
from typing import Any, Dict, List, Optional

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
payments_router = APIRouter(tags=["payments"])

stripe_webhook_secret = None

# MongoDB configuration
MONGO_URI = None
ENV = None
STRIPE_PRODUCT_TAG = None

# Global db variable removed - use dependency injection instead

class SPUCreditException(Exception):
    """
    Raised when an organization has insufficient SPU credits to complete an operation.
    
    This exception should be caught at the API level and converted to HTTP 402 Payment Required.
    """
    
    def __init__(self, org_id: str, required_spus: int, available_spus: int = 0):
        self.org_id = org_id
        self.required_spus = required_spus
        self.available_spus = available_spus
        
        message = (
            f"Insufficient SPU credits for organization {org_id}. "
            f"Required: {required_spus}, Available: {available_spus}"
        )
        super().__init__(message)


class StripeAsync:
    @staticmethod
    async def _run_in_threadpool(func, *args, **kwargs):
        """Run a Stripe API call in a thread pool to make it non-blocking"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    @staticmethod
    async def customer_create(*args, **kwargs) -> Dict[str, Any]:
        return await StripeAsync._run_in_threadpool(stripe.Customer.create, *args, **kwargs)

    @staticmethod
    async def customer_modify(customer_id: str, *args, **kwargs) -> Dict[str, Any]:
        return await StripeAsync._run_in_threadpool(stripe.Customer.modify, customer_id, *args, **kwargs)

    @staticmethod
    async def customer_list(*args, **kwargs) -> Dict[str, Any]:
        return await StripeAsync._run_in_threadpool(stripe.Customer.list, *args, **kwargs)

    @staticmethod
    async def customer_search(*args, **kwargs) -> Dict[str, Any]:
        return await StripeAsync._run_in_threadpool(stripe.Customer.search, *args, **kwargs)

    @staticmethod
    async def customer_delete(customer_id: str) -> Dict[str, Any]:
        return await StripeAsync._run_in_threadpool(stripe.Customer.delete, customer_id)

    @staticmethod
    async def subscription_create(*args, **kwargs) -> Dict[str, Any]:
        return await StripeAsync._run_in_threadpool(stripe.Subscription.create, *args, **kwargs)

    @staticmethod
    async def subscription_modify(subscription_id: str, *args, **kwargs) -> Dict[str, Any]:
        return await StripeAsync._run_in_threadpool(stripe.Subscription.modify, subscription_id, *args, **kwargs)

    @staticmethod
    async def subscription_list(*args, **kwargs) -> Dict[str, Any]:
        return await StripeAsync._run_in_threadpool(stripe.Subscription.list, *args, **kwargs)

    @staticmethod
    async def subscription_delete(subscription_id: str, **kwargs) -> Dict[str, Any]:
        return await StripeAsync._run_in_threadpool(stripe.Subscription.delete, subscription_id, **kwargs)

    @staticmethod
    async def setup_intent_create(*args, **kwargs) -> Dict[str, Any]:
        return await StripeAsync._run_in_threadpool(stripe.SetupIntent.create, *args, **kwargs)

    @staticmethod
    async def billing_portal_session_create(*args, **kwargs) -> Dict[str, Any]:
        return await StripeAsync._run_in_threadpool(stripe.billing_portal.Session.create, *args, **kwargs)

    @staticmethod
    async def webhook_construct_event(payload: bytes, sig_header: str, secret: str) -> Dict[str, Any]:
        return await StripeAsync._run_in_threadpool(
            stripe.Webhook.construct_event,
            payload,
            sig_header,
            secret
        )


    @staticmethod
    async def subscription_item_list(*args, **kwargs) -> Dict[str, Any]:
        return await StripeAsync._run_in_threadpool(
            stripe.SubscriptionItem.list,
            *args,
            **kwargs
        )


# Pydantic models for request/response validation
class UsageRecord(BaseModel):
    spus: int = Field(default=0)  # New field for SPU tracking
    operation: str
    source: str = "backend"

class PortalSessionResponse(BaseModel):
    payment_portal_url: str
    stripe_enabled: bool

class SubscriptionPlan(BaseModel):
    plan_id: str
    name: str
    base_price: float
    included_spus: int  # Monthly SPU allowance
    features: List[str]
    currency: str = "usd"
    interval: str = "month"

class SubscriptionResponse(BaseModel):
    plans: List[SubscriptionPlan]
    current_plan: Optional[str] = None
    subscription_status: Optional[str] = None
    cancel_at_period_end: bool = False
    current_period_start: Optional[int] = None  # Unix timestamp
    current_period_end: Optional[int] = None  # Unix timestamp
    stripe_enabled: bool = False
    stripe_payments_portal_enabled: bool = False

class UsageData(BaseModel):
    subscription_type: Optional[str]
    usage_unit: str
    period_metered_usage: int
    total_metered_usage: int
    remaining_included: int
    purchased_credits: int
    purchased_credits_used: int
    purchased_credits_remaining: int
    granted_credits: int
    granted_credits_used: int
    granted_credits_remaining: int
    period_start: Optional[int] = None  # Unix timestamp
    period_end: Optional[int] = None    # Unix timestamp

class UsageResponse(BaseModel):
    usage_source: str  # "stripe", "local", or "none"
    data: UsageData

class CreditUpdate(BaseModel):
    amount: int

class PurchaseCreditsRequest(BaseModel):
    credits: int = Field(ge=10, le=10000)  # Minimum 10, maximum 10000 credits
    success_url: str
    cancel_url: str

class PurchaseCreditsResponse(BaseModel):
    checkout_url: str
    session_id: str

class CheckoutSessionRequest(BaseModel):
    plan_id: str

class UsageRangeRequest(BaseModel):
    start_date: str                   # ISO date string (required)
    end_date: str                     # ISO date string (required)

class UsageDataPoint(BaseModel):
    date: str                         # ISO date string
    spus: int                         # SPUs used on this date
    operation: str                    # Type of operation
    source: str                       # Source of usage

class UsageRangeResponse(BaseModel):
    data_points: List[UsageDataPoint]
    total_spus: int                   # Total SPUs in the period

# Dynamic configuration - populated from Stripe at startup
CREDIT_CONFIG = {
    "price_per_credit": 0.0,
    "currency": "usd",
    "min_spu_purchase": 0,
    "max_spu_purchase": 0,
    "min_cost": 0.0,
    "max_cost": 0.0,
    "granted_credits": 100 # Number of credits granted to each user
}

# SPU limits per tier - populated from Stripe metadata at startup
TIER_LIMITS = {
    "individual": 0,
    "team": 0,
    "enterprise": None     # No limit (custom billing, not in Stripe)
}

def stripe_enabled() -> bool:
    # Consider Stripe enabled only if api_key is a non-empty string
    return stripe.api_key is not None

# Modify the init_payments_env function
async def init_payments_env(database):
    global MONGO_URI, ENV, STRIPE_PRODUCT_TAG
    global NEXTAUTH_URL
    global stripe_webhook_secret

    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    ENV = os.getenv("ENV", "dev")
    NEXTAUTH_URL = os.getenv("NEXTAUTH_URL", "http://localhost:3000")
    STRIPE_PRODUCT_TAG = os.getenv("STRIPE_PRODUCT_TAG", "doc_router")

    # Database connection is now passed as parameter to functions that need it

    # Normalize empty strings to None for robustness
    stripe_secret_key = os.getenv("STRIPE_SECRET_KEY", "")
    if stripe_secret_key != "":
        stripe.api_key = stripe_secret_key
    else:
        stripe.api_key = None
    stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if stripe_webhook_secret == "":
        stripe_webhook_secret = None

    logger.info(f"init_payments_env() completed; stripe_enabled={stripe_enabled()}, product_tag={STRIPE_PRODUCT_TAG}")
    
async def init_payments(db):
    await init_payments_env(db)

    logger.info("Stripe initialized")

    ad.payments.set_check_payment_limits_hook(check_payment_limits)
    ad.payments.set_record_payment_usage_hook(record_payment_usage)
    
    # Initialize dynamic configuration from Stripe
    await get_credit_config()
    await get_tier_limits()

    await sync_all_customers(db)
    logger.info("Stripe customers synced")

async def get_tier_limits() -> Dict[str, Any]:
    """
    Fetch tier limits dynamically from Stripe base price metadata for the configured product
    """
    global TIER_LIMITS
    
    if not stripe_enabled():
        return

    # Get all active prices for our product
    prices = await StripeAsync._run_in_threadpool(
        stripe.Price.list,
        active=True,
        expand=['data.product']
    )
    
    # Filter by product metadata
    product_prices = [
        price for price in prices.data 
        if price.product.metadata.get('product') == STRIPE_PRODUCT_TAG
    ]
    
    logger.info(f"Found {len(product_prices)} prices for product tag: {STRIPE_PRODUCT_TAG}")
    
    # Find base prices and extract limits from metadata
    for price in product_prices:
        metadata = price.metadata
        price_type = metadata.get('price_type')
        
        if price_type == 'base':
            tier = metadata.get('tier', '').strip()
            if tier in ['individual', 'team']:
                included_spus = metadata.get('included_spus')
                if not included_spus:
                    raise ValueError(f"Missing included_spus metadata for {tier} base price {price.id}")
                TIER_LIMITS[tier] = int(included_spus)
                logger.info(f"Loaded {tier} SPU limit from Stripe: {included_spus}")
    
    # Ensure we have non-zero limits for individual and team
    if TIER_LIMITS['individual'] == 0:
        raise ValueError("Individual SPU limit must be non-zero")
    if TIER_LIMITS['team'] == 0:
        raise ValueError("Team SPU limit must be non-zero")

async def get_credit_config() -> Dict[str, Any]:
    """
    Fetch credit configuration dynamically from Stripe credit prices for the configured product
    """
    global CREDIT_CONFIG
    
    if not stripe_enabled():
        return
    
    # Get all active prices for our product
    prices = await StripeAsync._run_in_threadpool(
        stripe.Price.list,
        active=True,
        expand=['data.product']
    )
    
    # Filter by product metadata
    product_prices = [
        price for price in prices.data 
        if price.product.metadata.get('product') == STRIPE_PRODUCT_TAG
    ]
    
    logger.info(f"Found {len(product_prices)} prices for product tag: {STRIPE_PRODUCT_TAG}")
    
    credit_config = None
    
    # Find credit prices
    for price in product_prices:
        metadata = price.metadata
        price_type = metadata.get('price_type')
        
        if price_type == 'credit':
            # Validate price has unit_amount
            if price.unit_amount is None:
                raise ValueError(f"Credit price {price.id} has no unit_amount set in Stripe")
                
            # Build config from Stripe price and metadata
            # Stripe unit_amount is in the smallest currency unit (cents for USD)
            # Account for transform_quantity.divide_by if present
            transform_divide_by = price.get('transform_quantity', {}).get('divide_by', 1)
            price_per_credit = (price.unit_amount / 100) / transform_divide_by
            
            # Get required metadata
            min_spu_purchase = metadata.get('min_spu_purchase')
            max_spu_purchase = metadata.get('max_spu_purchase')
            
            # Log found price for debugging
            logger.info(f"Found credit price {price.id}: unit_amount={price.unit_amount}, currency={price.currency}")
            logger.info(f"Credit price metadata: {dict(metadata)}")
            
            if not min_spu_purchase:
                raise ValueError(f"Missing min_spu_purchase metadata for credit price {price.id}")
            if not max_spu_purchase:
                raise ValueError(f"Missing max_spu_purchase metadata for credit price {price.id}")

            CREDIT_CONFIG["price_per_credit"] = price_per_credit
            CREDIT_CONFIG["currency"] = price.currency
            CREDIT_CONFIG["min_spu_purchase"] = int(min_spu_purchase)
            CREDIT_CONFIG["max_spu_purchase"] = int(max_spu_purchase)
            CREDIT_CONFIG["min_cost"] = int(min_spu_purchase) * price_per_credit
            CREDIT_CONFIG["max_cost"] = int(max_spu_purchase) * price_per_credit
            
            logger.info(f"Loaded credit config from Stripe: price=${price_per_credit:.3f}, min={min_spu_purchase}, max={max_spu_purchase}")
            return
    
    raise ValueError(f"No credit price found in Stripe with price_type=credit for product tag: {STRIPE_PRODUCT_TAG}")

# Function to fetch base pricing from Stripe
async def get_tier_config(db, org_id: str = None) -> Dict[str, Any]:
    """
    Fetch tier configuration dynamically from Stripe prices (base pricing only) for the configured product
    """

    tier_config = {
        "individual": {
            "base_price_id": None, 
            "base_price": 0.0, 
            "included_spus": None
        },
        "team": {
            "base_price_id": None, 
            "base_price": 0.0, 
            "included_spus": None
        },
        "enterprise": {
            "base_price_id": None, 
            "base_price": 0.0, 
            "included_spus": None
        }
    }

    if not stripe_enabled():
        return tier_config

    # Get all active prices for our product
    prices = await StripeAsync._run_in_threadpool(
        stripe.Price.list,
        active=True,
        expand=['data.product']
    )
    
    # Filter by product metadata
    product_prices = [
        price for price in prices.data 
        if price.product.metadata.get('product') == STRIPE_PRODUCT_TAG
    ]
    
    logger.info(f"Found {len(product_prices)} prices for product tag: {STRIPE_PRODUCT_TAG}")
    
    # Find base prices for each tier
    for price in product_prices:
        metadata = price.metadata
        price_type = metadata.get('price_type')
        
        if price_type != 'base':
            continue
            
        tier = metadata.get('tier', '').strip()
        if tier in ['individual', 'team']:
            included_spus = metadata.get('included_spus')
            if not included_spus:
                raise ValueError(f"Missing included_spus metadata for {tier} base price {price.id}")
                
            tier_config[tier] = {
                'base_price_id': price.id,
                'base_price': price.unit_amount / 100,
                'included_spus': int(included_spus)
            }
            logger.info(f"Loaded {tier} tier config from Stripe: ${price.unit_amount / 100}, {included_spus} SPUs")
    
    # Ensure we found both individual and team tiers
    if 'individual' not in tier_config or 'team' not in tier_config:
        missing = [t for t in ['individual', 'team'] if t not in tier_config]
        raise ValueError(f"Missing base prices in Stripe for tiers: {missing} (product tag: {STRIPE_PRODUCT_TAG})")
    
    return tier_config

def format_price_per_spu(price: float) -> str:
    """
    Format price per SPU to show only necessary decimal places.
    Shows 3 decimals only if the third decimal is non-zero, otherwise shows 2 decimals.
    """
    # Round to 3 decimal places first to handle floating point precision issues
    rounded_price = round(price, 3)
    
    # Check if the third decimal place is significant
    if rounded_price * 1000 == int(rounded_price * 1000):
        # No significant third decimal, use 2 decimal places
        return f"{rounded_price:.2f}"
    else:
        # Third decimal is significant, use 3 decimal places
        return f"{rounded_price:.3f}"



async def sync_payments_customers(db) -> Tuple[int, int, List[str]]:
    """
    Initialize payment customers for all organizations without Stripe API calls.
    Sets up local payment customer records with zero SPU credits, usage, and billing periods.
    This runs regardless of Stripe configuration.
    
    Returns:
        Tuple containing (total_orgs, successful_syncs, error_messages)
    """
    logger.info("Starting sync of local payment customers (no Stripe APIs)")
    
    try:
        # Get all organizations from MongoDB
        orgs = await db.organizations.find().to_list(length=None)
        total_orgs = len(orgs)
        local_org_ids = set(str(org["_id"]) for org in orgs)
        
        # Get all local payment customers
        payment_customers_list = await db.payments_customers.find({"org_id": {"$exists": True}}).to_list(length=None)
        payment_org_ids = set(customer.get("org_id") for customer in payment_customers_list if customer.get("org_id"))
        
        # Find organizations that need local payment customer creation
        missing_from_payments = local_org_ids - payment_org_ids
        orphaned_in_payments = payment_org_ids - local_org_ids
        
        logger.info(f"Total orgs: {total_orgs}")
        logger.info(f"Payment customers: {len(payment_org_ids)}")
        logger.info(f"Missing from payments: {len(missing_from_payments)}")
        logger.info(f"Orphaned in payments: {len(orphaned_in_payments)}")
        
        # Clean up orphaned payment customers
        if orphaned_in_payments:
            logger.info(f"Cleaning up {len(orphaned_in_payments)} orphaned payment customers")
            await _cleanup_orphaned_payment_customers(db, orphaned_in_payments)
        
        if not missing_from_payments:
            logger.info("All organizations already have local payment customers")
            return total_orgs, 0, []
        
        # Create local payment customers for missing organizations
        return await _create_payments_customer_set(db, missing_from_payments)
    
    except Exception as e:
        logger.error(f"Error during payment customers sync: {e}")
        return 0, 0, [f"Global error: {str(e)}"]


async def sync_stripe_customers(db) -> Tuple[int, int, List[str]]:
    """
    Sync organizations with Stripe customers and update local records.
    Skips if Stripe API key is not configured.
    
    Returns:
        Tuple containing (total_orgs, successful_syncs, error_messages)
    """
    if not stripe_enabled():
        logger.warning("Stripe API key not configured - sync_stripe_customers skipped")
        return 0, 0, ["Stripe API key not configured"]

    logger.info("Starting sync of Stripe customers")
    
    try:
        # Get all organizations from MongoDB
        orgs = await db.organizations.find().to_list(length=None)
        total_orgs = len(orgs)
        local_org_ids = set(str(org["_id"]) for org in orgs)
        
        # Get all Stripe customers with org_id metadata
        stripe_org_ids, stripe_customer_map = await _get_stripe_customer_org_ids()
        
        # Find organizations that need Stripe syncing
        missing_from_stripe = local_org_ids - stripe_org_ids
        orphaned_in_stripe = stripe_org_ids - local_org_ids
        
        # Find existing payment customers that need stripe_customer_id updated
        existing_stripe_orgs = local_org_ids & stripe_org_ids
        payment_customers_needing_update = set()
        
        if existing_stripe_orgs:
            # Check which payment customers are missing stripe_customer_id
            for org_id in existing_stripe_orgs:
                payment_customer = await db.payments_customers.find_one({"org_id": org_id})
                if payment_customer and not payment_customer.get("stripe_customer_id"):
                    payment_customers_needing_update.add(org_id)
        
        logger.info(f"Total orgs: {total_orgs}")
        logger.info(f"Stripe customers: {len(stripe_org_ids)}")
        logger.info(f"Missing from Stripe: {len(missing_from_stripe)}")
        logger.info(f"Orphaned in Stripe: {len(orphaned_in_stripe)}")
        logger.info(f"Payment customers needing stripe_customer_id update: {len(payment_customers_needing_update)}")
        
        # Clean up orphaned Stripe customers
        if orphaned_in_stripe:
            logger.info(f"Cleaning up {len(orphaned_in_stripe)} orphaned Stripe customers")
            await _cleanup_orphaned_stripe_customers(db, orphaned_in_stripe, stripe_customer_map)
        
        # Combine orgs that need syncing: new Stripe customers + existing customers needing update
        orgs_to_sync = missing_from_stripe | payment_customers_needing_update
        
        if not orgs_to_sync:
            logger.info("All organizations have properly linked Stripe customers")
            return total_orgs, 0, []
        
        # Sync the organizations that need Stripe customers or updates
        return await _create_stripe_customer_set(db, orgs_to_sync)
    
    except Exception as e:
        logger.error(f"Error during Stripe customer sync: {e}")
        return 0, 0, [f"Global error: {str(e)}"]


async def sync_all_customers(db) -> Tuple[int, int, List[str]]:
    """
    Differential sync: sync organizations to both Stripe and payments_customers collection.
    Ensures all organizations have both Stripe customers and local payment customer records.
    
    Returns:
        Tuple containing (total_orgs, successful_syncs, error_messages)
    """
    logger.info("Starting differential sync of customers with Stripe and payments_customers")
    
    try:
        # First, ensure all orgs have local payment customers
        payments_result = await sync_payments_customers(db)
        
        # Then, sync with Stripe if configured
        stripe_result = await sync_stripe_customers(db)
        
        # Combine results
        total_orgs = max(payments_result[0], stripe_result[0])
        successful_syncs = payments_result[1] + stripe_result[1]
        errors = payments_result[2] + stripe_result[2]
        
        logger.info(f"Combined sync completed: {successful_syncs} total operations, {len(errors)} errors")
        return total_orgs, successful_syncs, errors
    
    except Exception as e:
        logger.error(f"Error during differential customer sync: {e}")
        return 0, 0, [f"Global error: {str(e)}"]

async def _get_stripe_customer_org_ids() -> Tuple[set, Dict[str, str]]:
    """Get all org_ids from Stripe customers metadata for the current product and return mapping to customer_ids"""
    try:
        org_ids = set()
        customer_map = {}  # org_id -> stripe_customer_id
        has_more = True
        starting_after = None
        
        while has_more:
            params = {"limit": 100}
            if starting_after:
                params["starting_after"] = starting_after
                
            customers = await StripeAsync.customer_list(**params)
            
            for customer in customers.data:
                # Only include customers that belong to this product
                customer_product = customer.metadata.get("product")
                if customer_product != STRIPE_PRODUCT_TAG:
                    continue  # Skip customers from other products (e.g., SigAgent)
                
                org_id = customer.metadata.get("org_id")
                if org_id:
                    org_ids.add(org_id)
                    customer_map[org_id] = customer.id
            
            has_more = customers.has_more
            if has_more and customers.data:
                starting_after = customers.data[-1].id
        
        return org_ids, customer_map
    
    except Exception as e:
        logger.error(f"Error getting Stripe customer org_ids: {e}")
        return set(), {}

async def _cleanup_orphaned_stripe_customers(db, orphaned_org_ids: set, stripe_customer_map: Dict[str, str]) -> Tuple[int, List[str]]:
    """Delete orphaned Stripe customers that don't have corresponding organizations"""
    deleted_count = 0
    errors = []
    
    logger.info(f"Starting cleanup of {len(orphaned_org_ids)} orphaned Stripe customers")
    
    for org_id in orphaned_org_ids:
        stripe_customer_id = stripe_customer_map.get(org_id)
        if not stripe_customer_id:
            continue
            
        try:
            # Check if customer has any active subscriptions
            subscriptions = await StripeAsync.subscription_list(customer=stripe_customer_id, status="active")
            
            if subscriptions.data:
                logger.warning(f"Skipping deletion of customer {stripe_customer_id} (org_id: {org_id}) - has active subscriptions")
                continue
            
            # Delete the customer from Stripe
            await StripeAsync.customer_delete(stripe_customer_id)
            
            # Also clean up from local payments_customers collection
            await db.payments_customers.delete_one({"org_id": org_id})
            
            deleted_count += 1
            logger.info(f"Deleted orphaned Stripe customer {stripe_customer_id} (org_id: {org_id})")
            
        except Exception as e:
            error_msg = f"Error deleting orphaned customer {stripe_customer_id} (org_id: {org_id}): {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    logger.info(f"Cleanup completed: {deleted_count} orphaned customers deleted")
    return deleted_count, errors

async def _cleanup_orphaned_payment_customers(db, orphaned_org_ids: set) -> Tuple[int, List[str]]:
    """Delete orphaned payment customers that don't have corresponding organizations"""
    deleted_count = 0
    errors = []
    
    logger.info(f"Starting cleanup of {len(orphaned_org_ids)} orphaned payment customers")
    
    for org_id in orphaned_org_ids:
        try:
            # Delete the payment customer record
            result = await db.payments_customers.delete_one({"org_id": org_id})
            if result.deleted_count > 0:
                deleted_count += 1
                logger.info(f"Deleted orphaned payment customer for org_id: {org_id}")
            
        except Exception as e:
            error_msg = f"Error deleting orphaned payment customer for org_id {org_id}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    logger.info(f"Payment customer cleanup completed: {deleted_count} orphaned records deleted")
    return deleted_count, errors


async def _create_payments_customer_set(db, org_ids_to_create: set) -> Tuple[int, int, List[str]]:
    """Create local payment customer records for organizations without Stripe API calls"""
    successful = 0
    errors = []
    
    # Process in batches of 10
    org_ids_list = list(org_ids_to_create)
    batch_size = 10
    
    for i in range(0, len(org_ids_list), batch_size):
        batch = org_ids_list[i:i + batch_size]
        
        # Create tasks for each org in the batch
        tasks = []
        for org_id in batch:
            task = _create_payments_customer(db, org_id=org_id)
            tasks.append(task)
        
        # Execute batch in parallel
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    error_msg = f"Error creating local payment customer for org {batch[idx]}: {str(result)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                elif result:
                    successful += 1
                else:
                    errors.append(f"Failed to create local payment customer for org {batch[idx]}")
        
        except Exception as e:
            error_msg = f"Error processing local payment customer batch: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        logger.info(f"Processed batch {i//batch_size + 1}/{(len(org_ids_list) + batch_size - 1)//batch_size}")
    
    logger.info(f"Local payment customer creation completed: {successful}/{len(org_ids_list)} customers created")
    return len(org_ids_list), successful, errors


async def _create_stripe_customer_set(db, org_ids_to_sync: set) -> Tuple[int, int, List[str]]:
    """Sync only the specified organization IDs with Stripe"""
    successful = 0
    errors = []
    
    # Process in batches of 10
    org_ids_list = list(org_ids_to_sync)
    batch_size = 10
    
    for i in range(0, len(org_ids_list), batch_size):
        batch = org_ids_list[i:i + batch_size]
        
        # Create tasks for each org in the batch
        tasks = []
        for org_id in batch:
            task = sync_customer(db, org_id=org_id)
            tasks.append(task)
        
        # Execute batch in parallel
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    error_msg = f"Error syncing Stripe customer for org {batch[idx]}: {str(result)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                elif result:
                    successful += 1
                else:
                    errors.append(f"Failed to create/get Stripe customer for org {batch[idx]}")
        
        except Exception as e:
            error_msg = f"Error processing Stripe sync batch: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        logger.info(f"Processed batch {i//batch_size + 1}/{(len(org_ids_list) + batch_size - 1)//batch_size}")
    
    logger.info(f"Stripe sync completed: {successful}/{len(org_ids_list)} customers synchronized")
    return len(org_ids_list), successful, errors


async def _create_payments_customer(db, org_id: str) -> Dict[str, Any]:
    """Create a local payment customer record without Stripe API calls"""
    logger.info(f"Creating local payment customer for org_id: {org_id}")

    try:
        # Get the org details
        org = await db.organizations.find_one({"_id": ObjectId(org_id)})
        if not org:
            logger.error(f"No organization found for org_id: {org_id}")
            return None
            
        org_name = org.get("name")

        # Get the first admin member
        user_id = None
        members = org.get("members", [])
        for member in members:
            if member.get("role") == "admin":
                user_id = str(member.get("user_id"))
                break
        
        if not user_id:
            logger.error(f"No admin member found for org_id: {org_id}")
            return None

        # Get the user details
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(f"No user found for user_id: {user_id} in org_id: {org_id}")
            return None
        
        user_name = user.get("name")
        user_email = user.get("email")

        if not user_name:
            logger.error(f"No user_name found for user_id: {user_id}")
            return None

        if not user_email:
            logger.error(f"No email found for user_id: {user_id}")
            return None

        # Check if customer already exists
        existing_customer = await db.payments_customers.find_one({"org_id": org_id})
        if existing_customer:
            logger.info(f"Local payment customer already exists for org_id: {org_id}")
            return existing_customer

        # Create new local payment customer with zero values
        customer = {
            "org_id": org_id,
            "user_id": user_id,
            "stripe_customer_id": None,  # No Stripe customer yet
            "user_name": user_name,
            "user_email": user_email,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
            # Initialize credit fields to zero
            "purchased_credits": 0,
            "purchased_credits_used": 0,
            "granted_credits": CREDIT_CONFIG["granted_credits"],
            "granted_credits_used": 0,
            # Initialize subscription fields to zero
            "subscription_spus_used": 0,
            "stripe_current_billing_period_start": None,
            "stripe_current_billing_period_end": None
        }

        await db.payments_customers.insert_one(customer)
        logger.info(f"Created local payment customer for org_id: {org_id}, user_id: {user_id}")

        return customer
    
    except Exception as e:
        logger.error(f"Error creating local payment customer for org_id {org_id}: {e}")
        raise e

async def get_payment_customer(db, org_id: str) -> Dict[str, Any]:
    """
    Get local payment customer data (fast, no Stripe API calls)
    Returns local MongoDB payment customer record
    """
    return await db.payments_customers.find_one({"org_id": org_id})

async def get_stripe_customer(db, org_id: str) -> Dict[str, Any]:
    """
    Get the Stripe customer for the given org_id (calls Stripe API - use sparingly)
    For most use cases, prefer get_payment_customer() which uses local data
    """
    if not stripe_enabled():
        # No-op if Stripe is not configured
        return None

    # First try local lookup for faster performance
    payment_customer = await get_payment_customer(db, org_id)
    if payment_customer and payment_customer.get("stripe_customer_id"):
        stripe_customer_id = payment_customer["stripe_customer_id"]
        try:
            # Direct Stripe customer retrieval (faster than search)
            stripe_customer = await StripeAsync._run_in_threadpool(
                stripe.Customer.retrieve, stripe_customer_id
            )
            if stripe_customer and not stripe_customer.get("deleted"):
                return stripe_customer
        except Exception as e:
            logger.warning(f"Could not retrieve Stripe customer {stripe_customer_id}: {e}")

    # Fallback to Stripe search - filter by product tag to avoid cross-product conflicts
    logger.info(f"Local lookup failed, searching Stripe for org_id: {org_id}")
    stripe_customer_list = await StripeAsync.customer_search(query=f"metadata['org_id']:'{org_id}' AND metadata['product']:'{STRIPE_PRODUCT_TAG}'")
        
    if stripe_customer_list and stripe_customer_list.data:
        # Filter results to ensure they belong to this product (search query might not be perfect)
        filtered_customers = [
            c for c in stripe_customer_list.data 
            if c.metadata.get("product") == STRIPE_PRODUCT_TAG
        ]
        
        if len(filtered_customers) > 1:
            logger.warning(f"Multiple Stripe customers found for org_id: {org_id} with product: {STRIPE_PRODUCT_TAG}")
        
        if filtered_customers:
            return filtered_customers[0]
    
    logger.info(f"No Stripe customers found for org_id: {org_id} with product: {STRIPE_PRODUCT_TAG}")
    return None

# Helper functions
async def sync_payments_customer(db, org_id: str) -> Dict[str, Any]:
    """Create or update local payment customer record (no Stripe API calls)"""

    logger.info(f"Syncing local payments customer for org_id: {org_id}")

    try:
        # Get organization details
        org = await db["organizations"].find_one({"_id": ObjectId(org_id)})
        if not org:
            logger.error(f"No organization found for org_id: {org_id}")
            return None
        
        logger.info(f"Organization: {org}")
            
        org_name = org.get("name")

        # Get the first admin member
        user_id = None
        members = org.get("members", [])
        for member in members:
            if member.get("role") == "admin":
                user_id = str(member.get("user_id"))
                break
        
        if not user_id:
            logger.error(f"No admin member found for org_id: {org_id}")
            return None

        # Get user details
        user = await db["users"].find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(f"No user found for user_id: {user_id} in org_id: {org_id}")
            return None
        
        user_name = user.get("name")
        user_email = user.get("email")

        if not user_name:
            logger.error(f"No user_name found for user_id: {user_id}")
            return None

        if not user_email:
            logger.error(f"No email found for user_id: {user_id}")
            return None

        logger.info(f"Syncing local payment customer for org_id: {org_id} user_id: {user_id} email: {user_email} name: {user_name}")

        # Check if local payment customer already exists
        customer = await db.payments_customers.find_one({"org_id": org_id})

        logger.info(f"Local payment customer: {customer}")
        
        if customer:
            logger.info(f"Updating existing local payment customer for org_id: {org_id}")
            # Update existing local payment customer
            await db.payments_customers.update_one(
                {"org_id": org_id},
                {"$set": {
                    "user_id": user_id,
                    "user_name": user_name,
                    "user_email": user_email,
                    "updated_at": datetime.now(UTC)
                }}
            )
            customer = await db.payments_customers.find_one({"org_id": org_id})
            logger.info(f"Updated local payment customer for org_id: {org_id}")
        else:
            logger.info(f"Creating new local payment customer for org_id: {org_id}")
            
            # Create new local payment customer
            customer = {
                "org_id": org_id,
                "user_id": user_id,
                "stripe_customer_id": None,  # No Stripe customer yet
                "user_name": user_name,
                "user_email": user_email,
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
                # Initialize credit fields to zero
                "purchased_credits": 0,
                "purchased_credits_used": 0,
                "granted_credits": CREDIT_CONFIG["granted_credits"],
                "granted_credits_used": 0,
                # Initialize subscription fields to zero
                "subscription_spus_used": 0,
                "stripe_current_billing_period_start": None,
                "stripe_current_billing_period_end": None
            }

            await db.payments_customers.insert_one(customer)
            customer = await db.payments_customers.find_one({"org_id": org_id})

        # Ensure credits are initialized
        await ensure_subscription_credits(db, customer)

        return customer
    
    except Exception as e:
        logger.error(f"Error in sync_payments_customer: {e}")
        raise e


async def sync_stripe_customer(db, org_id: str) -> Dict[str, Any]:
    """Create or update a Stripe customer for the given org_id"""
    
    if not stripe_enabled():
        logger.warning("Stripe API key not configured - sync_stripe_customer skipped")
        return None

    logger.info(f"Syncing Stripe customer for org_id: {org_id}")

    try:
        # Get organization and user details
        org = await db.organizations.find_one({"_id": ObjectId(org_id)})
        if not org:
            logger.error(f"No organization found for org_id: {org_id}")
            return None
            
        org_name = org.get("name")

        # Get the first admin member
        user_id = None
        members = org.get("members", [])
        for member in members:
            if member.get("role") == "admin":
                user_id = str(member.get("user_id"))
                break
        
        if not user_id:
            logger.error(f"No admin member found for org_id: {org_id}")
            return None

        # Get user details
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(f"No user found for user_id: {user_id} in org_id: {org_id}")
            return None
        
        user_name = user.get("name")
        user_email = user.get("email")
        user_description = f"{org_name} org admin"

        if not user_name or not user_email:
            logger.error(f"Missing user details for user_id: {user_id}")
            return None

        customer_metadata = {
            "org_id": org_id,
            "org_name": org_name,
            "user_id": user_id,
            "product": STRIPE_PRODUCT_TAG,  # Tag customers with product to avoid cross-product conflicts
            "updated_at": datetime.now(UTC).isoformat()
        }

        logger.info(f"Syncing Stripe customer for org_id: {org_id} user_id: {user_id} email: {user_email} name: {user_name}")

        # Search for existing Stripe customer
        stripe_customer = await get_stripe_customer(db, org_id)

        if stripe_customer:            
            # Check if customer needs updating
            stripe_customer_metadata = stripe_customer.metadata
            update_customer = False
            
            if (stripe_customer.name != user_name or 
                stripe_customer.email != user_email or 
                stripe_customer.description != user_description):
                update_customer = True

            for key in ["org_id", "org_name", "user_id", "product"]:
                if stripe_customer_metadata.get(key) != customer_metadata.get(key):
                    update_customer = True
                    break

            if update_customer:
                # Update the customer in Stripe
                await StripeAsync.customer_modify(
                    stripe_customer.id,
                    name=user_name,
                    email=user_email,
                    description=user_description,
                    metadata=customer_metadata
                )
                logger.info(f"Updated Stripe customer {stripe_customer.id}")
        else:
            # Create new customer in Stripe
            stripe_customer = await StripeAsync.customer_create(
                name=user_name,
                email=user_email,
                description=user_description,
                metadata=customer_metadata
            )
            logger.info(f"Created new Stripe customer {stripe_customer.id}")
        
        # Handle existing subscriptions
        org_type = org.get("type")
        existing_subscription = await get_stripe_subscription(db, stripe_customer.id)
        if existing_subscription:
            await set_subscription_type(db, org_id, stripe_customer.id, org_type)
            await sync_local_subscription_data(db, org_id, stripe_customer.id, existing_subscription)

        # Update local payment customer with Stripe customer ID
        payment_customer = await db.payments_customers.find_one({"org_id": org_id})
        if payment_customer:
            # Check if the stripe_customer_id changed
            if payment_customer.get("stripe_customer_id") != stripe_customer.id:
                logger.info(f"Stripe customer_id changed from {payment_customer.get('stripe_customer_id')} to {stripe_customer.id}")
                
            # Update with new Stripe customer ID
            await db.payments_customers.update_one(
                {"org_id": org_id},
                {"$set": {
                    "stripe_customer_id": stripe_customer.id,
                    "updated_at": datetime.now(UTC)
                }}
            )
            
            # Get updated customer
            payment_customer = await db.payments_customers.find_one({"org_id": org_id})
            
            # Ensure credits are initialized
            await ensure_subscription_credits(db, payment_customer)

        return stripe_customer
    
    except Exception as e:
        logger.error(f"Error in sync_stripe_customer: {e}")
        raise e


async def sync_customer(db, org_id: str) -> Dict[str, Any]:
    """Sync both local payment customer and Stripe customer for an organization"""
    
    logger.info(f"Syncing customer (both payments and Stripe) for org_id: {org_id}")

    try:
        # First, ensure local payment customer exists
        payment_customer = await sync_payments_customer(db=db, org_id=org_id)
        if not payment_customer:
            logger.error(f"Failed to sync local payment customer for org_id: {org_id}")
            return None

        # Then sync with Stripe if configured
        stripe_customer = await sync_stripe_customer(db, org_id)
        
        # Return the updated local payment customer
        return await db.payments_customers.find_one({"org_id": org_id})
    
    except Exception as e:
        logger.error(f"Error in sync_customer: {e}")
        raise e


async def save_usage_record(db, org_id: str, spus: int, operation: str, source: str = "backend") -> Dict[str, Any]:
    """Record usage for an organization locally"""
    
    logger.info(f"save_usage_record() called with org_id: {org_id}, spus: {spus}, operation: {operation}, source: {source}")

    # Store usage record (no Stripe dependencies)
    usage_record = {
        "org_id": org_id,
        "spus": spus,
        "operation": operation,
        "source": source,
        "timestamp": datetime.now(UTC)
    }
    
    await db.payments_usage_records.insert_one(usage_record)
    return usage_record



async def check_payment_limits(org_id: str, spus: int) -> bool:
    """Check if organization has hit payment limits using local data only (no Stripe API calls)"""

    logger.debug(f"Checking spu limits for org_id: {org_id} spus: {spus}")

    db = ad.common.get_async_db()

    payment_customer = await db.payments_customers.find_one({"org_id": org_id})
    if not payment_customer:
        raise ValueError(f"No customer found for org_id: {org_id}")

    await ensure_subscription_credits(db, payment_customer)

    # Get all subscription and credit data from local customer document (NO Stripe API calls)
    subscription_type = payment_customer.get("subscription_type")
    subscription_spu_allowance = payment_customer.get("subscription_spu_allowance", 0)
    subscription_spus_used = payment_customer.get("subscription_spus_used", 0)
    
    # Calculate subscription SPUs remaining
    subscription_spus_remaining = 0
    if subscription_spu_allowance:
        subscription_spus_remaining = max(subscription_spu_allowance - subscription_spus_used, 0)
    
    # Get credit information
    purchased_credits = payment_customer.get("purchased_credits", 0)
    purchased_used = payment_customer.get("purchased_credits_used", 0)
    purchased_remaining = max(purchased_credits - purchased_used, 0)
    
    granted_credits = payment_customer.get("granted_credits", CREDIT_CONFIG["granted_credits"])
    granted_used = payment_customer.get("granted_credits_used", 0)
    granted_remaining = max(granted_credits - granted_used, 0)
    
    # Calculate total available SPUs (subscription + credits)
    total_available = subscription_spus_remaining + purchased_remaining + granted_remaining
    
    # Enterprise plans allow overage - always return True
    if subscription_type == "enterprise":
        logger.info(f"Enterprise plan allows overage for org_id: {org_id}")
        return True
    
    # Individual and team plans block usage when credits are exhausted
    if total_available >= spus:
        logger.info(f"Sufficient spu credits available for org_id: {org_id} (available: {total_available}, requested: {spus})")
        return True
    else:
        logger.warning(f"Insufficient spu credits for org_id: {org_id} (available: {total_available}, requested: {spus})")
        raise SPUCreditException(org_id, spus, total_available)

async def sync_local_subscription_data(db, org_id: str, stripe_customer_id: str, subscription: Dict[str, Any]):
    """Sync subscription billing period and details to local stripe_customer document"""
    try:
        if not subscription or subscription.get("status") != "active":
            return
            
        # Get subscription details
        subscription_type = get_subscription_type(subscription)
        
        # Check if this is an enterprise customer (they should not have Stripe subscriptions)
        is_enterprise = await is_enterprise_customer(db, org_id)
        if is_enterprise:
            logger.warning(f"Enterprise customer {org_id} should not have Stripe subscription {subscription.get('id')}")
            return
        
        # Get billing period - try both API versions for compatibility
        current_period_start = None
        current_period_end = None
        subscription_item_id = None
        
        # Try new API (2025-03-31+): billing periods in subscription items
        subscription_items = subscription.get("items", {}).get("data", [])
        if subscription_items:
            subscription_item = subscription_items[0]
            subscription_item_id = subscription_item.get("id")
            current_period_start = subscription_item.get("current_period_start")
            current_period_end = subscription_item.get("current_period_end")
        
        # Fallback to legacy API (pre-2025-03-31): billing periods in subscription
        if not current_period_start or not current_period_end:
            current_period_start = subscription.get("current_period_start")
            current_period_end = subscription.get("current_period_end")
        
        if not current_period_start or not current_period_end:
            logger.error(f"No billing period found in subscription {subscription.get('id')} for org {org_id}")
            return
            
        # Get subscription SPU allowance
        subscription_spu_allowance = 0
        if subscription_type in TIER_LIMITS:
            subscription_spu_allowance = TIER_LIMITS[subscription_type]
        
        # Update local customer document with subscription data
        update_data = {
            "subscription_type": subscription_type,
            "stripe_subscription_status": subscription.get("status"),
            "stripe_subscription_id": subscription.get("id"),
            "stripe_subscription_item_id": subscription_item_id,
            "stripe_current_billing_period_start": current_period_start,
            "stripe_current_billing_period_end": current_period_end,
            "subscription_spu_allowance": subscription_spu_allowance,
            "subscription_updated_at": datetime.now(UTC)
        }
        
        # Set stripe_payments_portal_enabled to True for any non-enterprise subscription (never revert back to False)
        if subscription_type != 'enterprise':
            update_data["stripe_payments_portal_enabled"] = True
        
        await db.payments_customers.update_one(
            {"org_id": org_id},
            {"$set": update_data}
        )
        
        logger.info(f"Synced local subscription data for org {org_id}: {subscription_type} plan, period {current_period_start}-{current_period_end}")
        
    except Exception as e:
        logger.error(f"Error syncing local subscription data for org {org_id}: {e}")

async def delete_payments_customer(db, org_id: str) -> Dict[str, Any]:
    """
    Delete a Stripe customer and remove from local collection.
    The customer remains in Stripe where it's kept forever and can be retrieved later.
    
    Args:
        org_id: The org ID of the Stripe customer to delete
        force: If True, delete even if there are active subscriptions
        db: Database connection (optional, will be created if not provided)
        
    Returns:
        Dictionary with status information about the operation
    """

    logger.info(f"Deleting Stripe customer for org_id: {org_id}")
    
    try:
        # Find local customer record
        customer = await db.payments_customers.find_one({"org_id": org_id})
        if not customer:
            logger.warning(f"No local customer found for org_id: {org_id}")
            return {"success": False, "reason": "Customer not found"}
            
        if stripe_enabled():
            stripe_customer_id = customer["stripe_customer_id"]
            
            # Cancel any active Stripe subscription first
            try:
                stripe_subscription = await get_stripe_subscription(db, stripe_customer_id)
                if stripe_subscription:
                    await StripeAsync.subscription_delete(stripe_subscription.id)
                    logger.info(f"Deleted subscription {stripe_subscription.get('id')} for customer {stripe_customer_id}")
            except Exception as e:
                logger.warning(f"Error deleting subscription for customer {stripe_customer_id}: {e}")

            # Delete the Stripe customer (it remains recoverable in Stripe)
            await StripeAsync.customer_delete(stripe_customer_id)
            logger.info(f"Deleted Stripe customer: {stripe_customer_id}")
        
        # Remove from our local collection
        await db.payments_customers.delete_one({"org_id": org_id})
        logger.info(f"Removed local customer record for org_id: {org_id}")
        
        return {
            "success": True, 
            "customer_id": stripe_customer_id,
            "deleted_at": datetime.now(UTC)
        }
        
    except Exception as e:
        logger.error(f"Error deleting Stripe customer: {e}")
        return {"success": False, "error": str(e)}



async def is_enterprise_customer(db, org_id: str) -> bool:
    """Check if an organization is an enterprise customer"""
    org = await db["organizations"].find_one({"_id": ObjectId(org_id)})
    if not org:
        return False
    return org.get("type") == "enterprise"

async def get_current_billing_period() -> tuple:
    """Get current month billing period boundaries as unix timestamps"""
    now = datetime.now(UTC)
    period_start = datetime(now.year, now.month, 1)
    
    # Next month start
    if now.month == 12:
        period_end = datetime(now.year + 1, 1, 1)
    else:
        period_end = datetime(now.year, now.month + 1, 1)
    
    return int(period_start.timestamp()), int(period_end.timestamp())

async def get_billing_period_for_customer(db, org_id: str) -> tuple:
    """Get billing period boundaries from local customer data (no Stripe API calls)"""
    # Get local customer data
    customer = await db.payments_customers.find_one({"org_id": org_id})
    if not customer:
        return None, None
    
    # Check if we have local billing period data
    period_start = customer.get("stripe_current_billing_period_start")
    period_end = customer.get("stripe_current_billing_period_end")
    subscription_type = customer.get("subscription_type")
    
    if period_start and period_end:
        return period_start, period_end
    
    # If no local billing period but customer has subscription type, we may need to sync
    if subscription_type:
        # For enterprise, use calendar month
        is_enterprise = await is_enterprise_customer(db, org_id)
        if is_enterprise:
            return await get_current_billing_period()
    
    # No active subscription or billing period
    return None, None

async def get_stripe_subscription(db, customer_id: str) -> Dict[str, Any]:
    """Get a subscription for a customer"""
    stripe_subscription_list = await StripeAsync.subscription_list(customer=customer_id)
    if not stripe_subscription_list or not stripe_subscription_list.get("data"):
        return None

    subscriptions = stripe_subscription_list.get("data")
    n_subscriptions = len(subscriptions)
    
    if n_subscriptions > 1:
        # Log detailed information about the multiple subscriptions for debugging
        logger.error(f"FATAL: Multiple subscriptions detected for customer {customer_id}")
        for i, sub in enumerate(subscriptions):
            logger.error(f"  Subscription {i+1}: {sub.get('id')} - Status: {sub.get('status')} - Created: {sub.get('created')}")
            items = sub.get('items', {}).get('data', [])
            for item in items:
                price = item.get('price', {})
                logger.error(f"    Item: {item.get('id')} - Price: {price.get('id')} - Amount: {price.get('unit_amount')}")
        
        raise ValueError(f"FATAL: Customer {customer_id} has {n_subscriptions} subscriptions. Only one subscription per customer is allowed. This indicates a bug in subscription management.")
    elif n_subscriptions == 0:
        return None
    
    return subscriptions[0]

def get_subscription_type(subscription: Dict[str, Any]) -> str:
    """Get the subscription type from subscription metadata"""
    # First try to get from metadata
    subscription_type = subscription.get("metadata", {}).get("subscription_type")
    if subscription_type:
        return subscription_type


async def set_subscription_type(db, org_id: str, customer_id: str, subscription_type: str):
    """Enable a subscription for a customer with proper proration"""

    tier_config = await get_tier_config(db, org_id)
    
    if subscription_type not in tier_config.keys():
        raise ValueError(f"Invalid subscription type: {subscription_type}")

    # Skip enterprise - they don't use Stripe
    if subscription_type == "enterprise":
        logger.info(f"Skipping Stripe subscription for enterprise org {org_id}")
        return True

    base_price_id = tier_config[subscription_type]["base_price_id"]
    
    if not base_price_id:
        raise ValueError(f"No base price configured for subscription type: {subscription_type}")

    # Get the current subscription
    subscription = await get_stripe_subscription(db, customer_id)
    
    if subscription:
        update_subscription = False
        subscription_items = subscription.get("items", {}).get("data", [])
        
        # Check if we need to update the subscription
        current_subscription_type = get_subscription_type(subscription)
        if current_subscription_type != subscription_type:
            update_subscription = True
        
        # Check if the subscription has the correct base price (should have only 1 item now)
        if len(subscription_items) != 1:
            update_subscription = True
        else:
            current_base_price_id = subscription_items[0].get("price", {}).get("id")
            if current_base_price_id != base_price_id:
                update_subscription = True

        if update_subscription:
            logger.info(f"Updating subscription {subscription.id} from {current_subscription_type} to {subscription_type}, base_price_id {base_price_id}")

            # Build items list: explicitly delete old items and add new ones
            items = []
            
            # First, mark all existing items for deletion
            for item in subscription_items:
                items.append({'id': item['id'], 'deleted': True})
                logger.info(f"Marking subscription item {item['id']} for deletion")
            
            # Then add the new item with the correct price
            items.append({'price': base_price_id})
            logger.info(f"Adding new subscription item with price {base_price_id}")

            # Prepare subscription modification parameters
            modify_params = {
                'items': items,
                'proration_behavior': 'create_prorations',
                'metadata': {'subscription_type': subscription_type}
            }
            
            # If subscription is set to cancel at period end, reactivate it
            if subscription.get('cancel_at_period_end', False):
                modify_params['cancel_at_period_end'] = False
                logger.info(f"Reactivating subscription {subscription.id} that was set to cancel at period end")

            # Modify existing subscription with proration and metadata
            await StripeAsync.subscription_modify(subscription.id, **modify_params)
            logger.info(f"Successfully updated subscription {subscription.id} to {subscription_type}")
        else:
            # Even if no subscription update is needed, check if we need to reactivate a cancelling subscription
            if subscription.get('cancel_at_period_end', False):
                await StripeAsync.subscription_modify(
                    subscription.id,
                    cancel_at_period_end=False
                )
                logger.info(f"Reactivated subscription {subscription.id} that was set to cancel at period end")
    else:
        # Create new subscription for customers without one (base pricing only)
        await StripeAsync.subscription_create(
            customer=customer_id,
            items=[{'price': base_price_id}],
            payment_behavior='default_incomplete',
            expand=['latest_invoice.payment_intent'],
            metadata={'subscription_type': subscription_type}
        )

    # Set stripe_payments_portal_enabled to True for any non-enterprise subscription (never revert back to False)
    if subscription_type != 'enterprise':
        await db.payments_customers.update_one(
            {"org_id": org_id},
            {"$set": {"stripe_payments_portal_enabled": True}}
        )
        logger.info(f"Set stripe_payments_portal_enabled=True for org {org_id} with {subscription_type} subscription")

    return True

@payments_router.post("/v0/orgs/{organization_id}/payments/customer-portal")
async def customer_portal(
    organization_id: str,
    current_user: User = Depends(get_org_admin_user)
) -> PortalSessionResponse:
    """Generate a customer portal link or return empty URL if not available"""

    logger.info(f"Generating customer portal for org_id: {organization_id}")

    db = ad.common.get_async_db()

    # Get customer data to check stripe_payments_portal_enabled flag
    customer = await db.payments_customers.find_one({"org_id": organization_id})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Check if stripe payments portal is available
    stripe_payments_portal_enabled = customer.get("stripe_payments_portal_enabled", False)
    if not stripe_payments_portal_enabled:
        logger.info(f"Payment portal not available for org_id: {organization_id}")
        return PortalSessionResponse(payment_portal_url="", stripe_enabled=stripe_enabled())

    try:
        # Generate Stripe portal when stripe_payments_portal is true
        logger.info(f"Stripe customer found for org_id: {organization_id}: {customer['stripe_customer_id']}")
        session = await StripeAsync.billing_portal_session_create(
            customer=customer["stripe_customer_id"],
            return_url=f"{NEXTAUTH_URL}/settings/organizations/{organization_id}/subscription?tab=plans",
        )
        logger.info(f"Stripe customer portal URL: {session.url}")
        return PortalSessionResponse(payment_portal_url=session.url, stripe_enabled=stripe_enabled())
    except Exception as e:
        logger.error(f"Error generating customer portal: {e}")
        return PortalSessionResponse(payment_portal_url="", stripe_enabled=stripe_enabled())

@payments_router.post("/v0/orgs/{organization_id}/payments/checkout-session")
async def create_checkout_session(
    organization_id: str,
    request: CheckoutSessionRequest,
    current_user: User = Depends(get_admin_or_org_user)
) -> PortalSessionResponse:
    """Create a Stripe Checkout session for subscription setup"""

    plan_id = request.plan_id
    logger.info(f"Creating checkout session for org_id: {organization_id}, plan: {plan_id}")

    db = ad.common.get_async_db()

    # Check if user is trying to select Enterprise plan without admin privileges
    if plan_id == 'enterprise':
        is_sys_admin = await is_system_admin(current_user.user_id)
        
        if not is_sys_admin:
            raise HTTPException(
                status_code=403, 
                detail="Enterprise plan requires admin privileges"
            )
        
        # Enterprise plans don't use Stripe - handle locally
        try:
            # First, check for and cancel any existing Stripe subscription with proration
            customer = await db.payments_customers.find_one({"org_id": organization_id})
            if customer and customer.get("stripe_customer_id"):
                stripe_customer_id = customer["stripe_customer_id"]
                try:
                    existing_subscription = await get_stripe_subscription(db, stripe_customer_id)
                    if existing_subscription:
                        # Cancel existing subscription immediately with proration (creates credit)
                        logger.info(f"Canceling existing subscription {existing_subscription.get('id')} for Enterprise upgrade with proration")
                        await StripeAsync.subscription_delete(
                            existing_subscription.get('id'),
                            prorate=True  # This creates a prorated credit on the customer's account
                        )
                        logger.info(f"Successfully canceled subscription {existing_subscription.get('id')} with prorated credit")
                        
                        # Update local payment customer to reflect enterprise upgrade
                        await db.payments_customers.update_one(
                            {"org_id": organization_id},
                            {"$set": {
                                "subscription_type": "enterprise",
                                "stripe_subscription_status": "canceled",
                                "stripe_subscription_id": None,
                                "stripe_subscription_item_id": None,
                                "stripe_current_billing_period_start": None,
                                "stripe_current_billing_period_end": None,
                                "subscription_spu_allowance": None,  # Enterprise has no SPU limits
                                "subscription_updated_at": datetime.now(UTC)
                            }}
                        )
                except ValueError as e:
                    if "FATAL" in str(e):
                        logger.error(f"Multiple subscriptions detected during Enterprise upgrade for customer {stripe_customer_id}")
                        raise HTTPException(status_code=500, detail="Multiple subscriptions detected. Please contact support before upgrading to Enterprise.")
                    else:
                        logger.warning(f"Error checking subscription during Enterprise upgrade: {e}")
            
            # Update organization type to enterprise
            await db.organizations.update_one(
                {"_id": ObjectId(organization_id)},
                {"$set": {"type": "enterprise"}}
            )
            
            logger.info(f"Updated organization {organization_id} to enterprise plan")
            
            # Return success URL to redirect back to subscription page
            success_url = f"{NEXTAUTH_URL}/settings/organizations/{organization_id}/subscription?success=true&tab=plans"
            return PortalSessionResponse(payment_portal_url=success_url, stripe_enabled=stripe_enabled())
            
        except Exception as e:
            logger.error(f"Error updating organization to enterprise: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update organization: {str(e)}")

    try:
        is_org_admin = await is_organization_admin(organization_id, current_user.user_id)

        if not is_org_admin:
            raise HTTPException(status_code=403, detail="You are not authorized to create a checkout session")

        # Get the customer
        customer = await db.payments_customers.find_one({"org_id": organization_id})
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # Check if customer already has an active subscription
        stripe_customer_id = customer["stripe_customer_id"]
        try:
            existing_subscription = await get_stripe_subscription(db, stripe_customer_id)
            if existing_subscription:
                # Customer has existing subscription - modify it directly instead of using Checkout
                logger.info(f"Customer {stripe_customer_id} has existing subscription {existing_subscription.get('id')}, using direct subscription modification instead of Checkout")
                
                success = await set_subscription_type(db, organization_id, stripe_customer_id, plan_id)
                if success:
                    # Return success URL directly since we modified the subscription
                    success_url = f"{NEXTAUTH_URL}/settings/organizations/{organization_id}/subscription?success=true&tab=plans"
                    return PortalSessionResponse(payment_portal_url=success_url, stripe_enabled=stripe_enabled())
                else:
                    raise HTTPException(status_code=500, detail="Failed to update subscription")
        except ValueError as e:
            if "FATAL" in str(e):
                # Multiple subscriptions detected - this is a critical error
                logger.error(f"Multiple subscriptions detected for customer {stripe_customer_id}, cannot proceed with checkout")
                raise HTTPException(status_code=500, detail="Multiple subscriptions detected. Please contact support.")
            else:
                # Other subscription errors, continue with checkout
                logger.warning(f"Error checking existing subscription: {e}")
        
        # No existing subscription - proceed with normal Stripe Checkout flow
        logger.info(f"Customer {stripe_customer_id} has no existing subscription, proceeding with Stripe Checkout")
        
        # Get tier configuration
        tier_config = await get_tier_config(db, organization_id)
        if plan_id not in tier_config:
            raise HTTPException(status_code=400, detail=f"Invalid plan: {plan_id}")
        
        # Get price ID for the plan (base pricing only)
        base_price_id = tier_config[plan_id]["base_price_id"]
        
        if not base_price_id:
            raise HTTPException(status_code=500, detail=f"Price configuration not found for plan: {plan_id}")
        
        # Create checkout session for new subscription
        session = await StripeAsync._run_in_threadpool(
            stripe.checkout.Session.create,
            customer=customer["stripe_customer_id"],
            payment_method_types=['card'],
            line_items=[
                {
                    'price': base_price_id,
                    'quantity': 1,
                }
            ],
            mode='subscription',
            success_url=f"{NEXTAUTH_URL}/settings/organizations/{organization_id}/subscription?success=true&tab=plans",
            cancel_url=f"{NEXTAUTH_URL}/settings/organizations/{organization_id}/subscription?canceled=true&tab=plans",
            metadata={
                'org_id': organization_id,
                'plan_id': plan_id,
                'user_id': current_user.user_id
            },
            subscription_data={
                'metadata': {
                    'subscription_type': plan_id,
                    'org_id': organization_id
                }
            }
        )
        
        logger.info(f"Created Stripe checkout session: {session.id}, URL: {session.url}")
        return PortalSessionResponse(payment_portal_url=session.url, stripe_enabled=stripe_enabled())
        
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@payments_router.post("/v0/orgs/{organization_id}/payments/usage")
async def record_usage(
    organization_id: str,
    usage: UsageRecord,
    current_user: User = Depends(get_current_user)
):
    """Record usage for an organization"""

    logger.info(f"api_record_usage called with org_id: {organization_id}, spus: {usage.spus}, operation: {usage.operation}, source: {usage.source}")

    # Check if the current user is a member of the organization
    if not await is_organization_member(org_id=organization_id, user_id=current_user.user_id):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied, user {current_user.user_id} is not a member of organization {organization_id}"
        )

    try:
        result = await record_payment_usage(
            organization_id,
            usage.spus,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Helper functions for webhook handlers
def extract_customer_id_from_event(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract customer_id from different Stripe webhook event types.
    Returns customer_id if found, None otherwise.
    """
    event_type = event.get("type", "")
    event_object = event.get("data", {}).get("object", {})
    
    # Subscription events have customer directly
    if "subscription" in event_type:
        return event_object.get("customer")
    
    # Invoice events have customer directly
    if "invoice" in event_type:
        return event_object.get("customer")
    
    # Checkout session events have customer directly
    if "checkout.session" in event_type:
        return event_object.get("customer")
    
    # For other event types, try to get customer from the object
    return event_object.get("customer")

async def verify_customer_product_tag(customer_id: str) -> bool:
    """
    Verify that a Stripe customer belongs to our product.
    Uses local payments_customers collection for fast lookup (no Stripe API call).
    Returns True if customer belongs to our product, False otherwise.
    """
    try:
        db = ad.common.get_async_db()
        
        # Fast check: if customer exists in our local payments_customers with this stripe_customer_id,
        # it means we've synced them and they have our product tag
        customer = await db.payments_customers.find_one({"stripe_customer_id": customer_id})
        if customer:
            return True
        
        # Customer not found in local DB - they're not our customer
        # (No need to check Stripe API - if we haven't synced them, they're not ours)
        return False
    except Exception as e:
        logger.error(f"Error verifying product tag for customer {customer_id}: {e}")
        return False

async def handle_subscription_updated(db, subscription: Dict[str, Any]):
    """Handle subscription created or updated event"""
    logger.info(f"Handling subscription updated event for subscription_id {subscription['id']}")
    
    try:
        # Get org_id from subscription metadata or customer metadata
        customer_id = subscription.get("customer")
        if not customer_id:
            logger.error(f"No customer_id found in subscription {subscription['id']}")
            return
            
        # Find our local customer record
        customer = await db.payments_customers.find_one({"stripe_customer_id": customer_id})
        if not customer:
            logger.error(f"No local customer found for Stripe customer {customer_id}")
            return
            
        org_id = customer.get("org_id")
        if not org_id:
            logger.error(f"No org_id found for Stripe customer {customer_id}")
            return
        
        # Sync the subscription data locally
        await sync_local_subscription_data(db, org_id, customer_id, subscription)
        logger.info(f"Synced subscription data for org {org_id} from webhook")
        
    except Exception as e:
        logger.error(f"Error handling subscription updated webhook: {e}")

async def handle_subscription_deleted(db, subscription: Dict[str, Any]):
    """Handle subscription deleted event"""
    logger.info(f"Handling subscription deleted event for subscription_id: {subscription['id']}")
    
    try:
        # Get org_id from subscription metadata or customer metadata
        customer_id = subscription.get("customer")
        if not customer_id:
            logger.error(f"No customer_id found in subscription {subscription['id']}")
            return
            
        # Find our local customer record
        customer = await db.payments_customers.find_one({"stripe_customer_id": customer_id})
        if not customer:
            logger.error(f"No local customer found for Stripe customer {customer_id}")
            return
            
        org_id = customer.get("org_id")
        if not org_id:
            logger.error(f"No org_id found for Stripe customer {customer_id}")
            return
        
        # Check if this is an enterprise customer (don't clear their subscription_type)
        is_enterprise = await is_enterprise_customer(db, org_id)
        
        # Clear subscription data from local customer record
        update_data = {
            "stripe_subscription_status": "canceled",
            "stripe_subscription_id": None,
            "stripe_subscription_item_id": None,
            "stripe_current_billing_period_start": None,
            "stripe_current_billing_period_end": None,
            "subscription_spu_allowance": 0,
            "subscription_updated_at": datetime.now(UTC)
        }
        
        # Only clear subscription_type and allowance for non-enterprise customers
        if not is_enterprise:
            update_data["subscription_type"] = None
        # Enterprise customers keep their subscription_type="enterprise" and unlimited allowance
        
        await db.payments_customers.update_one(
            {"org_id": org_id},
            {"$set": update_data}
        )
        
        logger.info(f"Cleared subscription data for org {org_id} from webhook")
        
    except Exception as e:
        logger.error(f"Error handling subscription deleted webhook: {e}")

async def handle_invoice_created(db, invoice: Dict[str, Any]):
    """Handle invoice.created event - triggers at the start of a new billing period"""
    logger.info(f"Handling invoice created event for invoice_id {invoice['id']}")
    
    try:
        # Only process subscription invoices (not one-time payments)
        subscription_id = invoice.get("subscription")
        if not subscription_id:
            logger.info(f"Invoice {invoice['id']} is not for a subscription, skipping")
            return
            
        # Get the subscription to access billing period information
        subscription = await StripeAsync._run_in_threadpool(
            stripe.Subscription.retrieve, subscription_id
        )
        
        if not subscription:
            logger.error(f"Could not retrieve subscription {subscription_id} for invoice {invoice['id']}")
            return
            
        # Find our local customer record
        customer_id = subscription.get("customer")
        if not customer_id:
            logger.error(f"No customer_id found in subscription {subscription_id}")
            return
            
        customer = await db.payments_customers.find_one({"stripe_customer_id": customer_id})
        if not customer:
            logger.error(f"No local customer found for Stripe customer {customer_id}")
            return
            
        org_id = customer.get("org_id")
        if not org_id:
            logger.error(f"No org_id found for Stripe customer {customer_id}")
            return
        
        # Sync the updated billing period information
        await sync_local_subscription_data(db, org_id, customer_id, subscription)
        logger.info(f"Updated billing period for org {org_id} from invoice.created webhook")
        
    except Exception as e:
        logger.error(f"Error handling invoice created webhook: {e}")

async def handle_invoice_payment_succeeded(db, invoice: Dict[str, Any]):
    """Handle invoice.payment_succeeded event - confirms successful billing period payment"""
    logger.info(f"Handling invoice payment succeeded event for invoice_id {invoice['id']}")
    
    try:
        # Only process subscription invoices
        subscription_id = invoice.get("subscription")
        if not subscription_id:
            logger.info(f"Invoice {invoice['id']} is not for a subscription, skipping")
            return
            
        # Find our local customer record via subscription
        customer_id = invoice.get("customer")
        if not customer_id:
            logger.error(f"No customer_id found in invoice {invoice['id']}")
            return
            
        customer = await db.payments_customers.find_one({"stripe_customer_id": customer_id})
        if not customer:
            logger.error(f"No local customer found for Stripe customer {customer_id}")
            return
            
        org_id = customer.get("org_id")
        if not org_id:
            logger.error(f"No org_id found for Stripe customer {customer_id}")
            return
        
        # Reset subscription SPU usage for the new billing period
        await db.payments_customers.update_one(
            {"org_id": org_id},
            {"$set": {
                "subscription_spus_used": 0,  # Reset usage for new billing period
                "subscription_updated_at": datetime.now(UTC)
            }}
        )
        
        logger.info(f"Reset subscription SPU usage for org {org_id} after successful payment")
        
    except Exception as e:
        logger.error(f"Error handling invoice payment succeeded webhook: {e}")


async def delete_all_payments_customers(dryrun: bool = True) -> Dict[str, Any]:
    """
    Permanently delete all customers from Stripe
    
    WARNING: This is a destructive operation that cannot be undone. It will:
    1. Delete all customers from Stripe
    2. Remove all customer records from the local database
    3. Delete all related subscriptions and usage records
    
    Args:
        confirm: Safety flag that must be set to True to perform deletion
        
    Returns:
        Dictionary with status information about the operation
    """
    
    logger.warning("Starting deletion of ALL Stripe customers")

    db = ad.common.get_async_db()
    
    deleted_count = 0
    failed_count = 0
    error_messages = []
    
    try:
        # First get all customers from Stripe
        has_more = True
        starting_after = None
        batch_size = 10
        
        while has_more:
            # Fetch customers in batches
            params = {"limit": batch_size}
            if starting_after:
                params["starting_after"] = starting_after
                
            customers = await StripeAsync.customer_list(**params)

            tasks = []
            
            # Process each customer in the batch
            for customer in customers.data:
                # First cancel any active subscriptions
                subscriptions = await StripeAsync.subscription_list(customer=customer.id)
                for subscription in subscriptions.data:
                    if not dryrun:
                        tasks.append(StripeAsync.subscription_delete(subscription.id))
                        logger.info(f"Deleting subscription {subscription.id} for customer {customer.id}")
                    else:
                        logger.info(f"Would have deleted subscription {subscription.id} for customer {customer.id}")
            
            await asyncio.gather(*tasks)

            tasks = []
             # Process each customer in the batch
            for customer in customers.data:
                # Delete the customer
                if not dryrun:
                    tasks.append(StripeAsync.customer_delete(customer.id))
                    deleted_count += 1
                    logger.info(f"Deleted Stripe customer: {customer.id}")
                else:
                    logger.info(f"Would have deleted Stripe customer: {customer.id}")
               

            await asyncio.gather(*tasks)
            
            # Check if there are more customers to process
            has_more = customers.has_more
            if has_more and customers.data:
                starting_after = customers.data[-1].id
        
        # Now clean up our local database
        try:
            if not dryrun:
                # Delete all local records
                await db.payments_customers.delete_many({"org_id": {"$exists": True}})
                logger.info("Deleted all local Stripe customer records")
            else:
                logger.info("Would have deleted all local Stripe customer records")
        except Exception as e:
            error_msg = f"Error cleaning up local database: {str(e)}"
            logger.error(error_msg)
            error_messages.append(error_msg)
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "errors": error_messages,
            "warning": "All Stripe customers have been permanently deleted."
        }
        
    except Exception as e:
        logger.error(f"Error during bulk deletion: {e}")
        return {"success": False, "error": str(e)}

@payments_router.get("/v0/orgs/{organization_id}/payments/subscription")
async def get_subscription_info(
    organization_id: str = None,
    current_user: User = Depends(get_admin_or_org_user)
) -> SubscriptionResponse:
    """Get available subscription plans and user's current plan"""

    logger.info(f"Getting subscription plans for org_id: {organization_id} user_id: {current_user.user_id}")

    db = ad.common.get_async_db()

    # Get the customer
    customer = await db.payments_customers.find_one({"org_id": organization_id})
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer not found for org_id: {organization_id}")
    
    tier_config = await get_tier_config(db, organization_id)

    if tier_config["individual"]["included_spus"] is not None:
        individual_price_per_spu = tier_config["individual"]["base_price"] / tier_config["individual"]["included_spus"]
        individual_included_spus = tier_config["individual"]["included_spus"]
    else:
        individual_price_per_spu = 0.0
        individual_included_spus = 0

    if tier_config["team"]["included_spus"] is not None:
        team_price_per_spu = tier_config["team"]["base_price"] / tier_config["team"]["included_spus"]
        team_included_spus = tier_config["team"]["included_spus"]
    else:
        team_price_per_spu = 0.0
        team_included_spus = 0

    if stripe_enabled():
        individual_features = [
            f"${format_price_per_spu(individual_price_per_spu)} per SPU",
            f"{individual_included_spus:,} SPUs per month",
            "Basic document processing",
            f"Additional SPUs at ${CREDIT_CONFIG['price_per_credit']:.2f} each"
        ]
        team_features = [
            f"${format_price_per_spu(team_price_per_spu)} per SPU",
            f"{team_included_spus:,} SPUs per month",
            "Advanced document processing",
            "Team collaboration features",
            f"Additional SPUs at ${CREDIT_CONFIG['price_per_credit']:.2f} each"
        ]
    else:
        individual_features = [
            "Basic document processing",
            "Custom pricing - contact sales"
        ]
        team_features = [
            "Advanced document processing",
            "Team collaboration features",
            "Custom pricing - contact sales"
        ]

    
    # Define the available plans with SPU allowances
    plans = [
        SubscriptionPlan(
            plan_id="individual",
            name="Individual",
            base_price=tier_config["individual"]["base_price"],
            included_spus=individual_included_spus,
            features=individual_features
        ),
        SubscriptionPlan(
            plan_id="team",
            name="Team", 
            base_price=tier_config["team"]["base_price"],
            included_spus=team_included_spus,
            features=team_features
        )
    ]
    
    # Add enterprise plan for all users (access control handled by frontend)
    plans.append(SubscriptionPlan(
        plan_id="enterprise",
        name="Enterprise",
        base_price=0.0,  # Custom pricing
        included_spus=0,  # Unlimited
        features=[
            "Custom document processing",
            "Dedicated support",
            "Custom pricing - contact sales"
        ]
    ))

    # Check if this is an enterprise customer
    is_enterprise = await is_enterprise_customer(db, organization_id)
    
    # Initialize billing period variables
    current_subscription_type = None
    subscription_status = None
    current_period_start, current_period_end = await get_current_billing_period()
    cancel_at_period_end = False
    
    if is_enterprise:
        # Enterprise customers use calendar months
        current_subscription_type = "enterprise"
        subscription_status = "active"  # Enterprise is always active
    elif not stripe_enabled():
        pass
    else:
        # Get the Stripe customer and subscription for non-enterprise customers
        stripe_customer = await get_stripe_customer(db, organization_id)

        if not stripe_customer:
            raise HTTPException(status_code=404, detail=f"Stripe customer not found for org_id: {organization_id}")

        # Get the subscription
        subscription = await get_stripe_subscription(db, stripe_customer.id)
        
        if not subscription:
            # No subscription found - use calendar month for unsubscribed organizations
            current_subscription_type = None
            subscription_status = "no_subscription"
            
            # Use current calendar month for unsubscribed organizations
            start_ts, end_ts = await get_current_billing_period()
            current_period_start = start_ts
            current_period_end = end_ts
        else:
            current_subscription_type = get_subscription_type(subscription)
            subscription_status = subscription.status
            
            # Check if subscription is set to cancel at period end
            cancel_at_period_end = subscription.get('cancel_at_period_end', False)
            
            # For subscribed organizations, use their billing period from Stripe
            subscription_period_start = subscription.get('current_period_start')
            subscription_period_end = subscription.get('current_period_end')
            
            # Try to get billing period from subscription items (new API)
            subscription_items = subscription.get("items", {}).get("data", [])
            if subscription_items and not subscription_period_start:
                subscription_item = subscription_items[0]
                subscription_period_start = subscription_item.get("current_period_start")
                subscription_period_end = subscription_item.get("current_period_end")
            
            if subscription_period_start and subscription_period_end:
                current_period_start = subscription_period_start
                current_period_end = subscription_period_end
            else:
                # Fallback to calendar month if no billing period found
                logger.warning(f"No billing period found for subscription {subscription.get('id')}, using calendar month")
                start_ts, end_ts = await get_current_billing_period()
                current_period_start = start_ts
                current_period_end = end_ts
            
            # If subscription is active but set to cancel at period end, show as "cancelling"
            if subscription_status == 'active' and cancel_at_period_end:
                subscription_status = 'cancelling'
    
    # Get stripe_payments_portal_enabled flag from customer data (defaults to False if not set)
    stripe_payments_portal_enabled = customer.get("stripe_payments_portal_enabled", False)
    
    return SubscriptionResponse(
        plans=plans, 
        current_plan=current_subscription_type,
        subscription_status=subscription_status,
        cancel_at_period_end=cancel_at_period_end,
        current_period_start=current_period_start,
        current_period_end=current_period_end,
        stripe_payments_portal_enabled=stripe_payments_portal_enabled,
        stripe_enabled=stripe_enabled()
    )

async def handle_activate_subscription(org_id: str, org_type: str, customer_id: str) -> bool:
    """Activate a subscription"""
    
    if not stripe_enabled():
        logger.info("Stripe API key not configured - handle_activate_subscription aborted")
        return False

    db = ad.common.get_async_db()

    try:
        # Get the current subscription
        subscription = await get_stripe_subscription(db, customer_id)
        if subscription:       
            # Check if subscription is set to cancel at period end
            if not subscription.get('cancel_at_period_end', False):
                logger.info(f"Subscription for customer_id: {customer_id} is not set to cancel at period end")
                return True  # Already active
            
            # Reactivate the subscription by removing cancel_at_period_end
            await StripeAsync.subscription_modify(
                subscription.id,
                cancel_at_period_end=False
            )
            
            logger.info(f"Reactivated subscription {subscription.id} for customer_id: {customer_id}")

        else:
            # Sync the subscription type with the organization type
            await sync_subscription(db, org_id, org_type)
            
            logger.info(f"Created new subscription for customer_id: {customer_id}")

        return True
        
    except Exception as e:
        logger.error(f"Error reactivating subscription: {e}")
        return False

async def sync_subscription(db, org_id: str, org_type: str) -> bool:
    """
    Sync organization type with subscription type in Stripe
    """
    if not stripe_enabled():
        logger.info(f"Stripe not configured - skipping subscription sync for org {org_id}")
        return True

    try:
        # Organization type is now the same as subscription type
        subscription_type = org_type

        # Get the Stripe customer
        stripe_customer = await get_stripe_customer(db, org_id)
        if not stripe_customer:
            logger.warning(f"No Stripe customer found for org {org_id}")
            return False

        # Set the subscription type in Stripe (this will now include metadata)
        success = await set_subscription_type(db, org_id, stripe_customer.id, subscription_type)
        if success:
            logger.info(f"Synced org {org_id} type {org_type} to subscription {subscription_type}")
        
        return success

    except Exception as e:
        logger.error(f"Error syncing organization subscription: {e}")
        return False

@payments_router.put("/v0/orgs/{organization_id}/payments/subscription")
async def activate_subscription(
    organization_id: str,
    current_user: User = Depends(get_current_user)
):
    """Activate a subscription"""
    
    logger.info(f"Activating subscription for org_id: {organization_id}")

    is_sys_admin = await is_system_admin(current_user.user_id)
    is_org_admin = await is_organization_admin(org_id=organization_id, user_id=current_user.user_id)

    if not is_sys_admin and not is_org_admin:
        raise HTTPException(status_code=403, detail="You are not authorized to activate a subscription")

    db = ad.common.get_async_db()

    org = await db.organizations.find_one({"_id": ObjectId(organization_id)})
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization not found: {organization_id}")

    org_type = org.get("type", "individual")

    # Check if this is an enterprise customer
    is_enterprise = await is_enterprise_customer(db, organization_id)
    
    if is_enterprise:
        # Enterprise subscriptions are always active - no action needed
        return {"status": "success", "message": "Enterprise subscription is always active"}

    try:
        # Get the customer for non-enterprise plans
        stripe_customer = await get_stripe_customer(db, organization_id)
        if not stripe_customer:
            raise HTTPException(status_code=404, detail=f"Stripe customer not found for org_id: {organization_id}")

        success = await handle_activate_subscription(organization_id, org_type, stripe_customer.id)
        if success:
            return {"status": "success", "message": "Subscription activated successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to activate subscription")

    except Exception as e:
        logger.error(f"Error activating subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@payments_router.delete("/v0/orgs/{organization_id}/payments/subscription")
async def deactivate_subscription(
    organization_id: str,
    current_user: User = Depends(get_current_user)
):
    """Cancel a subscription at the end of the current period"""
    
    logger.info(f"Deactivating subscription for org_id: {organization_id}")

    is_sys_admin = await is_system_admin(current_user.user_id)
    is_org_admin = await is_organization_admin(org_id=organization_id, user_id=current_user.user_id)

    if not is_sys_admin and not is_org_admin:
        raise HTTPException(status_code=403, detail="You are not authorized to cancel a subscription")

    db = ad.common.get_async_db()

    # Check if this is an enterprise customer
    is_enterprise = await is_enterprise_customer(db, organization_id)
    
    if is_enterprise:
        # Enterprise subscriptions cannot be cancelled via API - contact sales
        raise HTTPException(
            status_code=400, 
            detail="Enterprise subscriptions must be cancelled by contacting sales"
        )

    try:
        # Get the customer for non-enterprise plans
        stripe_customer = await get_stripe_customer(db, organization_id)
        if not stripe_customer:
            raise HTTPException(status_code=404, detail=f"Stripe customer not found for org_id: {organization_id}")

        # Get the current subscription
        subscription = await get_stripe_subscription(db, stripe_customer.id)
        if not subscription:
            raise HTTPException(status_code=404, detail=f"No active subscription found for org_id: {organization_id}")

        # Cancel the subscription at period end
        await StripeAsync.subscription_modify(
            subscription.id,
            cancel_at_period_end=True
        )
        
        logger.info(f"Cancelled subscription {subscription.id} for customer_id: {stripe_customer.id}")
        return {"status": "success", "message": "Subscription cancelled successfully"}

    except Exception as e:
        logger.error(f"Error cancelling subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@payments_router.get("/v0/orgs/{organization_id}/payments/usage/range")
async def get_usage_range(
    organization_id: str,
    request: UsageRangeRequest = Depends(),
    current_user: User = Depends(get_current_user)
) -> UsageRangeResponse:
    """Get SPU usage data for a date range with daily granularity"""
    
    # Check if user has access to this organization
    if not await is_organization_admin(org_id=organization_id, user_id=current_user.user_id) and not await is_system_admin(user_id=current_user.user_id):
        raise HTTPException(
            status_code=403,
            detail=f"Org admin access required for org_id: {organization_id}"
        )

    db = ad.common.get_async_db()

    try:
        # Parse start and end dates from request
        start_dt = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
        
        # Aggregate usage data by day
        pipeline = [
            {
                "$match": {
                    "org_id": organization_id,
                    "timestamp": {
                        "$gte": start_dt,
                        "$lt": end_dt
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$timestamp"},
                        "month": {"$month": "$timestamp"},
                        "day": {"$dayOfMonth": "$timestamp"}
                    },
                    "total_spus": {"$sum": "$spus"},
                    "operations": {"$addToSet": "$operation"},
                    "sources": {"$addToSet": "$source"}
                }
            },
            {
                "$sort": {
                    "_id.year": 1,
                    "_id.month": 1,
                    "_id.day": 1
                }
            }
        ]
        
        results = await db.payments_usage_records.aggregate(pipeline).to_list(length=None)
        
        # Process results
        data_points = []
        total_spus = 0
        
        for result in results:
            # Format date as YYYY-MM-DD
            date_str = f"{result['_id']['year']:04d}-{result['_id']['month']:02d}-{result['_id']['day']:02d}"
            
            spus = result['total_spus']
            total_spus += spus
            
            # Get the most common operation and source for this day
            operation = result['operations'][0] if result['operations'] else 'unknown'
            source = result['sources'][0] if result['sources'] else 'unknown'
            
            data_points.append(UsageDataPoint(
                date=date_str,
                spus=spus,
                operation=operation,
                source=source
            ))
        
        return UsageRangeResponse(
            data_points=data_points,
            total_spus=total_spus
        )
        
    except Exception as e:
        logger.error(f"Error getting usage range: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@payments_router.get("/v0/orgs/{organization_id}/payments/usage")
async def get_current_usage(
    organization_id: str,
    current_user: User = Depends(get_current_user)
) -> UsageResponse:
    # Check if user has access to this organization
    if not await is_organization_admin(org_id=organization_id, user_id=current_user.user_id) and not await is_system_admin(user_id=current_user.user_id):
        raise HTTPException(
            status_code=403,
            detail=f"Org admin access required for org_id: {organization_id}"
        )

    db = ad.common.get_async_db()

    try:
        customer = await db.payments_customers.find_one({"org_id": organization_id})
        if not customer:
            raise HTTPException(status_code=404, detail=f"No customer found for org_id: {organization_id}")
        
        await ensure_subscription_credits(db, customer)
        
        # Get subscription information
        period_start = None
        period_end = None
        subscription_type = None  # Default to None (no active plan)
        usage_unit = "spu"
        subscription_spu_allowance = 0
        subscription_spus_used = 0
        subscription_spus_remaining = 0
        
        # Get billing period boundaries (works for both enterprise and non-enterprise)
        period_start, period_end = await get_billing_period_for_customer(db, organization_id)
        
        # Check if this is an enterprise customer
        is_enterprise = await is_enterprise_customer(db, organization_id)
        
        if is_enterprise:
            subscription_type = "enterprise"
            subscription_spu_allowance = None  # Unlimited
        else:
            # Get subscription info from local customer data (NO Stripe API calls)
            subscription_type = customer.get("subscription_type")
            subscription_spu_allowance = customer.get("subscription_spu_allowance", 0)

        # Get subscription SPU usage from customer record
        subscription_spus_used = customer.get("subscription_spus_used", 0)
        
        # Calculate remaining SPUs (only for non-enterprise plans)
        if subscription_spu_allowance is not None:
            subscription_spus_remaining = max(subscription_spu_allowance - subscription_spus_used, 0)
        else:
            subscription_spus_remaining = 0  # Enterprise has unlimited
        
        # Get separate credit information
        purchased_credits = customer.get("purchased_credits", 0)
        purchased_used = customer.get("purchased_credits_used", 0)
        purchased_remaining = max(purchased_credits - purchased_used, 0)
        
        granted_credits = customer.get("granted_credits", CREDIT_CONFIG["granted_credits"])
        granted_used = customer.get("granted_credits_used", 0)
        granted_remaining = max(granted_credits - granted_used, 0)

        # --- Calculate both period and total metered usage ---
        period_metered_usage = 0
        total_metered_usage = 0
        
        # Period metered usage (paid usage for current billing period)
        if period_start and period_end:
            period_agg = await db.payments_usage_records.aggregate([
                {
                    "$match": {
                        "org_id": organization_id,
                        "operation": "paid_usage",
                        "timestamp": {
                            "$gte": datetime.fromtimestamp(period_start),
                            "$lte": datetime.fromtimestamp(period_end)
                        }
                    }
                },
                {"$group": {"_id": None, "total": {"$sum": "$spus"}}}
            ]).to_list(1)
            if period_agg and period_agg[0].get("total"):
                period_metered_usage = period_agg[0]["total"]
        
        # Total metered usage (all paid usage ever)
        total_agg = await db.payments_usage_records.aggregate([
            {"$match": {"org_id": organization_id, "operation": "paid_usage"}},
            {"$group": {"_id": None, "total": {"$sum": "$spus"}}}
        ]).to_list(1)
        if total_agg and total_agg[0].get("total"):
            total_metered_usage = total_agg[0]["total"]

        return UsageResponse(
            usage_source="stripe",
            data=UsageData(
                period_metered_usage=period_metered_usage,
                total_metered_usage=total_metered_usage,
                remaining_included=subscription_spus_remaining,  # Now shows subscription SPU remaining
                subscription_type=subscription_type,
                usage_unit=usage_unit,
                purchased_credits=purchased_credits,
                purchased_credits_used=purchased_used,
                purchased_credits_remaining=purchased_remaining,
                granted_credits=granted_credits,
                granted_credits_used=granted_used,
                granted_credits_remaining=granted_remaining,
                period_start=period_start,
                period_end=period_end,
            )
        )
        
    except Exception as e:
        logger.error(f"Error getting usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@payments_router.post("/v0/account/payments/webhook", status_code=200)
async def webhook_received(
    request: Request,
):
    """Handle Stripe webhook events"""

    try:
        event = await StripeAsync.webhook_construct_event(
            await request.body(),
            request.headers.get("stripe-signature"),
            stripe_webhook_secret
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Extract customer_id and verify product tag before processing
    customer_id = extract_customer_id_from_event(event)
    if customer_id:
        # Verify customer belongs to our product - silently skip if not
        if not await verify_customer_product_tag(customer_id):
            # Webhook is for a different product - this is normal, return success without processing
            return {"status": "success", "skipped": "different_product"}
    
    logger.info(f"Stripe webhook event received: {event['type']}")

    db = ad.common.get_async_db()

    # Store event in database for audit (only for our product)
    event_doc = {
        "stripe_event_id": event["id"],
        "type": event["type"],
        "data": event["data"],
        "created": datetime.fromtimestamp(event["created"]),
        "processed": False,
        "created_at": datetime.now(UTC)
    }
    await db.stripe_events.insert_one(event_doc)
    
    # Process different event types
    if event["type"] == "customer.subscription.created" or event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        await handle_subscription_updated(db, subscription)
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        await handle_subscription_deleted(db, subscription)
    elif event["type"] == "invoice.created":
        invoice = event["data"]["object"]
        await handle_invoice_created(db, invoice)
    elif event["type"] == "invoice.payment_succeeded":
        invoice = event["data"]["object"]
        await handle_invoice_payment_succeeded(db, invoice)
    elif event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        # Check if this is a subscription checkout or credit purchase
        if session.get("mode") == "subscription":
            await handle_checkout_session_completed(db, session)
        else:
            # Handle credit purchase
            await credit_customer_account_from_session(db, session)
    
    # Mark event as processed
    await db.stripe_events.update_one(
        {"stripe_event_id": event["id"]},
        {"$set": {"processed": True, "processed_at": datetime.now(UTC)}}
    )
    
    return {"status": "success"}

# Ensure credits are initialized for a stripe_customer
async def ensure_subscription_credits(db, stripe_customer_doc):
    update = {}
    # Add new fields for separate tracking
    if "purchased_credits" not in stripe_customer_doc:
        update["purchased_credits"] = 0
    if "purchased_credits_used" not in stripe_customer_doc:
        update["purchased_credits_used"] = 0
    if "granted_credits" not in stripe_customer_doc:
        update["granted_credits"] = CREDIT_CONFIG["granted_credits"]
    if "granted_credits_used" not in stripe_customer_doc:
        update["granted_credits_used"] = 0
    
    # Add subscription SPU tracking fields
    if "subscription_spus_used" not in stripe_customer_doc:
        update["subscription_spus_used"] = 0
    if "stripe_current_billing_period_start" not in stripe_customer_doc:
        update["stripe_current_billing_period_start"] = None
    if "stripe_current_billing_period_end" not in stripe_customer_doc:
        update["stripe_current_billing_period_end"] = None
    
    # If the customer has ever purchased credits (now or in the past), enable portal access
    try:
        purchased_total = stripe_customer_doc.get("purchased_credits", 0)
        purchased_used = stripe_customer_doc.get("purchased_credits_used", 0)
        if (purchased_total and purchased_total > 0) or (purchased_used and purchased_used > 0):
            update["stripe_payments_portal_enabled"] = True
    except Exception:
        pass

    if update:
        await db.payments_customers.update_one(
            {"_id": stripe_customer_doc["_id"]},
            {"$set": update}
        )

# Helper functions for improved usage tracking

async def get_current_balances(db, org_id: str) -> Dict[str, Any]:
    """Get current balances for an organization (fresh from database)"""
    customer = await db.payments_customers.find_one({"org_id": org_id})
    if not customer:
        raise Exception(f"No customer found for org_id: {org_id}")
    
    is_enterprise = await is_enterprise_customer(db, org_id)
    subscription_type = customer.get("subscription_type")
    subscription_spu_allowance = customer.get("subscription_spu_allowance", 0)
    
    # Handle enterprise unlimited allowance properly
    if is_enterprise or subscription_spu_allowance is None:
        subscription_spu_allowance = None  # Unlimited
        subscription_spus_remaining = float('inf')  # Unlimited
    else:
        subscription_spus_used = customer.get("subscription_spus_used", 0)
        subscription_spus_remaining = max(subscription_spu_allowance - subscription_spus_used, 0)
    
    # Get credit balances
    purchased_credits = customer.get("purchased_credits", 0)
    purchased_used = customer.get("purchased_credits_used", 0)
    purchased_remaining = max(purchased_credits - purchased_used, 0)
    
    granted_credits = customer.get("granted_credits", CREDIT_CONFIG["granted_credits"])
    granted_used = customer.get("granted_credits_used", 0)
    granted_remaining = max(granted_credits - granted_used, 0)
    
    return {
        "customer_id": customer["_id"],
        "is_enterprise": is_enterprise,
        "subscription_type": subscription_type,
        "subscription_spu_allowance": subscription_spu_allowance,
        "subscription_spus_remaining": subscription_spus_remaining,
        "purchased_remaining": purchased_remaining,
        "granted_remaining": granted_remaining
    }

def calculate_consumption_breakdown(spus: int, balances: Dict[str, Any]) -> Dict[str, int]:
    """Calculate how SPUs should be consumed across different sources"""
    if spus <= 0:
        return {"from_subscription": 0, "from_purchased": 0, "from_granted": 0, "from_paid": 0}
    
    # Consumption order: subscription → purchased → granted → paid
    subscription_remaining = balances["subscription_spus_remaining"]
    purchased_remaining = balances["purchased_remaining"]
    granted_remaining = balances["granted_remaining"]
    
    # Handle unlimited subscription (enterprise)
    if subscription_remaining == float('inf'):
        from_subscription = spus
        from_purchased = 0
        from_granted = 0
        from_paid = 0
    else:
        from_subscription = min(spus, subscription_remaining)
        remaining_after_subscription = spus - from_subscription
        
        from_purchased = min(remaining_after_subscription, purchased_remaining)
        remaining_after_purchased = remaining_after_subscription - from_purchased
        
        from_granted = min(remaining_after_purchased, granted_remaining)
        from_paid = remaining_after_purchased - from_granted
        
        # For non-enterprise plans, paid usage (overage) should not occur
        if from_paid > 0 and not balances["is_enterprise"]:
            logger.warning(f"Unexpected overage for {balances['subscription_type']} plan: {from_paid} SPUs")
    
    return {
        "from_subscription": from_subscription,
        "from_purchased": from_purchased,
        "from_granted": from_granted,
        "from_paid": from_paid
    }

async def update_customer_balances(db, customer_id: str, consumption: Dict[str, int]) -> None:
    """Update customer balances atomically"""
    update_operations = {}
    
    if consumption["from_subscription"] > 0:
        update_operations["subscription_spus_used"] = consumption["from_subscription"]
    
    if consumption["from_purchased"] > 0:
        update_operations["purchased_credits_used"] = consumption["from_purchased"]
    
    if consumption["from_granted"] > 0:
        update_operations["granted_credits_used"] = consumption["from_granted"]
    
    if update_operations:
        await db.payments_customers.update_one(
            {"_id": customer_id},
            {"$inc": update_operations}
        )

async def save_complete_usage_record(db, org_id: str, spus: int, consumption: Dict[str, int], 
                                   operation: str = "document_processing", source: str = "backend",
                                   llm_provider: str = None,
                                   llm_model: str = None,
                                   prompt_tokens: int = None,
                                   completion_tokens: int = None,
                                   total_tokens: int = None,
                                   actual_cost: float = None) -> Dict[str, Any]:
    """Save complete usage record with breakdown and LLM metrics"""
    usage_record = {
        "org_id": org_id,
        "spus": spus,
        "operation": operation,
        "source": source,
        "timestamp": datetime.now(UTC),
    }
    
    # Add LLM metrics if provided
    if llm_provider is not None:
        usage_record["llm_provider"] = llm_provider
    if llm_model is not None:
        usage_record["llm_model"] = llm_model
    if prompt_tokens is not None:
        usage_record["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        usage_record["completion_tokens"] = completion_tokens
    if total_tokens is not None:
        usage_record["total_tokens"] = total_tokens
    if actual_cost is not None:
        usage_record["actual_cost"] = actual_cost
    
    await db.payments_usage_records.insert_one(usage_record)
    
    # Also save paid usage record if there's overage (for compatibility with existing queries)
    if consumption["from_paid"] > 0:
        await save_usage_record(db, org_id, consumption["from_paid"], operation="paid_usage", source=source)
    
    return usage_record

def should_reset_billing_period(customer: Dict[str, Any], new_period_start: int) -> bool:
    """Check if billing period needs to be reset"""
    if not new_period_start:
        return False
    
    customer_period_start = customer.get("stripe_current_billing_period_start")
    return customer_period_start != new_period_start

async def reset_billing_period(db, customer: Dict[str, Any], period_start: int, period_end: int) -> None:
    """Reset billing period and subscription SPU usage atomically"""
    subscription_spu_allowance = customer.get("subscription_spu_allowance", 0)
    has_spu_allowance = subscription_spu_allowance is not None and subscription_spu_allowance > 0
    
    update_data = {
        "stripe_current_billing_period_start": period_start,
        "stripe_current_billing_period_end": period_end
    }
    
    # Only reset SPU usage for plans that have limits (not enterprise)
    if has_spu_allowance:
        update_data["subscription_spus_used"] = 0
    
    await db.payments_customers.update_one(
        {"_id": customer["_id"]},
        {"$set": update_data}
    )
    
    logger.info(f"Reset billing period for customer {customer['_id']}: {period_start} to {period_end}")

async def record_payment_usage(org_id: str, spus: int,
                              llm_provider: str = None,
                              llm_model: str = None,
                              prompt_tokens: int = None, 
                              completion_tokens: int = None, 
                              total_tokens: int = None, 
                              actual_cost: float = None) -> Dict[str, int]:
    """Record payment usage with proper SPU consumption order and atomic updates"""
    if spus <= 0:
        logger.warning(f"Invalid SPU amount: {spus} for org_id: {org_id}")
        return {"from_subscription": 0, "from_purchased": 0, "from_granted": 0, "from_paid": 0}

    db = ad.common.get_async_db()
    
    try:
        # 1. Get customer and ensure fields are initialized
        customer = await db.payments_customers.find_one({"org_id": org_id})
        if not customer:
            raise Exception(f"No customer found for org_id: {org_id}")
        
        await ensure_subscription_credits(db, customer)
        
        # 2. Handle billing period management (enterprise vs subscription)
        current_period_start, current_period_end = await get_billing_period_for_customer(db, org_id)
        
        # 3. Check for billing period reset (atomic operation)
        if should_reset_billing_period(customer, current_period_start):
            await reset_billing_period(db, customer, current_period_start, current_period_end)
        
        # 4. Get current balances (fresh from DB after potential reset)
        balances = await get_current_balances(db, org_id)
        
        # 5. Calculate consumption order: subscription → purchased → granted → paid
        consumption = calculate_consumption_breakdown(spus, balances)
        
        # 6. Update customer balances atomically
        await update_customer_balances(db, balances["customer_id"], consumption)
        
        # 7. Record complete usage record with breakdown and LLM metrics
        await save_complete_usage_record(db, org_id, spus, consumption, 
                                       operation="document_processing",
                                       llm_provider=llm_provider,
                                       llm_model=llm_model,
                                       prompt_tokens=prompt_tokens,
                                       completion_tokens=completion_tokens,
                                       total_tokens=total_tokens,
                                       actual_cost=actual_cost)
        
        return consumption
        
    except Exception as e:
        logger.error(f"Error recording payment usage for org_id {org_id}: {e}")
        raise

# Admin API to add credits
@payments_router.post("/v0/orgs/{organization_id}/payments/credits/add")
async def add_spu_credits(
    organization_id: str,
    update: CreditUpdate,
    current_user: User = Depends(get_current_user)
):
    logger.info(f"Adding {update.amount} admin credits to org {organization_id}")

    if not await is_system_admin(current_user.user_id):
        raise HTTPException(status_code=403, detail="Admin only")

    db = ad.common.get_async_db()   
    customer = await db.payments_customers.find_one({"org_id": organization_id})
    if not customer:
        raise HTTPException(status_code=404, detail="No customer for org")
    await ensure_subscription_credits(db, customer)
    await db.payments_customers.update_one(
        {"_id": customer["_id"]},
        {"$inc": {"granted_credits": update.amount}}
    )
    return {"success": True, "added": update.amount}

@payments_router.get("/v0/orgs/{organization_id}/payments/credits/config")
async def get_payments_credit_config(
    organization_id: str,
    current_user: User = Depends(get_admin_or_org_user)
):
    """Get credit purchase configuration"""
    
    return {
        "price_per_credit": CREDIT_CONFIG["price_per_credit"],
        "currency": CREDIT_CONFIG["currency"],
        "min_cost": CREDIT_CONFIG["min_cost"],
        "max_cost": CREDIT_CONFIG["max_cost"]
    }

@payments_router.post("/v0/orgs/{organization_id}/payments/credits/purchase")
async def purchase_credits(
    organization_id: str,
    request: PurchaseCreditsRequest,
    current_user: User = Depends(get_current_user)
):
    """Create a Stripe checkout session for credit purchase with dynamic pricing"""
    
    logger.info(f"purchase_credits called for org_id: {organization_id}, credits: {request.credits}")
    
    if not await is_organization_member(org_id=organization_id, user_id=current_user.user_id):
        logger.error(f"Access denied for user {current_user.user_id} to org {organization_id}")
        raise HTTPException(status_code=403, detail="Access denied")

    db = ad.common.get_async_db()

    # Calculate total cost for the requested credits
    total_cost = request.credits * CREDIT_CONFIG["price_per_credit"]
    
    # Validate cost limits instead of credit limits
    if total_cost < CREDIT_CONFIG["min_cost"]:
        logger.error(f"Purchase cost too low: ${total_cost:.2f} (minimum: ${CREDIT_CONFIG['min_cost']})")
        raise HTTPException(
            status_code=400, 
            detail=f"Purchase amount must be at least ${CREDIT_CONFIG['min_cost']} (you requested ${total_cost:.2f})"
        )
    
    if total_cost > CREDIT_CONFIG["max_cost"]:
        logger.error(f"Purchase cost too high: ${total_cost:.2f} (maximum: ${CREDIT_CONFIG['max_cost']})")
        raise HTTPException(
            status_code=400, 
            detail=f"Purchase amount cannot exceed ${CREDIT_CONFIG['max_cost']} (you requested ${total_cost:.2f})"
        )
    
    # Get or create Stripe customer
    stripe_customer = await get_stripe_customer(db, organization_id)
    if not stripe_customer:
        logger.info(f"No existing Stripe customer for org {organization_id}, creating one")
        await sync_customer(db, organization_id)
        stripe_customer = await get_stripe_customer(db, organization_id)
    
    if not stripe_customer:
        logger.error(f"Failed to create Stripe customer for org {organization_id}")
        raise HTTPException(status_code=500, detail="Failed to create Stripe customer")
    
    logger.info(f"Using Stripe customer: {stripe_customer.id}")
    
    try:
        # Calculate total amount in dollars
        total_amount_usd = request.credits * CREDIT_CONFIG["price_per_credit"]
        amount_cents = int(total_amount_usd * 100)
        
        logger.info(f"Calculated amount: ${total_amount_usd} ({amount_cents} cents)")

        # Create Stripe checkout session with dynamic pricing
        # Use product_data instead of product to create a new product on-the-fly
        session = await StripeAsync._run_in_threadpool(
            stripe.checkout.Session.create,
            customer=stripe_customer.id,
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': CREDIT_CONFIG["currency"],
                    'unit_amount': amount_cents,
                    'product_data': {
                        'name': f'{request.credits} SPU Credits',
                        'description': f'Purchase {request.credits} SPU credits (${total_amount_usd:.2f})',
                        'metadata': {
                            'type': 'spu_credits',
                            'credits': str(request.credits)
                        }
                    }
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={
                'org_id': organization_id,
                'credits': str(request.credits),
                'user_id': current_user.user_id,
                'spu_amount': str(request.credits),
                'customer_id': organization_id
            }
        )
        
        logger.info(f"Created Stripe checkout session: {session.id}, URL: {session.url}")
        
        return PurchaseCreditsResponse(
            checkout_url=session.url,
            session_id=session.id
        )
        
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {str(e)}")

async def credit_customer_account_from_session(db, session: Dict[str, Any]):
    """Credit customer account after successful Checkout session"""
    
    try:
        # Idempotency guard: ensure we only credit once per Checkout session
        session_id = session.get("id")
        if not session_id:
            logger.error("Checkout session missing id; skipping crediting")
            return

        already_processed = await db.payments_credit_transactions.find_one({"session_id": session_id})
        if already_processed:
            logger.info(f"Checkout session {session_id} already processed for credits; skipping duplicate credit")
            return

        metadata = session.get("metadata", {})
        org_id = metadata.get("org_id")
        credits = int(metadata.get("credits", 0))
        
        if not org_id or not credits:
            logger.error(f"Missing metadata in checkout session: {session['id']}")
            return
        
        # Add credits to the organization
        customer = await db.payments_customers.find_one({"org_id": org_id})
        if not customer:
            logger.error(f"No customer found for org: {org_id}")
            return
        
        await ensure_subscription_credits(db, customer)
        await db.payments_customers.update_one(
            {"_id": customer["_id"]},
            {"$inc": {"purchased_credits": credits}}
        )

        # Enable Stripe portal for customers who purchased credits
        await db.payments_customers.update_one(
            {"_id": customer["_id"]},
            {"$set": {"stripe_payments_portal_enabled": True}}
        )
        
        # Record processed transaction for idempotency and audit
        try:
            await db.payments_credit_transactions.insert_one({
                "session_id": session_id,
                "org_id": org_id,
                "credits": credits,
                "created_at": datetime.now(UTC)
            })
        except Exception as e:
            # If insert fails due to race/dup, log and continue
            logger.warning(f"Could not record credit transaction for session {session_id}: {e}")
        
        logger.info(f"Credited {credits} purchased SPUs to organization {org_id} from checkout session {session['id']}")
        
    except Exception as e:
        logger.error(f"Error processing checkout session completion: {e}")
        logger.error(f"Error processing checkout session completion: {e}")

# Update the webhook handler to handle checkout.session.completed for subscriptions
async def handle_checkout_session_completed(db, session: Dict[str, Any]):
    """Handle checkout session completed event"""
    try:
        
        metadata = session.get("metadata", {})
        org_id = metadata.get("org_id")
        plan_id = metadata.get("plan_id")
        
        if not org_id or not plan_id:
            logger.error(f"Missing metadata in checkout session: {session['id']}")
            return
        
        # The subscription should already be created by Stripe
        # We just need to ensure our local state is updated
        logger.info(f"Checkout session completed for org {org_id}, plan {plan_id}")
        
        # Refresh the customer data to ensure we have the latest subscription info
        await sync_customer(db, org_id)
        
    except Exception as e:
        logger.error(f"Error processing checkout session completion: {e}")