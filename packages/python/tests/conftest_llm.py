import json
import os
import asyncio
import threading
import time
from unittest.mock import patch, AsyncMock
from bson import ObjectId
from worker.worker import main as worker_main
import analytiq_data as ad
import logging

logger = logging.getLogger(__name__)


class MockLLMResponse:
    """Mock LLM response object that mimics litellm response structure"""
    def __init__(self, content="Test response from mocked LLM", finish_reason="stop"):
        self.id = "chatcmpl-test123"
        self.object = "chat.completion"
        self.model = "gpt-4o-mini"  # Add model attribute that LiteLLM expects
        self.created = 1700000000
        self.choices = [MockChoice(content, finish_reason)]
        self.usage = MockUsage()
        self.system_fingerprint = None

    def __getitem__(self, key):
        """Allow dict-like access for LiteLLM compatibility"""
        return getattr(self, key, None)

    def get(self, key, default=None):
        """Allow dict-like access for LiteLLM compatibility"""
        return getattr(self, key, default)


class MockChoice:
    """Mock choice object"""
    def __init__(self, content, finish_reason="stop"):
        self.message = MockMessage(content)
        self.finish_reason = finish_reason


class MockMessage:
    """Mock message object"""
    def __init__(self, content):
        self.role = "assistant"
        self.content = content


class MockUsage:
    """Mock usage object"""
    def __init__(self):
        self.prompt_tokens = 10
        self.completion_tokens = 20
        self.total_tokens = 30


def _mock_textract_geometry(left: float, top: float, width: float = 0.9, height: float = 0.06):
    """Normalized Geometry like Textract API (BoundingBox + Polygon)."""
    return {
        "BoundingBox": {
            "Width": width,
            "Height": height,
            "Left": left,
            "Top": top,
        },
        "Polygon": [
            {"X": left, "Y": top},
            {"X": left + width, "Y": top},
            {"X": left + width, "Y": top + height},
            {"X": left, "Y": top + height},
        ],
    }


def mock_textract_blocks_invoice_sample():
    """
    Minimal valid Textract ``Blocks`` list: PAGE with CHILD lines, each LINE with WORD children
    and Geometry. Required for amazon-textract-textractor / :func:`Document.open`.
    """
    lines_spec = [
        ("mock-line-1", "mock-word-1", "INVOICE #12345", 0.10),
        ("mock-line-2", "mock-word-2", "Total: $1,234.56", 0.18),
        ("mock-line-3", "mock-word-3", "Vendor: Acme Corp", 0.26),
    ]
    line_ids = [s[0] for s in lines_spec]
    blocks = [
        {
            "BlockType": "PAGE",
            "Id": "mock-page-1",
            "Page": 1,
            "Geometry": _mock_textract_geometry(0.0, 0.0, width=1.0, height=1.0),
            "Relationships": [{"Type": "CHILD", "Ids": line_ids}],
        },
    ]
    for line_id, word_id, text, top in lines_spec:
        geo = _mock_textract_geometry(0.05, top)
        blocks.append(
            {
                "BlockType": "LINE",
                "Id": line_id,
                "Page": 1,
                "Text": text,
                "Confidence": 98.0,
                "Geometry": geo,
                "Relationships": [{"Type": "CHILD", "Ids": [word_id]}],
            }
        )
        blocks.append(
            {
                "BlockType": "WORD",
                "Id": word_id,
                "Page": 1,
                "Text": text,
                "TextType": "PRINTED",
                "Confidence": 98.0,
                "Geometry": geo,
            }
        )
    return blocks


class MockTextractResponse:
    """Mock response for Textract run_textract function"""
    def __init__(self, blocks=None):
        self.blocks = blocks or mock_textract_blocks_invoice_sample()


async def mock_run_textract(analytiq_client, blob, feature_types=[], query_list=None, document_id=None, **kwargs):
    """Mock implementation of ad.aws.textract.run_textract that matches the real function signature"""
    blocks = mock_textract_blocks_invoice_sample()
    return {
        "Blocks": blocks,
        "DocumentMetadata": {"Pages": 1},
        "AnalyzeDocumentModelVersion": None,
        "DetectDocumentTextModelVersion": "mock-detect-v1",
    }


class MockLiteLLMFileResponse:
    """Mock response for litellm file creation"""
    def __init__(self, file_id="file-test123"):
        self.id = file_id
        self.object = "file"
        self.purpose = "assistants"
        self.filename = "test_file.txt"
        self.bytes = 1024
        self.created_at = 1700000000


async def mock_litellm_acreate_file_with_retry(file, purpose, custom_llm_provider, api_key):
    """Mock implementation of _litellm_acreate_file_with_retry"""
    return MockLiteLLMFileResponse()


async def mock_litellm_acompletion_with_retry(analytiq_client, model, messages, api_key, temperature=0.1, response_format=None, **kwargs):
    """Mock implementation of _litellm_acompletion_with_retry that returns valid JSON."""
    # Always return a JSON object that looks like structured extraction
    mocked_json = {
        "invoice_number": "12345",
        "total_amount": 1234.56,
        "vendor": {"name": "Acme Corp"}
    }
    return MockLLMResponse(content=json.dumps(mocked_json))


class WorkerAppliance:
    """Test appliance for spawning worker processes with mocked functions"""

    def __init__(self, n_workers=1, supports_response_schema=True, supports_pdf_input=True, mock_llm_response=None):
        self.n_workers = n_workers
        self.supports_response_schema = supports_response_schema
        self.supports_pdf_input = supports_pdf_input
        # Create default mock LLM response if none provided
        if mock_llm_response is None:
            default_response = MockLLMResponse()
            default_response.choices[0].message.content = json.dumps({
                "invoice_number": "12345",
                "total_amount": 1234.56,
                "vendor": {
                    "name": "Acme Corp"
                }
            })
            self.mock_llm_response = default_response
        else:
            self.mock_llm_response = mock_llm_response
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.patches = []
        self.started_mocks = []

    def start(self):
        """Start the worker appliance with all necessary patches"""
        # Apply all patches before starting the worker thread
        self.patches = [
            patch('analytiq_data.aws.textract.run_textract', new=mock_run_textract),
            patch('analytiq_data.llm.llm._litellm_acompletion_with_retry', new_callable=AsyncMock),
            patch('analytiq_data.llm.llm._litellm_acreate_file_with_retry', new=mock_litellm_acreate_file_with_retry),
            patch('litellm.completion_cost', return_value=0.001),
            patch('litellm.supports_response_schema', return_value=self.supports_response_schema),
            patch('litellm.utils.supports_pdf_input', return_value=self.supports_pdf_input)
        ]

        # Start all patches
        self.started_mocks = []
        for p in self.patches:
            started = p.start()
            self.started_mocks.append(started)

        # Configure the LLM completion mock
        if len(self.started_mocks) >= 2:
            mock_llm_completion = self.started_mocks[1]
            mock_llm_completion.return_value = self.mock_llm_response

        # Set environment variable for worker count
        self.original_n_workers = os.environ.get('N_WORKERS')
        self.original_env = os.environ.get('ENV')
        os.environ['N_WORKERS'] = str(self.n_workers)

        logger.info(f"WorkerAppliance ENV: {os.environ['ENV']}")

        # Import and start the worker in a separate thread
        def run_worker():
            logger.info(f"WorkerAppliance ENV: {os.environ['ENV']}")

            # Create new event loop for the thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Run until stop event is set
                async def run_until_stop():
                    main_task = asyncio.create_task(worker_main())
                    while not self.stop_event.is_set():
                        await asyncio.sleep(0.1)
                    main_task.cancel()
                    try:
                        await main_task
                    except asyncio.CancelledError:
                        pass

                loop.run_until_complete(run_until_stop())
            finally:
                loop.close()

        self.worker_thread = threading.Thread(target=run_worker, daemon=True)
        self.worker_thread.start()

        # Give workers time to start
        time.sleep(1)

    def stop(self):
        """Stop the worker appliance and clean up patches"""
        if self.worker_thread:
            self.stop_event.set()
            self.worker_thread.join(timeout=5)

        # Stop all patches
        for p in self.patches:
            try:
                p.stop()
            except:
                pass
        self.patches.clear()

        # Restore original environment variables
        if self.original_n_workers is not None:
            os.environ['N_WORKERS'] = self.original_n_workers
        elif 'N_WORKERS' in os.environ:
            del os.environ['N_WORKERS']

        if self.original_env is not None:
            os.environ['ENV'] = self.original_env
        elif 'ENV' in os.environ:
            del os.environ['ENV']

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()