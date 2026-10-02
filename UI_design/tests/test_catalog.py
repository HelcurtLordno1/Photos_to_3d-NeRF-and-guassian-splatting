import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from UI_design.backend.catalog import load_catalog, ply_vertices


class CatalogTest(unittest.TestCase):
    def test_unknown_major_is_rejected_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "artifacts/ui/catalog.json"
            path.parent.mkdir(parents=True)
            source = json.dumps({"catalog": {"schema_version": 2}, "assets": {}})
            path.write_text(source)
            with self.assertRaises(ValueError):
                load_catalog(root)
            self.assertEqual(path.read_text(), source)

    def test_ply_count_is_bounded_and_does_not_decode_body(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "splat.ply"
            path.write_bytes(
                b"ply\r\nformat binary_little_endian 1.0\r\nelement vertex 1656903\r\nend_header\r\n\x00\xff"
            )
            self.assertEqual(ply_vertices(path), 1656903)
            for header in (
                b"not-ply",
                b"ply\nelement vertex 0\nend_header\n",
                b"ply\n" + b"x" * 65536 + b"end_header",
            ):
                path.write_bytes(header)
                with self.subTest(header=header[:30]), self.assertRaises(ValueError):
                    ply_vertices(path)


if __name__ == "__main__":
    unittest.main()
