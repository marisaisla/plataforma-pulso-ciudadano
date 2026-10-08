"""Check routing in fresh processes without rendering historical videos."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULES = [
    'build_go2win_pdf_video', 'build_movilizacion_explainer',
    'build_go2win_presentacion_video', 'build_go2win_visual_video',
    'build_go2win_recorrido_video', 'build_go2win_dashboard_video',
    'build_go2win_dashboard_v3', 'build_go2win_dashboard_v4',
    'build_go2win_dashboard_v5', 'build_go2win_dashboard_v6',
]


class MediaStorageTests(unittest.TestCase):
    def test_generators_use_configured_root_from_another_working_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            shared = Path(folder) / 'shared'
            shared.mkdir()
            env = dict(os.environ, GO2WIN_FILES_ROOT=str(shared),
                       PYTHONPATH=str(ROOT / 'scripts') + os.pathsep + str(ROOT))
            code = '''
import importlib, os, sys
from pathlib import Path
m = importlib.import_module(sys.argv[1])
root = Path(os.environ['GO2WIN_FILES_ROOT'])
seen = set()
def check(module):
    if id(module) in seen: return
    seen.add(id(module))
    for name, value in vars(module).items():
        if isinstance(value, Path) and not name.startswith('_'):
            assert value.is_relative_to(root), (name, str(value))
        if name in ('VIDEOS', 'PPT_SCENES'):
            assert all(p.is_relative_to(root) for p in value.values())
        if name in ('base', 'video', 'visual', 'previous'): check(value)
check(m)
'''
            for module in MODULES:
                with self.subTest(module=module):
                    result = subprocess.run([sys.executable, '-c', code, module],
                                            cwd=folder, env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(os.name == 'nt', 'Windows PowerShell paths')
    def test_powershell_root_precedence_and_unavailable_share(self):
        with tempfile.TemporaryDirectory() as folder:
            helper = str(ROOT / 'scripts/shared_files.ps1').replace("'", "''")
            command = ". '" + helper + "'; $ErrorActionPreference='Stop'; Get-Go2WinFilesRoot"
            env = dict(os.environ, GO2WIN_FILES_ROOT=folder)
            result = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command],
                                    cwd=folder, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), folder)
            env['GO2WIN_FILES_ROOT'] = str(Path(folder) / 'unavailable')
            result = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command],
                                    cwd=folder, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(Path(env['GO2WIN_FILES_ROOT']).exists())


if __name__ == '__main__':
    unittest.main()
