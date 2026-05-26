import unittest

from env_parser import parse_env


class EnvParserTest(unittest.TestCase):
    def test_ignores_comments_and_blanks(self):
        lines = ["API_KEY=abc", "", "# comment", "MODE = prod"]
        self.assertEqual(parse_env(lines), {"API_KEY": "abc", "MODE": "prod"})


if __name__ == "__main__":
    unittest.main()

