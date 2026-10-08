"""Stop tracking managed files, keeping and verifying every local byte."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)

def digest(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    paths=[p.decode('utf-8') for p in git('ls-files','-z','--','data','output','assets/go2win_video').split(b'\0') if p]
    if not paths:
        print('Los directorios ya estan fuera del indice.');return
    # Refuse if a source has disappeared or has staged modifications.
    if git('diff','--cached','--name-only','--','data','output','assets/go2win_video').strip():
        raise SystemExit('Hay cambios preparados en estas carpetas. Revisarlos antes de continuar.')
    hashes={p:digest(ROOT/p) for p in paths}
    receipt=ROOT/'.build/storage-separation'
    receipt.mkdir(parents=True,exist_ok=True)
    (receipt/'local-files.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
    git('rm','-r','--cached','--','data','output','assets/go2win_video')
    for p,sha in hashes.items():
        if digest(ROOT/p)!=sha: raise RuntimeError(f'Archivo local alterado: {p}')
    print(f'{len(paths)} archivos retirados SOLO del indice de Git. Copias locales verificadas con SHA256.')

if __name__=='__main__': main()
