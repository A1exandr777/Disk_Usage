import io
import sys
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import diskUsage
from fileData import FileData


class TestDiskUsage(unittest.TestCase):

    def test_convert_bytes(self):
        self.assertEqual(diskUsage.convert_bytes(500), "500.0 B")
        self.assertEqual(diskUsage.convert_bytes(2048), "2.0 KB")
        self.assertEqual(diskUsage.convert_bytes(5 * 1024**2), "5.0 MB")
        self.assertEqual(diskUsage.convert_bytes(3 * 1024**3), "3.0 GB")

    def test_get_size(self):
        import tempfile
        import pathlib

        with tempfile.TemporaryDirectory() as tmpdir:
            p = pathlib.Path(tmpdir)
            f1 = p / "a.txt"
            f1.write_text("abc")
            f2 = p / "b.txt"
            f2.write_bytes(b"123456")

            size = diskUsage.get_size(str(p))
            self.assertEqual(size, f1.stat().st_size + f2.stat().st_size)

    @patch("diskUsage.walk")
    @patch("diskUsage.path.getsize")
    @patch("diskUsage.stat")
    def test_traversal(self, mock_stat, mock_getsize, mock_walk):
        now = datetime.now(timezone(timedelta(hours=5)))
        mock_stat.return_value.st_mtime = now.timestamp()
        mock_getsize.return_value = 100

        mock_walk.return_value = [
            ("/base", ["dir1"], ["f1.txt"]),
            ("/base/dir1", [], ["f2.txt"]),
        ]

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            result, max_len = diskUsage.traversal("/base")
            output = fake_out.getvalue()

        self.assertTrue(any(isinstance(r, FileData) for r in result))
        self.assertIn("Scanning complete!", output)
        self.assertGreater(max_len, 0)

    def test_sort_dirs_name_size_depth_modify(self):
        files = [
            FileData("b.txt", 200, 2, "", False, datetime.now()),
            FileData("a.txt", 100, 1, "", False, datetime.now()),
        ]

        by_name = diskUsage.sort_dirs(files, "name", False)
        self.assertEqual([f.name for f in by_name], ["a.txt", "b.txt"])

        by_size = diskUsage.sort_dirs(files, "size", False)
        self.assertEqual(by_size[0].size, 200)

        by_depth = diskUsage.sort_dirs(files, "depth", False)
        self.assertEqual(by_depth[0].depth, 1)

        by_time = diskUsage.sort_dirs(files, "modify", True)
        self.assertIsInstance(by_time[0].time, datetime)


if __name__ == '__main__':
    unittest.main()
