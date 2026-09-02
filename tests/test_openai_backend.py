import json
import unittest
from unittest.mock import patch

from recon.openai_backend import OpenAIBackend


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        body = {"output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps({"ids": ["TXN00001", "ORD00001"]})}
        ]}]}
        return json.dumps(body).encode()


class OpenAIBackendTests(unittest.TestCase):
    @patch("recon.openai_backend.urlopen", return_value=FakeResponse())
    def test_extracts_structured_model_output(self, mocked_urlopen):
        backend = OpenAIBackend(api_key="test-key", model="test-model")

        ids = backend.extract_ids("some narration")

        self.assertEqual(ids, ("TXN00001", "ORD00001"))
        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertFalse(payload["store"])


if __name__ == "__main__":
    unittest.main()
