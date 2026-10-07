import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from services import storage
from scripts.copy_shared_files import copy_files


class StorageTests(unittest.TestCase):
    def test_legacy_paths_use_shared_copy_even_when_missing(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(storage,'get_setting',return_value=folder):
            expected=Path(folder)/'data/reference_documents/a.pdf'
            for old in ['data/reference_documents/a.pdf',r'C:\Users\otro\Proyecto\data\reference_documents\a.pdf']:
                self.assertEqual(storage.resolve_document_path(old),expected)
            self.assertEqual(storage.resolve_document_path(r'D:\viejo\output\pdf\b.pdf'),Path(folder)/'output/pdf/b.pdf')

    def test_defaults_and_unsafe_paths(self):
        with patch.object(storage,'get_setting',return_value=''):
            self.assertEqual(storage.storage_path('data'),storage.PROJECT_ROOT/'data')
            for bad in ['data/../.env','.env',r'C:\data\x']:
                with self.assertRaises(ValueError): storage.storage_path(bad)
        with patch.object(storage,'get_setting',return_value='relative'):
            with self.assertRaises(ValueError): storage.files_root()

    def test_copy_is_verified_repeatable_and_preserves_conflicts(self):
        with tempfile.TemporaryDirectory() as base:
            src=Path(base)/'repo'; dest=Path(base)/'shared'
            (src/'data').mkdir(parents=True)
            (src/'data/map.geojson').write_text('original')
            (src/'data/local.db').write_bytes(b'private')
            (src/'.env').write_text('secret')
            self.assertEqual(len(copy_files(src,dest)),1)
            self.assertFalse(dest.exists())
            copy_files(src,dest,True)
            copy_files(src,dest,True)
            self.assertFalse((dest/'data/local.db').exists())
            self.assertFalse((dest/'.env').exists())
            (dest/'data/map.geojson').write_text('newer')
            with self.assertRaises(ValueError): copy_files(src,dest,True)
            self.assertEqual((dest/'data/map.geojson').read_text(),'newer')
            self.assertEqual((src/'data/map.geojson').read_text(),'original')

if __name__=='__main__': unittest.main()
