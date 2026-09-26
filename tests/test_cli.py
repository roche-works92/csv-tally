import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from csvtally.cli import main, resolve_column, resolve_columns, tally


class FakeStdin:
    """Mimics the parts of sys.stdin that open_input() touches."""

    def __init__(self, data):
        self.buffer = io.BytesIO(data)


class ResolveColumnTests(unittest.TestCase):
    def test_by_name(self):
        self.assertEqual(resolve_column(["id", "status"], "status", True), 1)

    def test_by_numeric_fallback_with_header(self):
        # a column argument that isn't a header name but parses as an int
        # is treated as a positional index even when a header is present
        self.assertEqual(resolve_column(["id", "status"], "1", True), 1)

    def test_unknown_name_raises(self):
        with self.assertRaises(SystemExit):
            resolve_column(["id", "status"], "nope", True)

    def test_no_header_requires_numeric(self):
        self.assertEqual(resolve_column([], "2", False), 2)
        with self.assertRaises(SystemExit):
            resolve_column([], "status", False)


class ResolveColumnsTests(unittest.TestCase):
    def test_single_column(self):
        self.assertEqual(resolve_columns(["id", "status"], "status", True), [1])

    def test_compound_key(self):
        self.assertEqual(
            resolve_columns(["id", "status", "region"], "status,region", True), [1, 2]
        )

    def test_compound_key_no_header(self):
        self.assertEqual(resolve_columns([], "0,2", False), [0, 2])


class TallyTests(unittest.TestCase):
    def test_counts_and_skips_short_rows(self):
        rows = [["a"], ["b", "x"], ["b", "x"], ["c"]]
        counts, skipped = tally(rows, [1])
        self.assertEqual(counts, {("x",): 2})
        self.assertEqual(skipped, 2)

    def test_compound_key(self):
        rows = [["a", "us"], ["a", "us"], ["a", "eu"], ["b", "us"]]
        counts, skipped = tally(rows, [0, 1])
        self.assertEqual(
            counts, {("a", "us"): 2, ("a", "eu"): 1, ("b", "us"): 1}
        )
        self.assertEqual(skipped, 0)


class MainEndToEndTests(unittest.TestCase):
    def _run_with_file(self, content, argv):
        fd, path = tempfile.mkstemp(suffix=".csv")
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
                f.write(content)
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(argv + [path])
            return code, out.getvalue()
        finally:
            os.remove(path)

    def test_quoted_field_with_embedded_comma_is_one_value(self):
        content = (
            "id,status,region\n"
            "1,shipped,us\n"
            "2,pending,eu\n"
            "3,shipped,us\n"
            '4,"cancelled, refunded",us\n'
        )
        code, out = self._run_with_file(content, ["status"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertIn("2\tshipped", lines)
        self.assertIn("1\tcancelled, refunded", lines)

    def test_quoted_field_with_embedded_newline_is_one_value(self):
        content = (
            "id,notes\n"
            '1,"line one\nline two"\n'
            '2,"line one\nline two"\n'
            "3,plain\n"
        )
        code, out = self._run_with_file(content, ["notes"])
        self.assertEqual(code, 0)
        self.assertIn("2\tline one\nline two", out)
        self.assertIn("1\tplain", out)

    def test_sort_and_limit(self):
        content = "k\na\na\nb\nc\nc\nc\n"
        code, out = self._run_with_file(content, ["k", "-n", "1"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "3\tc")

    def test_ascending_sort_by_value(self):
        content = "k\nb\na\nc\n"
        code, out = self._run_with_file(content, ["k", "--sort", "value", "--ascending"])
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["1\ta", "1\tb", "1\tc"])

    def test_no_header_numeric_column(self):
        content = "a,1\nb,2\nb,2\n"
        code, out = self._run_with_file(content, ["1", "--no-header"])
        self.assertEqual(code, 0)
        self.assertIn("2\t2", out)

    def test_compound_key_columns(self):
        content = (
            "id,status,region\n"
            "1,shipped,us\n"
            "2,shipped,us\n"
            "3,shipped,eu\n"
            "4,pending,us\n"
        )
        code, out = self._run_with_file(content, ["status,region"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertIn("2\tshipped\tus", lines)
        self.assertIn("1\tshipped\teu", lines)
        self.assertIn("1\tpending\tus", lines)

    def test_custom_delimiter(self):
        content = "k|v\nx|1\nx|1\ny|2\n"
        code, out = self._run_with_file(content, ["v", "-d", "|"])
        self.assertEqual(code, 0)
        self.assertIn("2\t1", out)

    def test_skipped_rows_reported_on_stderr(self):
        content = "a,b\n1,2\n3\n"
        fd, path = tempfile.mkstemp(suffix=".csv")
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
                f.write(content)
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = main(["b", path])
            self.assertEqual(code, 0)
            self.assertIn("skipped 1 row(s)", err.getvalue())
        finally:
            os.remove(path)

    def test_no_data_rows_is_an_error(self):
        content = "a,b\n"
        fd, path = tempfile.mkstemp(suffix=".csv")
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
                f.write(content)
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = main(["b", path])
            self.assertEqual(code, 1)
            self.assertIn("no data rows found", err.getvalue())
        finally:
            os.remove(path)

    def test_reads_from_stdin_when_file_omitted(self):
        data = b"id,status\n1,shipped\n2,shipped\n"
        out = io.StringIO()
        with mock.patch("sys.stdin", FakeStdin(data)):
            with redirect_stdout(out):
                code = main(["status"])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), "2\tshipped")

    def test_dash_also_reads_from_stdin(self):
        data = b"id,status\n1,pending\n"
        out = io.StringIO()
        with mock.patch("sys.stdin", FakeStdin(data)):
            with redirect_stdout(out):
                code = main(["status", "-"])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), "1\tpending")


if __name__ == "__main__":
    unittest.main()
