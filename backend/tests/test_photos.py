import io
import unittest
from PIL import Image
from backend.photos import validate_photo, MAX_BYTES


class PhotoTests(unittest.TestCase):
    def test_png_empty_and_oversized_rejected(self):
        buffer=io.BytesIO()
        Image.new('RGB',(10,10)).save(buffer,format='PNG')
        for raw in (b'',buffer.getvalue(),b'x'*(MAX_BYTES+1)):
            with self.assertRaises(ValueError): validate_photo(raw)

    def test_truncated_jpeg_rejected(self):
        buffer=io.BytesIO()
        Image.new('RGB',(10,10)).save(buffer,format='JPEG')
        with self.assertRaises(ValueError): validate_photo(buffer.getvalue()[:100])
