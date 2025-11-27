"""
Simple tests for payments system in non-Stripe mode.
Tests basic workspace setup and payment plan verification.
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, UTC
from bson import ObjectId

# Import payment functions
from app.routes.payments import (
    sync_payments_customer,
    get_payment_customer,
    check_payment_limits,
    save_usage_record,
    CREDIT_CONFIG,
    SPUCreditException
)

# Import database utilities
import analytiq_data as ad


@pytest_asyncio.fixture
async def individual_workspace(test_db):
    """Create a test organization and user for individual workspace testing."""
    db = test_db
    
    # Create a test user
    user_data = {
        "name": "Test User",
        "email": "test@example.com",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    }
    user_result = await db.users.insert_one(user_data)
    user_id = str(user_result.inserted_id)
    
    # Create a test organization
    org_data = {
        "name": "Test Individual Org",
        "type": "individual",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "members": [
            {
                "user_id": ObjectId(user_id),
                "role": "admin"
            }
        ]
    }
    org_result = await db.organizations.insert_one(org_data)
    org_id = str(org_result.inserted_id)
    
    yield {
        "org_id": org_id,
        "user_id": user_id,
        "org_data": org_data,
        "user_data": user_data
    }
    
    # Cleanup
    await db.users.delete_one({"_id": ObjectId(user_id)})
    await db.organizations.delete_one({"_id": ObjectId(org_id)})
    await db.payments_customers.delete_one({"org_id": org_id})
    await db.payments_usage_records.delete_many({"org_id": org_id})


@pytest.mark.asyncio
async def test_payments_initialization(test_db):
    """Test that payments system initializes correctly."""
    # Check that default credit config is set
    assert CREDIT_CONFIG["granted_credits"] == 100
    assert isinstance(CREDIT_CONFIG["price_per_credit"], float)


@pytest.mark.asyncio
async def test_create_individual_workspace_payment_customer(individual_workspace, test_db):
    """Test creating a payment customer for an individual workspace."""
    org_id = individual_workspace["org_id"]
    
    # Sync payment customer (creates local record)

    customer = await sync_payments_customer(db=test_db, org_id=org_id)
    
    # Verify customer was created
    assert customer is not None
    assert customer["org_id"] == org_id
    assert customer["user_id"] == individual_workspace["user_id"]
    assert customer["user_name"] == "Test User"
    assert customer["user_email"] == "test@example.com"
    assert customer["stripe_customer_id"] is None  # No Stripe in test mode
    
    # Verify credit initialization
    assert customer["purchased_credits"] == 0
    assert customer["purchased_credits_used"] == 0
    assert customer["granted_credits"] == CREDIT_CONFIG["granted_credits"]
    assert customer["granted_credits_used"] == 0
    
    # Verify subscription fields
    assert customer["subscription_spus_used"] == 0
    assert customer["stripe_current_billing_period_start"] is None
    assert customer["stripe_current_billing_period_end"] is None


@pytest.mark.asyncio
async def test_get_payment_customer(individual_workspace, test_db):
    """Test retrieving payment customer data."""
    org_id = individual_workspace["org_id"]
    
    # Create customer first
    await sync_payments_customer(db=test_db, org_id=org_id)
    
    # Get customer
    customer = await get_payment_customer(test_db, org_id)
    
    assert customer is not None
    assert customer["org_id"] == org_id
    assert customer["granted_credits"] == CREDIT_CONFIG["granted_credits"]


@pytest.mark.asyncio
async def test_payment_limits_with_granted_credits(individual_workspace, test_db):
    """Test payment limit checking with granted credits."""
    org_id = individual_workspace["org_id"]
    
    # Create customer first
    await sync_payments_customer(db=test_db, org_id=org_id)
    
    # Test with small SPU request (should be allowed)
    can_use_10_spus = await check_payment_limits(org_id, 10)
    assert can_use_10_spus is True
    
    # Test with exact granted credits amount
    granted_credits = CREDIT_CONFIG["granted_credits"]
    can_use_all_granted = await check_payment_limits(org_id, granted_credits)
    assert can_use_all_granted is True
    
    # Test with more than granted credits (should raise SPUCreditException for individual plan)
    with pytest.raises(SPUCreditException) as exc_info:
        await check_payment_limits(org_id, granted_credits + 1)
    
    # Verify exception details
    exception = exc_info.value
    assert exception.org_id == org_id
    assert exception.required_spus == granted_credits + 1
    assert exception.available_spus == granted_credits


@pytest.mark.asyncio
async def test_save_usage_record(individual_workspace, test_db):
    """Test saving usage records."""
    org_id = individual_workspace["org_id"]
    
    # Save a usage record
    usage_record = await save_usage_record(
        db=test_db,
        org_id=org_id,
        spus=25,
        operation="document_processing",
        source="test"
    )
    
    # Verify record was saved
    assert usage_record["org_id"] == org_id
    assert usage_record["spus"] == 25
    assert usage_record["operation"] == "document_processing"
    assert usage_record["source"] == "test"
    assert isinstance(usage_record["timestamp"], datetime)


@pytest.mark.asyncio
async def test_individual_workspace_plan_setup(individual_workspace, test_db):
    """Test that an individual workspace is set up correctly for payments."""
    org_id = individual_workspace["org_id"]
    
    # Create payment customer
    customer = await sync_payments_customer(db=test_db, org_id=org_id)
    
    # Verify individual workspace characteristics:
    # 1. Has granted credits for getting started
    assert customer["granted_credits"] == CREDIT_CONFIG["granted_credits"]
    assert customer["granted_credits_used"] == 0
    
    # 2. No purchased credits initially
    assert customer["purchased_credits"] == 0
    assert customer["purchased_credits_used"] == 0
    
    # 3. No active subscription initially
    assert customer.get("subscription_type") is None
    assert customer["subscription_spus_used"] == 0
    
    # 4. Can use granted credits for small workloads
    can_process_documents = await check_payment_limits(org_id, 50)
    assert can_process_documents is True
    
    # 5. Cannot exceed granted credits without payment (should raise SPUCreditException)
    with pytest.raises(SPUCreditException):
        await check_payment_limits(org_id, CREDIT_CONFIG["granted_credits"] + 1)


@pytest.mark.asyncio
async def test_workspace_without_payment_customer_fails(test_db):
    """Test that payment limits fail for non-existent customer."""
    fake_org_id = str(ObjectId())
    
    with pytest.raises(ValueError, match="No customer found"):
        await check_payment_limits(fake_org_id, 10)


if __name__ == "__main__":
    # Run tests directly
    asyncio.run(pytest.main([__file__, "-v"]))