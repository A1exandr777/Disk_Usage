import io
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

import du


class TestDu(unittest.TestCase):

    def test_strip_ansi(self):
        text = "\033[31mHello\033[0m"
        self.assertEqual(du.strip_ansi(text), "Hello")

    def test_truncate_name_short(self):
        name = "short.txt"
        self.assertEqual(du.truncate_name(name, 50), name)

    def test_truncate_name_long(self):
        name = "veryverylongfilename.txt"
        truncated = du.truncate_name(name, 10)
        self.assertIn("...", truncated)
        self.assertTrue(truncated.endswith(".txt"))

    def test_arguments_parsing_defaults(self):
        with patch("sys.argv", ["prog", "path"]):
            args = du.arguments_parsing()
            self.assertEqual(args.base_path, "path")
            self.assertEqual(args.sort, "none")
            self.assertEqual(args.depth, 100)
            self.assertFalse(args.reverse)

    def test_arguments_parsing_custom(self):
        argv = ["prog", "base", "--sort", "size", "--depth", "3", "--reverse",
                "--top", "5", "--block", "50", "--ext", "txt"]
        with patch("sys.argv", argv):
            args = du.arguments_parsing()
            self.assertEqual(args.base_path, "base")
            self.assertEqual(args.sort, "size")
            self.assertEqual(args.depth, 3)
            self.assertTrue(args.reverse)
            self.assertEqual(args.top, 5)
            self.assertEqual(args.block, 50)
            self.assertEqual(args.ext, "txt")

    def test_print_entry_file(self):
        fake_file = type("Entry", (), {})()
        fake_file.name = "file.txt"
        fake_file.size = 1024
        fake_file.is_dir = False
        fake_file.indent = "  "
        fake_file.time = datetime(2023, 1, 1)

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            du.print_entry(fake_file, total_size=2048)
            output = fake_out.getvalue()

        self.assertIn("file.txt", output)
        self.assertIn("50.00%", output)
        self.assertIn("KB", output)

    def test_print_entry_dir(self):
        fake_dir = type("Entry", (), {})()
        fake_dir.name = "mydir"
        fake_dir.size = 500
        fake_dir.is_dir = True
        fake_dir.indent = ""
        fake_dir.time = None

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            du.print_entry(fake_dir, total_size=1000)
            output = fake_out.getvalue()

        # имя каталога выделено цветом (ANSI-код)
        self.assertIn("\033[92mmydir\033[0m", output)
        self.assertIn("50.00%", output)

    @patch("du.get_size", return_value=2000)
    def test_print_table(self, mock_get_size):
        fake1 = type("Entry", (), {})()
        fake1.name = "subdir"
        fake1.size = 1000
        fake1.is_dir = True
        fake1.indent = "  "
        fake1.time = None

        fake2 = type("Entry", (), {})()
        fake2.name = "file.txt"
        fake2.size = 1000
        fake2.is_dir = False
        fake2.indent = "  "
        fake2.time = None

        entries = [fake1, fake2]

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            du.print_table(entries, "/base")
            output = fake_out.getvalue()

        self.assertIn("subdir", output)
        self.assertIn("file.txt", output)
        self.assertIn("100.00%", output)


if __name__ == '__main__':
    unittest.main()
