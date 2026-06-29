import boto3
import botocore
import aioboto3
import aiobotocore.session
from aiobotocore.credentials import (
    AioAssumeRoleCredentialFetcher,
    AioCredentials,
    AioDeferredRefreshableCredentials,
)
from botocore.config import Config
from botocore.credentials import AssumeRoleCredentialFetcher, DeferredRefreshableCredentials
from botocore.exceptions import ClientError
import logging
import os
import asyncio
from contextlib import asynccontextmanager

import analytiq_data as ad

logger = logging.getLogger(__name__)

# One initialized AsyncAWSClient per (env, region) per process — avoids aioboto3/aiohttp
# session churn when many flow OCR items run Textract in parallel.
# Init locks are retained for the process lifetime (few distinct env/region keys).
_async_aws_clients: dict[tuple[str, str], "AsyncAWSClient"] = {}
_async_aws_client_init_locks: dict[tuple[str, str], asyncio.Lock] = {}

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
    Get the AWS keys from ``cloud_config`` (type aws), with fallback to legacy ``aws_config``.

    Args:
        analytiq_client: The AnalytiqClient.

    Returns:
        The AWS keys.
    """
    from analytiq_data.cloud.cloud_config import get_aws_config_dict

    return await get_aws_config_dict(analytiq_client)

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
    """
    Async AWS client for S3, Textract, SES, etc.

    Two credential tracks:
    - Track A (config keys): ``aws_access_key_id`` / ``aws_secret_access_key`` from cloud
      config — static, used by Bedrock via litellm. Never rotated by assume-role refresh.
    - Track B (assumed role): ``AioDeferredRefreshableCredentials`` on a stable
      ``aioboto3.Session`` — used by ``client()`` for service API calls.
    """

    def __init__(self, analytiq_client, region_name: str = "us-east-1"):
        self.env = analytiq_client.env
        self.region_name = region_name
        self.analytiq_client = analytiq_client
        self._session_lock = asyncio.Lock()

    async def init(self):
        aws_keys = await get_aws_config(self.analytiq_client)
        # Track A: static config keys (Bedrock / litellm)
        self.aws_access_key_id = aws_keys["aws_access_key_id"]
        self.aws_secret_access_key = aws_keys["aws_secret_access_key"]

        if not self.aws_access_key_id or not self.aws_secret_access_key:
            raise Exception(f"AWS credentials not configured. Cannot create async AWS client.")

        # Track B: async assume-role session for service clients
        self.assume_role_arn = None
        self._source_credentials = None
        self._source_aio_session = None
        self.assumed_role_credentials = None
        self._aio_session = None
        self.session = None
        self.s3_bucket_name = None

        try:
            await self._setup_assumed_role_session()
            self.s3_bucket_name = await get_s3_bucket_name(self.analytiq_client)

        except Exception as e:
            logger.error(f"AWS role assumption failed: {e}")
            logger.info("Async AWS client falling back to basic AWS credentials")
            self.session = aioboto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name,
            )
            self.s3_bucket_name = await get_s3_bucket_name(self.analytiq_client)

    async def _resolve_assume_role_arn(self) -> str:
        """One-shot sync STS lookup for role ARN (off event loop)."""

        def _sync() -> str:
            session = boto3.Session(
                region_name=self.region_name,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
            )
            identity = session.client("sts").get_caller_identity()
            return get_assume_role_arn(identity["Arn"])

        return await asyncio.to_thread(_sync)

    async def _setup_assumed_role_session(self) -> None:
        """Build stable aioboto3 session with async assume-role credentials."""
        self.assume_role_arn = await self._resolve_assume_role_arn()

        self._source_credentials = AioCredentials(
            self.aws_access_key_id,
            self.aws_secret_access_key,
        )
        self._source_aio_session = aiobotocore.session.AioSession()
        region_name = self.region_name
        source_aio_session = self._source_aio_session

        def _sts_client_creator(service_name, **kwargs):
            kwargs.setdefault("region_name", region_name)
            return source_aio_session.create_client(service_name, **kwargs)

        fetcher = AioAssumeRoleCredentialFetcher(
            client_creator=_sts_client_creator,
            source_credentials=self._source_credentials,
            role_arn=self.assume_role_arn,
        )
        self.assumed_role_credentials = AioDeferredRefreshableCredentials(
            method="assume-role",
            refresh_using=fetcher.fetch_credentials,
        )

        self._aio_session = aiobotocore.session.AioSession()
        self._aio_session._credentials = self.assumed_role_credentials

        await self.assumed_role_credentials.get_frozen_credentials()

        self.session = aioboto3.Session(
            botocore_session=self._aio_session,
            region_name=self.region_name,
        )

    async def _refresh_assumed_role_credentials(self, *, force: bool = False) -> None:
        """Refresh Track B assumed-role tokens in place (aioboto3 session unchanged)."""
        credentials = self.assumed_role_credentials
        if credentials is None:
            return
        if force:
            async with credentials._refresh_lock:
                await credentials._protected_refresh(is_mandatory=True)
        else:
            await credentials.get_frozen_credentials()
        logger.debug("Refreshed async AWS assumed-role credentials")

    async def refresh_credentials(self) -> None:
        """Refresh Track B credentials before opening AWS service clients."""
        if self.assumed_role_credentials is None:
            return
        async with self._session_lock:
            await self._refresh_assumed_role_credentials()

    _REFRESHABLE_AUTH_ERROR_CODES = frozenset({
        "ExpiredToken",
        "ExpiredTokenException",
        "InvalidToken",
        "TokenRefreshRequired",
        "InvalidSignatureException",
        "RequestExpired",
    })

    @classmethod
    def is_refreshable_auth_error(cls, exc: BaseException) -> bool:
        """True when refreshing assumed-role credentials and retrying may succeed."""
        if isinstance(exc, ClientError):
            code = exc.response.get("Error", {}).get("Code", "")
            if code in cls._REFRESHABLE_AUTH_ERROR_CODES:
                return True
        msg = str(exc)
        return any(
            marker in msg
            for marker in (
                "ExpiredToken",
                "InvalidSignatureException",
                "Signature expired",
                "security token included in the request is expired",
                "TokenRefreshRequired",
            )
        )

    async def _open_client(self, session, service_name: str, config: Config):
        """Open a service client; refresh credentials once if ``__aenter__`` fails on auth."""
        cm = session.client(service_name, config=config)
        try:
            client = await cm.__aenter__()
            return cm, client
        except Exception as e:
            if self.assumed_role_credentials and self.is_refreshable_auth_error(e):
                logger.warning(
                    "AWS credentials expired during client open, refreshing and retrying"
                )
                async with self._session_lock:
                    await self._refresh_assumed_role_credentials(force=True)
                    session = self.session
                cm = session.client(service_name, config=config)
                client = await cm.__aenter__()
                return cm, client
            raise

    @asynccontextmanager
    async def client(self, service_name: str):
        """Create an async client (single yield; signature retry only on client open)."""
        config = Config(
            connect_timeout=10,
            read_timeout=120,
            retries={"max_attempts": 2},
        )

        async with self._session_lock:
            session = self.session
        cm, aws_client = await self._open_client(session, service_name, config)
        try:
            yield aws_client
        except BaseException as e:
            await cm.__aexit__(type(e), e, e.__traceback__)
            raise
        else:
            await cm.__aexit__(None, None, None)

async def get_aws_client_async(analytiq_client, region_name: str = "us-east-1") -> AsyncAWSClient:
    """
    Get a shared AsyncAWSClient for this process (keyed by env and region).

    Args:
        analytiq_client: The AnalytiqClient.
        region_name: AWS region name.

    Returns:
        The AsyncAWSClient.
    """
    key = (analytiq_client.env, region_name)
    cached = _async_aws_clients.get(key)
    if cached is not None:
        return cached

    if key not in _async_aws_client_init_locks:
        _async_aws_client_init_locks[key] = asyncio.Lock()

    async with _async_aws_client_init_locks[key]:
        cached = _async_aws_clients.get(key)
        if cached is not None:
            return cached
        aws_client = AsyncAWSClient(analytiq_client, region_name)
        await aws_client.init()
        _async_aws_clients[key] = aws_client
        return aws_client
