import unittest
from pathlib import Path
from struct import unpack


class DocumentationTests(unittest.TestCase):
    def test_architecture_image_is_valid_and_linked(self):
        readme = Path("README.md").read_text(encoding="utf-8")
        image_path = Path("docs/system-architecture.png")

        self.assertIn(
            "![AI Finance Controller system architecture](docs/system-architecture.png)",
            readme,
        )
        image = image_path.read_bytes()
        self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
        width, height = unpack(">II", image[16:24])
        self.assertGreaterEqual(width, 1000)
        self.assertGreaterEqual(height, 600)

    def test_readme_uses_only_the_png_architecture_artifact(self):
        readme = Path("README.md").read_text(encoding="utf-8")

        self.assertNotIn("system-architecture.svg", readme)
        self.assertNotIn("system-architecture.drawio", readme)
        self.assertNotIn("system-architecture-prompt.md", readme)


if __name__ == "__main__":
    unittest.main()
