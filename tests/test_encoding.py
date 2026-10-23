"""Home Assistant reads packaged source and service metadata as UTF-8."""
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
TEXT_SUFFIXES = {'.py', '.js', '.json', '.yaml', '.yml', '.html', '.md'}

class PackageEncodingTests(unittest.TestCase):
    def test_packaged_text_files_are_utf8(self):
        for folder in ['custom_components', 'frontend', 'tests', '.github']:
            for path in (ROOT / folder).rglob('*'):
                if path.is_file() and path.suffix in TEXT_SUFFIXES:
                    with self.subTest(path=str(path.relative_to(ROOT))):
                        path.read_bytes().decode('utf-8', errors='strict')
        for filename in ['README.md', 'CHANGELOG.md', 'hacs.json', 'package.json']:
            with self.subTest(path=filename):
                (ROOT / filename).read_bytes().decode('utf-8', errors='strict')

if __name__ == '__main__': unittest.main()
