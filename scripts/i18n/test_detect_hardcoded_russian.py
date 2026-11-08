import tempfile
import unittest
from pathlib import Path

import detect_hardcoded_russian as scanner


class SourceFileDiscoveryTests(unittest.TestCase):
    def test_scans_typescript_files_and_keeps_javascript_support(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir)
            expected_names = {
                'Legacy.jsx',
                'Legacy.js',
                'Component.tsx',
                'utilities.ts',
            }
            for name in expected_names:
                (source_dir / name).write_text("const label = 'Русский текст';\n", encoding='utf-8')

            discovered = {Path(path).name for path in scanner.iter_source_files(source_dir)}
            self.assertEqual(discovered, expected_names)
            self.assertEqual(
                scanner.scan_file(source_dir / 'Component.tsx'),
                [(1, 'Русский текст')],
            )


if __name__ == '__main__':
    unittest.main()
