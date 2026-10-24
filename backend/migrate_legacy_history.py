"""Auditar o copiar las cargas anteriores sin modificar public.

python -m backend.migrate_legacy_history             # solo análisis
python -m backend.migrate_legacy_history --apply --actor-id ID_ADMIN
"""
import argparse
import gzip
import json
import uuid
from datetime import datetime, timezone

from backend.database import connect
from backend.legacy_history import (analyze, canonical, digest, protected_checksums,
                                    read_sources, write_migration)
from services.storage import storage_path


def verified_snapshot(content, snapshot_hash):
    # Insumo compartido: no usar .build ni una copia local si MARISA no responde.
    from services.settings import get_setting
    if not get_setting('GO2WIN_FILES_ROOT').strip():
        raise RuntimeError('Falta GO2WIN_FILES_ROOT; no se crea un respaldo local como alternativa.')
    path = storage_path('data/history_migration') / ('legacy_'+snapshot_hash+'.json.gz')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if digest(gzip.decompress(path.read_bytes()).decode('utf-8')) != snapshot_hash:
            raise RuntimeError('El respaldo existente no concilia; no se sobrescribe.')
        return path
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temporary.open('xb') as handle:
        handle.write(gzip.compress(content.encode('utf-8'), mtime=0))
    if digest(gzip.decompress(temporary.read_bytes()).decode('utf-8')) != snapshot_hash:
        raise RuntimeError('La copia de respaldo no concilia; no se migra.')
    temporary.rename(path)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--actor-id', type=int)
    args = parser.parse_args()
    from services.settings import get_setting
    if get_setting('DB_BACKEND').strip().lower() != 'postgresql':
        raise RuntimeError('Los visores no están configurados con PostgreSQL; revisar el origen antes de migrar.')
    if args.apply and not args.actor_id:
        parser.error('--apply requiere --actor-id de un administrador activo')
    if args.apply:
        from backend.migrate_history import migrate
        migrate()
    with connect() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        if not args.apply:
            conn.execute('SET TRANSACTION READ ONLY')
        else:
            actor = conn.execute("SELECT id FROM public.field_workers WHERE id=%s AND active=1 AND role_key='administrator'", (args.actor_id,)).fetchone()
            if not actor:
                raise RuntimeError('El actor no es un administrador activo.')
        sources = read_sources(conn)
        print('Origen leído:',sum(len(rows) for rows in sources.values()),'registros.',flush=True)
        snapshot_hash = digest(canonical(sources))
        before = protected_checksums(conn)
        if args.apply:
            path = verified_snapshot(canonical(sources), snapshot_hash)
            print('Respaldo compartido verificado:',path,flush=True)
            report = write_migration(conn, sources, args.actor_id, path, before)
        else:
            _,report = analyze(sources)
            report.update(snapshot_sha256=snapshot_hash, protected_before=before, mode='read_only_preview')
    # El informe final solo se publica después del COMMIT exitoso.
    if args.apply:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        path = storage_path('output/history_migration') / f'reconciliation_run_{report["run_id"]}_{stamp}_{uuid.uuid4().hex[:8]}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(report,ensure_ascii=False,indent=2,default=str)
        with path.open('x',encoding='utf-8') as handle:
            handle.write(content)
        if digest(path.read_text(encoding='utf-8')) != digest(content):
            raise RuntimeError('Migración confirmada en BD, pero el informe compartido no concilia; consultar legacy_runs.report.')
        print('INFORME:',path)
    print(json.dumps({k:v for k,v in report.items() if k not in ('groups','protected_before','protected_after')},ensure_ascii=False,indent=2,default=str))


if __name__ == '__main__':
    main()
