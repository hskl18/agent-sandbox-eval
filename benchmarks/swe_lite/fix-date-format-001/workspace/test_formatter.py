import unittest
from datetime import date

from formatter import format_date


class FormatterTest(unittest.TestCase):
    def test_iso_date(self):
        self.assertEqual(format_date(date(2026, 5, 26)), "2026-05-26")


if __name__ == "__main__":
    unittest.main()

