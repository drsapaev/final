import unittest

from scripts.add_pr_review_adoption_entry import AdoptionEntry, append_entry, format_entry


class AdoptionEntryTests(unittest.TestCase):
    def test_format_entry_matches_adoption_log_shape(self):
        entry = AdoptionEntry(
            entry_date="2026-05-02",
            focus="Example PR",
            track="Contract / Scope",
            evidence="PR body and diff",
            gate_result="passed",
            repeated_gap="none",
            prevention="none",
            next_action="record next live adoption entry",
        )

        self.assertEqual(
            format_entry(entry),
            "\n".join(
                [
                    "## 2026-05-02 - Example PR",
                    "",
                    "- Track: Contract / Scope",
                    "- Evidence reviewed: PR body and diff",
                    "- Gate result: passed",
                    "- Repeated gap observed: none",
                    "- Prevention added: none",
                    "- Next action: record next live adoption entry",
                    "",
                ]
            ),
        )

    def test_append_entry_places_new_entry_first_under_log_heading(self):
        log_text = "# Adoption\n\n## Log\n\n## 2026-05-01 - Old Entry\n\n- Track: Scope\n"
        entry_text = "## 2026-05-02 - New Entry\n\n- Track: Contract\n\n"

        updated = append_entry(log_text, entry_text)

        self.assertIn("## Log\n\n## 2026-05-02 - New Entry", updated)
        self.assertLess(
            updated.index("## 2026-05-02 - New Entry"),
            updated.index("## 2026-05-01 - Old Entry"),
        )

    def test_append_entry_requires_log_heading(self):
        with self.assertRaises(ValueError):
            append_entry("# Adoption\n", "## 2026-05-02 - Entry\n")


if __name__ == "__main__":
    unittest.main()
