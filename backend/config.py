import os
from pathlib import Path

from dotenv import dotenv_values


def setting(key: str) -> str:
    values = dotenv_values(Path(__file__).resolve().parents[1] / '.env')
    return os.environ.get(key, values.get(key) or '')
