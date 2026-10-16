import os

DEFAULT_APP_NAME = "Smart Document Router"


def app_name() -> str:
    value = (os.getenv("APP_NAME") or DEFAULT_APP_NAME).strip()
    return value or DEFAULT_APP_NAME
