import os
from dotenv import load_dotenv
import logging

def _configure_stamina_logging() -> None:
    """
    Register a stamina retry hook that logs *what* is being retried.

    Stamina's built-in logging hook records the callable name and the causing
    exception only in the logging ``extra`` dict, so with our plain
    ``%(message)s`` format those details are dropped and the log line is just
    ``stamina.retry_scheduled``. This hook folds them into the message instead.
    """
    import stamina
    from stamina.instrumentation import RetryDetails, set_on_retry_hooks

    stamina_logger = logging.getLogger("stamina")

    def log_retry(details: RetryDetails) -> None:
        stamina_logger.info(
            f"stamina retry #{details.retry_num} for {details.name}: "
            f"caused_by={details.caused_by!r}; "
            f"waiting {round(details.wait_for, 2)}s "
            f"(waited {round(details.waited_so_far, 2)}s so far)"
        )

    set_on_retry_hooks([log_retry])


def setup() -> None:
    """
    Setup the environment variables
    """
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Check if we're in testing mode (pytest or pytest_ts environment)
    env = os.getenv("ENV", "")
    is_testing = env.startswith("pytest")

    # Only load .env file if not in testing mode
    # In testing mode, all environment variables should be set by the test framework
    if not is_testing:
        dotenv_path = os.path.join(current_dir, "../../../.env")
        load_dotenv(dotenv_path=dotenv_path, override=False)

    # Configure logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    _configure_stamina_logging()
