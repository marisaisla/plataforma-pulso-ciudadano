"""Actualizar el contrato: python -m backend.export_openapi."""
import json
from pathlib import Path
from backend.main import app


if __name__=='__main__':
    target=Path(__file__).with_name('openapi.json')
    target.write_text(json.dumps(app.openapi(),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Contrato OpenAPI actualizado: '+app.version)
