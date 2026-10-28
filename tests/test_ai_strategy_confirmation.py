from pathlib import Path
import tempfile
import unittest

from ai.strategy_confirmation import claim_cohort,freeze


class ConfirmationProtocolTests(unittest.TestCase):
    def test_development_and_overlapping_reserved_protocols_are_rejected(self):
        with self.assertRaises(ValueError):freeze('unused',13,'unused',14950000,20)
        with self.assertRaises(ValueError):freeze('unused',13,'unused',15499000,20)
        with self.assertRaises(ValueError):freeze('unused',12,'unused',15400000,20)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);ledger=root/'ledger.jsonl'
            manifest=dict(seed=15400000,games=20,cases=[{}]*192)
            claim_cohort(manifest,root/'a.json',root/'a-result.json',ledger=ledger)
            with self.assertRaises(ValueError):
                claim_cohort(manifest,root/'different.json',root/'different-result.json',ledger=ledger)
            with self.assertRaises(ValueError):
                claim_cohort({**manifest,'seed':15400010},root/'overlap.json',root/'overlap-result.json',ledger=ledger)
            claim_cohort({**manifest,'seed':15400050},root/'cold.json',root/'cold-result.json',ledger=ledger)
            self.assertEqual(2,len(ledger.read_text().splitlines()))
