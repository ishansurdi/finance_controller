"""Optional hosted narration interpreter using OpenAI Structured Outputs."""

import json
import os
from urllib.request import Request, urlopen


class OpenAIBackend:
    """Extract finance references with a model; verifier authority remains local."""

    name = "openai_responses_api"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-5.5")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for --agent-backend openai")

    def extract_ids(self, narration: str) -> tuple[str, ...]:
        schema = {
            "type": "object",
            "properties": {"ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["ids"],
            "additionalProperties": False,
        }
        payload = {
            "model": self.model,
            "instructions": (
                "Extract explicit transaction IDs beginning TXN and order IDs beginning ORD. "
                "Do not infer, repair, or invent identifiers. Return each in appearance order."
            ),
            "input": narration,
            "text": {"format": {"type": "json_schema", "name": "finance_references",
                                "strict": True, "schema": schema}},
            "store": False,
        }
        request = Request("https://api.openai.com/v1/responses",
                          data=json.dumps(payload).encode("utf-8"), method="POST",
                          headers={"Authorization": f"Bearer {self.api_key}",
                                   "Content-Type": "application/json"})
        with urlopen(request, timeout=30) as response:
            body = json.load(response)
        text = next(content["text"] for item in body["output"] if item["type"] == "message"
                    for content in item["content"] if content["type"] == "output_text")
        return tuple(json.loads(text)["ids"])
