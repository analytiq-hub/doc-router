import boto3
import botocore
import aioboto3
from botocore.config import Config
from botocore.credentials import AssumeRoleCredentialFetcher, DeferredRefreshableCredentials
import logging
import os
import asyncio
from contextlib import asynccontextmanager

import analytiq_data as ad

logger = logging.getLogger(__name__)

async def get_s3_bucket_name(analytiq_client) -> str:
    """
    Get the S3 bucket name from database configuration or environment variable with fallback to default.
    
    Args:
        analytiq_client: Optional AnalytiqClient to check database configuration
        
    Returns:
        The S3 bucket name to use for AWS operations.
    """
    try:
        aws_config = await get_aws_config(analytiq_client)
        if aws_config.get("s3_bucket_name"):
            return aws_config["s3_bucket_name"]
    except Exception as e:
        logger.warning(f"Could not get S3 bucket name from database: {e}")

class SyncAWSClient:
    def __init__(self, analytiq_client, region_name: str = "us-east-1"):
        self.env = analytiq_client.env
        self.region_name = region_name
        self.analytiq_client = analytiq_client

    async def init(self):
        # Get the AWS keys
        aws_keys = await get_aws_config(self.analytiq_client)
        self.aws_access_key_id = aws_keys["aws_access_key_id"]
        self.aws_secret_access_key = aws_keys["aws_secret_access_key"]

        # Create the session
        self.user_session = boto3.Session(
            region_name=self.region_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key
        )

        # It's possible that the AWS keys are not set, in which case
        # assuming the role will fail.
        # Initialize the AWS clients with neutral values, and set them only if the
        # credentials are valid.
        self.session = self.user_session
        self.s3 = None
        self.textract = None
        self.ses = None

        try:
            # Get the user's identity
            user_identity = self.user_session.client("sts").get_caller_identity()

            # Get the assume role ARN
            assume_role_arn = get_assume_role_arn(user_identity["Arn"])

            fetcher = AssumeRoleCredentialFetcher(
                client_creator=self.user_session.client,
                source_credentials=self.user_session.get_credentials(),
                role_arn=assume_role_arn,
            ) 
            botocore_session = botocore.session.Session()
            botocore_session._credentials = DeferredRefreshableCredentials(
                method='assume-role',
                refresh_using=fetcher.fetch_credentials
            )

            # Create the assumed role session
            self.session = boto3.Session(botocore_session=botocore_session)

            # Create the s3 client
            self.s3 = self.session.client("s3", region_name=self.region_name)
            self.s3_bucket_name = await get_s3_bucket_name(self.analytiq_client)

            # Create the textract client
            self.textract = self.session.client("textract", region_name=self.region_name)

        except Exception as e:
            logger.info(f"AWS credentials are not correct: {e}")
            logger.info("AWS client created with empty AWS credentials")

async def get_aws_client_sync(analytiq_client, region_name: str = "us-east-1") -> SyncAWSClient:
    """
    Get the SyncAWSClient.

    Args:
        analytiq_client: The AnalytiqClient.

    Returns:
        The SyncAWSClient.
    """
    aws_client = SyncAWSClient(analytiq_client, region_name)
    await aws_client.init()
    return aws_client

async def get_aws_config(analytiq_client) -> dict:
    """
    Get the AWS keys.

    Args:
        analytiq_client: The AnalytiqClient.

    Returns:
        The AWS keys.
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    aws_config_collection = db["aws_config"]

    aws_config = await aws_config_collection.find_one()
    
    # Parse the AWS keys
    access_key_id = ""
    secret_access_key = ""
    if aws_config:
        access_key_id = ad.crypto.decrypt_token(aws_config.get("access_key_id", ""))
        secret_access_key = ad.crypto.decrypt_token(aws_config.get("secret_access_key", ""))

    return {
        "aws_access_key_id": access_key_id,
        "aws_secret_access_key": secret_access_key,
        "s3_bucket_name": aws_config.get("s3_bucket_name") if aws_config else None
    }

def get_assume_role_arn(user_arn: str) -> str:
    """
    Get the assume role ARN.

    Args:
        user_arn: The user ARN.

    Returns:
        The assume role ARN.
    """
    account_id = user_arn.split(":")[4]
    user_name = user_arn.split("/")[-1]
    account_name = user_name.split("-")[0]
    user_name_base = user_name.split("-")[1]
    return f"arn:aws:iam::{account_id}:role/{account_name}-{user_name_base}-role"

class AsyncAWSClient:
    def __init__(self, analytiq_client, region_name: str = "us-east-1"):
        self.env = analytiq_client.env
        self.region_name = region_name
        self.analytiq_client = analytiq_client
        
    async def init(self):
        # Get the AWS keys
        aws_keys = await get_aws_config(self.analytiq_client)
        self.aws_access_key_id = aws_keys["aws_access_key_id"]
        self.aws_secret_access_key = aws_keys["aws_secret_access_key"]
        
        if not self.aws_access_key_id or not self.aws_secret_access_key:
            raise Exception(f"AWS credentials not configured. Cannot create async AWS client.")
        
        # Create the user session (sync for initial setup)
        self.user_session = boto3.Session(
            region_name=self.region_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key
        )

        # Store credential fetcher for refresh capability
        self.credential_fetcher = None
        self.botocore_session = None
        self.assume_role_arn = None

        # Initialize with user session credentials
        self.session = aioboto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
        self.s3_bucket_name = None

        try:
            # Get the user's identity
            user_identity = self.user_session.client("sts").get_caller_identity()

            # Get the assume role ARN
            self.assume_role_arn = get_assume_role_arn(user_identity["Arn"])

            # Create role assumption credentials using the same approach as sync client
            self.credential_fetcher = AssumeRoleCredentialFetcher(
                client_creator=self.user_session.client,
                source_credentials=self.user_session.get_credentials(),
                role_arn=self.assume_role_arn,
            )
            
            # Create a botocore session with deferred credentials like the sync client
            self.botocore_session = botocore.session.Session()
            self.botocore_session._credentials = DeferredRefreshableCredentials(
                method='assume-role',
                refresh_using=self.credential_fetcher.fetch_credentials
            )
            
            # Update session with fresh credentials
            self._refresh_session()
            
            # Get S3 bucket name
            self.s3_bucket_name = await get_s3_bucket_name(self.analytiq_client)

        except Exception as e:
            logger.error(f"AWS role assumption failed: {e}")
            logger.info("Async AWS client falling back to basic AWS credentials")
            # Fall back to basic credentials if role assumption fails
            self.s3_bucket_name = await get_s3_bucket_name(self.analytiq_client)

    def _refresh_session(self):
        """Refresh the session with current credentials"""
        if self.botocore_session and self.botocore_session._credentials:
            # Get fresh credentials
            credentials = self.botocore_session.get_credentials()
            
            # Create new async session with fresh credentials
            self.session = aioboto3.Session(
                aws_access_key_id=credentials.access_key,
                aws_secret_access_key=credentials.secret_key,
                aws_session_token=credentials.token,
                region_name=self.region_name
            )
            logger.debug("Refreshed async AWS session with new credentials")

    @asynccontextmanager
    async def client(self, service_name: str):
        """Create an async client with automatic credential refresh"""
        # Configure timeouts
        config = Config(
            connect_timeout=10,      # 10s to establish connection
            read_timeout=120,        # 2 minutes to read response (enough for API calls, not infinite)
            retries={'max_attempts': 2}
        )

        try:
            # Refresh session to ensure we have current credentials
            if self.botocore_session:
                self._refresh_session()

            async with self.session.client(service_name, config=config) as client:
                yield client
        except Exception as e:
            # If we get a signature error, try refreshing credentials once
            if "InvalidSignatureException" in str(e) or "Signature expired" in str(e):
                logger.warning(f"AWS signature expired, refreshing credentials and retrying")
                if self.botocore_session:
                    self._refresh_session()
                    async with self.session.client(service_name, config=config) as client:
                        yield client
                else:
                    raise e
            else:
                raise e

async def get_aws_client_async(analytiq_client, region_name: str = "us-east-1") -> AsyncAWSClient:
    """
    Get the AsyncAWSClient.

    Args:
        analytiq_client: The AnalytiqClient.
        region_name: AWS region name.

    Returns:
        The AsyncAWSClient.
    """
    aws_client = AsyncAWSClient(analytiq_client, region_name)
    await aws_client.init()
    return aws_client
