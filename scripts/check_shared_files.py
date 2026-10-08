"""Read-only check of the share and DB document links before activation."""
import argparse
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True)
    parser.add_argument('--database',action='store_true')
    args=parser.parse_args()
    os.environ['GO2WIN_FILES_ROOT']=args.root
    from services.storage import files_root, resolve_document_path
    root=files_root()
    if not root.is_dir():
        raise SystemExit('Carpeta no accesible. No activar GO2WIN_FILES_ROOT todavía.')
    missing=[]
    from services.gis import LOCAL_STATE_DATASETS, LOCAL_DISTRICT_DATASETS, LOCAL_SECTION_DATASETS
    for p in set([*LOCAL_STATE_DATASETS.values(),*LOCAL_DISTRICT_DATASETS.values(),*LOCAL_SECTION_DATASETS.values()]):
        if not p.is_file(): missing.append(str(p))
    if args.database:
        from services.database import query
        for row in query('SELECT id, file_path FROM reference_documents'):
            p=resolve_document_path(row['file_path'])
            if not p.is_file() or not p.resolve().is_relative_to(root.resolve()):
                missing.append(f'Documento {row["id"]}: {p}')
    if missing:
        print('Pendientes antes de activar:')
        print('\n'.join(missing))
        raise SystemExit(1)
    print('Cartografia verificada.' + (' Documentos de BD verificados.' if args.database else ' Falta verificar documentos con --database.'))

if __name__=='__main__': main()
