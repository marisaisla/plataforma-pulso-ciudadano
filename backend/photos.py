"""Descarga acotada de Telegram sin exponer el token en errores."""
import io
import re
import warnings
import httpx
from PIL import Image, UnidentifiedImageError
from backend.config import setting

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 25_000_000


def download_photo(file_id):
    token = setting('TELEGRAM_BOT_TOKEN')
    if not token:
        raise RuntimeError('Token Telegram no configurado.')
    try:
        with httpx.Client(timeout=25, follow_redirects=False, trust_env=False) as client:
            response = client.post(f'https://api.telegram.org/bot{token}/getFile', json={'file_id':file_id})
            if response.status_code>=500 or response.status_code in (401,429):
                raise RuntimeError('Telegram no disponible.')
            if not response.is_success:
                raise ValueError('Archivo no disponible.')
            info = response.json()
            if not info.get('ok'):
                raise ValueError('Archivo no disponible.')
            info=info['result']
            path=info.get('file_path','')
            if not re.fullmatch(r'[A-Za-z0-9_/-]+\.[A-Za-z0-9]+',path) or '..' in path or path.startswith('/') or info.get('file_size',0)>MAX_BYTES:
                raise ValueError('Archivo inválido o demasiado grande.')
            content=bytearray()
            with client.stream('GET',f'https://api.telegram.org/file/bot{token}/{path}') as response:
                if not response.is_success:
                    raise RuntimeError('Descarga Telegram no disponible.')
                for chunk in response.iter_bytes(65536):
                    content.extend(chunk)
                    if len(content)>MAX_BYTES:
                        raise ValueError('Fotografía demasiado grande.')
            return bytes(content)
    except httpx.HTTPError:
        raise RuntimeError('No se pudo descargar la fotografía; se reintentará.') from None
    except (KeyError, TypeError):
        raise ValueError('Archivo inválido.') from None


def validate_photo(raw):
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:
        raise ValueError('Tamaño inválido.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format!='JPEG' or image.width*image.height>MAX_PIXELS:
                    raise ValueError('Imagen inválida.')
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
    except (OSError,UnidentifiedImageError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise ValueError('JPEG inválido.') from None
