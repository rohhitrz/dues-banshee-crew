import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ICON = REPO_ROOT / "assets" / "icon.png"
SCRIPT = REPO_ROOT / "scripts" / "make_icon.py"
SIGNATURE = b"\x89PNG\r\n\x1a\n"


class IconTest(unittest.TestCase):
    def test_png_signature(self):
        self.assertEqual(ICON.read_bytes()[:8], SIGNATURE)

    def test_ihdr_is_512_square_8bit_rgb(self):
        data = ICON.read_bytes()
        length, tag = struct.unpack(">I4s", data[8:16])
        self.assertEqual(tag, b"IHDR")
        self.assertEqual(length, 13)
        width, height, depth, colour = struct.unpack(">IIBB", data[16:26])
        self.assertEqual((width, height), (512, 512))
        self.assertEqual(depth, 8)
        self.assertEqual(colour, 2)

    def test_generator_reproduces_committed_icon(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "icon.png"
            subprocess.run(
                [sys.executable, str(SCRIPT), str(out)],
                check=True,
                cwd=tmp,
            )
            self.assertEqual(out.read_bytes(), ICON.read_bytes())


if __name__ == "__main__":
    unittest.main()
