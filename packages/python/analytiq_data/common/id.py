import bson


def is_valid_object_id(s: str) -> bool:
    """Check if string is a valid 24-char hex ObjectId format."""
    return s is not None and len(s) == 24 and all(c in "0123456789abcdef" for c in s.lower())


def create_id() -> str:
    """
    Create a unique id

    Returns:
        str: The unique id
    """
    return str(bson.ObjectId())