# main.py

# Standard library imports
import os
import sys
import logging
import warnings
from contextlib import asynccontextmanager
# Defer litellm import to avoid event loop warnings
# import litellm

# Suppress Pydantic deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pydantic")

# Set up the path first, before other imports
cwd = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{cwd}/..")

# Third-party imports
from fastapi import FastAPI
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

# Local imports
from docrouter_app import startup
from docrouter_app.routes.payments import payments_router, init_payments
from docrouter_app.routes.documents import documents_router
from docrouter_app.routes.ocr import ocr_router
from docrouter_app.routes.llm import llm_router
from docrouter_app.routes.prompts import prompts_router
from docrouter_app.routes.schemas import schemas_router
from docrouter_app.routes.tags import tags_router
from docrouter_app.routes.forms import forms_router
from docrouter_app.routes.aws import aws_router
from docrouter_app.routes.token import token_router
from docrouter_app.routes.oauth import oauth_router
from docrouter_app.routes.orgs import orgs_router
from docrouter_app.routes.users import users_router
from docrouter_app.routes.emails import emails_router
import analytiq_data as ad

# Set up the environment variables. This reads the .env file.
ad.common.setup()

# Environment variables
ENV = os.getenv("ENV", "dev")
NEXTAUTH_URL = os.getenv("NEXTAUTH_URL")
FASTAPI_ROOT_PATH = os.getenv("FASTAPI_ROOT_PATH", "/")
MONGODB_URI = os.getenv("MONGODB_URI")
SES_FROM_EMAIL = os.getenv("SES_FROM_EMAIL")

logger = logging.getLogger(__name__)

logger.info(f"ENV: {ENV}")
logger.info(f"NEXTAUTH_URL: {NEXTAUTH_URL}")
logger.info(f"FASTAPI_ROOT_PATH: {FASTAPI_ROOT_PATH}")
logger.info(f"MONGODB_URI: {MONGODB_URI}")
logger.info(f"SES_FROM_EMAIL: {SES_FROM_EMAIL}")
# JWT settings
NEXTAUTH_SECRET = os.getenv("NEXTAUTH_SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Define MongoDB connection check function to be used in lifespan
async def check_mongodb_connection(uri):
    try:
        # Create a MongoDB client
        mongo_client = AsyncIOMotorClient(uri)
        
        # The ismaster command is cheap and does not require auth
        await mongo_client.admin.command('ismaster')
        logger.info(f"MongoDB connection successful at {uri}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB at {uri}: {e}")
        return False

UPLOAD_DIR = "data"


@asynccontextmanager
async def lifespan(app):
    # Startup code (previously in @app.on_event("startup"))
    
    # Check MongoDB connectivity first
    await check_mongodb_connection(MONGODB_URI)
    
    analytiq_client = ad.common.get_analytiq_client()
    await startup.setup_admin(analytiq_client)
    await startup.setup_api_creds(analytiq_client)
    
    # Initialize payments
    db = ad.common.get_async_db(analytiq_client)
    await init_payments(db)
    
    yield  # This is where the app runs
    
    # Shutdown code (if any) would go here
    # For example: await some_client.close()

# Create the FastAPI app with the lifespan
app = FastAPI(
    root_path=FASTAPI_ROOT_PATH,
    lifespan=lifespan
)
security = HTTPBearer()

# CORS allowed origins
CORS_ORIGINS_DEF = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://host.docker.internal:3000",
]

# Only add NEXTAUTH_URL if it's not None
if NEXTAUTH_URL:
    CORS_ORIGINS_DEF.append(NEXTAUTH_URL)

cors_origins = os.getenv("CORS_ORIGINS", ",".join(CORS_ORIGINS_DEF)).split(",")
logger.info(f"CORS allowed origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"] # Needed to expose the Content-Disposition header to the frontend
)

app.include_router(payments_router)
app.include_router(documents_router)
app.include_router(ocr_router)
app.include_router(llm_router)
app.include_router(prompts_router)
app.include_router(schemas_router)
app.include_router(tags_router)
app.include_router(forms_router)
app.include_router(token_router)
app.include_router(aws_router)
app.include_router(oauth_router)
app.include_router(orgs_router)
app.include_router(users_router)
app.include_router(emails_router)
