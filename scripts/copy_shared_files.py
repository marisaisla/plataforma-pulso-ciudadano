"""Copy managed files to a share with SHA256 verification; never delete/overwrite.
Run from project root: python scripts/copy_shared_files.py --destination UNC [--apply]
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ('data', 'output', 'assets/go2win_video')


def digest(p):
    with p.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(root):
    for folder in FOLDERS:
        for p in sorted((root / folder).rglob('*')):
            if p.is_symlink() or p.is_junction():
                raise ValueError(f'No se copian enlaces: {p}')
            if not p.is_file():
                continue
            rel = p.relative_to(root)
            if 'backups' in rel.parts or p.suffix.lower() in {'.db', '.dump', '.log'} or p.name.endswith(('.db-wal', '.db-shm')):
                continue
            yield rel, p


def copy_files(source, destination, apply=False):
    source, destination = source.resolve(), destination.resolve()
    if destination == source or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('El destino debe estar fuera del repositorio y no contenerlo.')
    rows=[]
    for rel,p in inventory(source):
        target=destination/rel
        if not target.resolve().is_relative_to(destination):
            raise ValueError(f'Destino fuera de la carpeta compartida: {rel}')
        sha=digest(p)
        if target.exists() and (not target.is_file() or digest(target)!=sha):
            raise ValueError(f'Conflicto: {rel}. No se sobrescribirá. Revisar versiones.')
        rows.append({'path':rel.as_posix(),'bytes':p.stat().st_size,'sha256':sha})
    if not apply:
        return rows
    destination.mkdir(parents=True,exist_ok=True)
    for row in rows:
        p=source/row['path']; target=destination/row['path']
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            # Exclusive creation protects an existing file even if another writer appears.
            with target.open('xb') as dst, p.open('rb') as src:
                shutil.copyfileobj(src,dst)
        if digest(target)!=row['sha256']:
            raise ValueError(f'Verificación fallida: {row["path"]}. No activar la carpeta.')
    manifests=destination/'_migration'
    manifests.mkdir(exist_ok=True)
    name=datetime.now().strftime('manifest-%Y%m%d-%H%M%S-%f.json')
    (manifests/name).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    dest=Path(args.destination)
    if not dest.is_absolute():
        parser.error('El destino debe ser absoluto (local o UNC).')
    rows=copy_files(ROOT,dest,args.apply)
    print(json.dumps({'mode':'copied_and_verified' if args.apply else 'preview', 'files':len(rows),'bytes':sum(r['bytes'] for r in rows)},indent=2))
