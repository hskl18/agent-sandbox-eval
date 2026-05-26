import unittest

from calculator import add


class CalculatorTest(unittest.TestCase):
    def test_adds_numbers(self):
        self.assertEqual(add(20, 22), 42)


if __name__ == "__main__":
    unittest.main()

