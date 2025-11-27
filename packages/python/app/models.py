from pydantic import BaseModel, Field, constr, ConfigDict, field_validator, model_validator
from datetime import datetime
from typing import List, Literal, Optional, Any, Dict, Union, ForwardRef
from enum import Enum

# Pydantic models
class User(BaseModel):
    user_id: str
    user_name: str
    token_type: str

