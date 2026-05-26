import unittest

from dedupe import unique


class DedupeTest(unittest.TestCase):
    def test_preserves_first_seen_order(self):
        self.assertEqual(unique(["b", "a", "b", "c", "a"]), ["b", "a", "c"])


if __name__ == "__main__":
    unittest.main()

