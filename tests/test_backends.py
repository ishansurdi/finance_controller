import unittest
from pathlib import Path

from recon.agents import AbstainBackend, ReplayBackend


class BackendTests(unittest.TestCase):
    def test_replay_returns_recorded_response(self):
        backend = ReplayBackend(Path("replay/agent_responses.json"))
        ids = backend.extract_ids("PG SETTLEMENT REF TXN00001 / ORD00001")
        self.assertEqual(ids, ("TXN00001", "ORD00001"))

    def test_fallback_always_abstains(self):
        self.assertEqual(AbstainBackend().extract_ids("TXN00001"), ())


if __name__ == "__main__":
    unittest.main()
