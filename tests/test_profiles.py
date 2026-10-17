from __future__ import annotations

import copy
import csv
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "host"))

from profile_support import (  # noqa: E402
    ProfileError,
    assertion_failures,
    decode_word,
    list_profiles,
    load_profile,
    validate_profile,
)


class ProfileTests(unittest.TestCase):
    def test_bundled_profiles_validate(self) -> None:
        self.assertEqual(
            {profile["id"] for profile in list_profiles()},
            {"counter", "logic4", "c17", "s27"},
        )

    def test_logic4_physical_trace(self) -> None:
        profile = load_profile("logic4")
        words = [
            0x45DB, 0x466C, 0x46ED, 0x476E, 0x47FF, 0x4000, 0x4081, 0x4102,
            0x41D3, 0xC204, 0xC285, 0xC306, 0xC3D7, 0xC408, 0xC489, 0xC50A,
        ]
        rows = [decode_word(profile, index, word) for index, word in enumerate(words)]
        self.assertEqual(rows[8]["stimulus"], 3)
        self.assertEqual(rows[8]["y"], 1)
        self.assertEqual(rows[8]["trigger"], 1)
        self.assertFalse(assertion_failures(profile, rows))

    def test_counter_decode(self) -> None:
        profile = load_profile("counter")
        row = decode_word(profile, 8, 0x4520)
        self.assertEqual(row["count"], 0x20)
        self.assertEqual(row["state"], 1)
        self.assertEqual(row["running"], 1)
        self.assertEqual(row["trigger"], 1)

    def test_out_of_range_probe_is_rejected(self) -> None:
        profile = copy.deepcopy(load_profile("counter"))
        profile.pop("_path", None)
        profile["signals"][0] = {"name": "bad", "lsb": 15, "width": 2}
        with self.assertRaises(ProfileError):
            validate_profile(profile)

    def test_unsafe_expression_is_rejected(self) -> None:
        profile = copy.deepcopy(load_profile("logic4"))
        profile.pop("_path", None)
        profile["assertions"][0]["expression"] = "__import__('os').system('echo bad')"
        with self.assertRaises(ProfileError):
            validate_profile(profile)

    def test_c17_exhaustive_truth_table(self) -> None:
        profile = load_profile("c17")
        rows = []
        for vector in range(32):
            n1 = (vector >> 0) & 1
            n2 = (vector >> 1) & 1
            n3 = (vector >> 2) & 1
            n6 = (vector >> 3) & 1
            n7 = (vector >> 4) & 1
            n10 = 1 ^ (n1 & n3)
            n11 = 1 ^ (n3 & n6)
            n16 = 1 ^ (n2 & n11)
            n19 = 1 ^ (n11 & n7)
            n22 = 1 ^ (n10 & n16)
            n23 = 1 ^ (n16 & n19)
            word = vector | (n22 << 5) | (n23 << 6)
            rows.append(decode_word(profile, vector, word))
        self.assertEqual(assertion_failures(profile, rows), [])

    def test_c17_committed_hardware_trace(self) -> None:
        capture = ROOT / "captures" / "c17_example.csv"
        with capture.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 16)
        self.assertEqual([int(row["index"]) for row in rows], list(range(16)))
        vectors = [
            int(row["N1"])
            | (int(row["N2"]) << 1)
            | (int(row["N3"]) << 2)
            | (int(row["N6"]) << 3)
            | (int(row["N7"]) << 4)
            for row in rows
        ]
        self.assertEqual(vectors, list(range(16)))
        self.assertEqual([int(row["trigger"]) for row in rows], [0] * 8 + [1] + [0] * 7)
        self.assertTrue(all(int(row["N22_ok"]) for row in rows))
        self.assertTrue(all(int(row["N23_ok"]) for row in rows))

    def test_s27_committed_hardware_trace(self) -> None:
        capture = ROOT / "captures" / "s27_example.csv"
        with capture.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 16)
        self.assertEqual([int(row["index"]) for row in rows], list(range(16)))
        # The stimulus index must be contiguous so the trace proves correct
        # chronological ordering across the circular-buffer wrap.
        self.assertEqual([int(row["stimulus"]) for row in rows], list(range(16)))
        self.assertEqual([int(row["trigger"]) for row in rows], [0] * 8 + [1] + [0] * 7)
        self.assertTrue(all(int(row["expected_word_ok"]) for row in rows))

    def test_expected_words_are_checked(self) -> None:
        profile = load_profile("s27")
        expected = [int(value, 0) for value in profile["expected_words"]]
        rows = [decode_word(profile, index, word) for index, word in enumerate(expected)]
        self.assertFalse(assertion_failures(profile, rows))

        rows[3] = decode_word(profile, 3, expected[3] ^ 0x10)
        self.assertEqual(
            assertion_failures(profile, rows),
            [(3, "expected_word_ok", 0, 1)],
        )


if __name__ == "__main__":
    unittest.main()
