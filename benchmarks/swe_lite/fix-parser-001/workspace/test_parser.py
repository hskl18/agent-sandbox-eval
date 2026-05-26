import unittest

from parser import parse_line


class ParserTest(unittest.TestCase):
    def test_parse_line(self):
        self.assertEqual(parse_line("mode = prod"), ("mode", "prod"))


if __name__ == "__main__":
    unittest.main()

