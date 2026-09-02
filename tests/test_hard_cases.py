import csv
import tempfile
import unittest
from pathlib import Path

import generate_data
from recon.load import load_bank


class HardCaseTests(unittest.TestCase):
    def test_break_mix_allocates_hard_residual(self):
        counts = {name: generate_data.allocate_break_types(100).count(name)
                  for name in generate_data.BREAK_MIX}

        self.assertEqual(counts["narration_recovery"], 10)
        self.assertEqual(counts["same_amount_collision"], 5)
        self.assertEqual(counts["agent_disagreement"], 4)

    def test_bank_loader_preserves_narration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bank.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(("utr", "settlement_amount_paise", "value_date", "bank_narration"))
                writer.writerow(("U1", "100", "2026-01-03", "PG REF T1"))

            row = load_bank(path)[0]

        self.assertEqual(row.bank_narration, "PG REF T1")

    def test_three_recoveries_lack_corroborating_order_reference(self):
        generator = generate_data.Generator(generate_data.SEED)
        for number in range(1, 11):
            generator.generate_group(number, "narration_recovery")

        missing = [row for row in generator.bank if "REFERENCE MISSING" in row["bank_narration"]]

        self.assertEqual(len(missing), 3)

    def test_hard_multiplier_increases_hard_case_share(self):
        baseline = generate_data.scaled_break_mix(1.0)
        harder = generate_data.scaled_break_mix(2.0)
        hard_types = ("narration_recovery", "same_amount_collision", "agent_disagreement")

        self.assertGreater(sum(harder[name] for name in hard_types),
                           sum(baseline[name] for name in hard_types))
        self.assertAlmostEqual(sum(harder.values()), 1.0)


if __name__ == "__main__":
    unittest.main()
