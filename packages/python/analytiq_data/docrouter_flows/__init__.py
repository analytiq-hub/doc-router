"""
DocRouter-specific flow node implementations and integration services.

Lives under `analytiq_data` (not `app`) so any process that loads `analytiq_data`
— API workers, standalone queue workers — can register these nodes without
importing the FastAPI package tree.
"""

from .register import register_docrouter_nodes
from .services import *
