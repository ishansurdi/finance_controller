import os
import tempfile
import unittest
from pathlib import Path

from recon.environment import load_env


class EnvironmentTests(unittest.TestCase):
    def test_loads_values_without_overwriting_process_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("FIRST=value\nSECOND=file-value\n", encoding="utf-8")
            os.environ["SECOND"] = "process-value"
            try:
                load_env(path)
                self.assertEqual(os.environ["FIRST"], "value")
                self.assertEqual(os.environ["SECOND"], "process-value")
            finally:
                os.environ.pop("FIRST", None)
                os.environ.pop("SECOND", None)


if __name__ == "__main__":
    unittest.main()
