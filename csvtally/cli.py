"""Count occurrences of distinct values in one CSV column."""

import argparse
import csv
import io
import sys
from collections import Counter


def open_input(path):
    # Wrapping stdin's binary buffer with newline='' (rather than using
    # sys.stdin directly) keeps embedded newlines inside quoted fields
    # intact, the same way csv.reader expects a file opened with newline=''.
    if path is None or path == "-":
        return io.TextIOWrapper(sys.stdin.buffer, newline="", encoding="utf-8")
    return open(path, newline="", encoding="utf-8")


def resolve_column(header, column_arg, has_header):
    if not has_header:
        try:
            return int(column_arg)
        except ValueError:
            raise SystemExit(
                f"--no-header requires a numeric column index, got {column_arg!r}"
            )
    if column_arg in header:
        return header.index(column_arg)
    try:
        return int(column_arg)
    except ValueError:
        raise SystemExit(
            f"column {column_arg!r} not found in header: {header}"
        )


def tally(rows, index):
    counts = Counter()
    skipped = 0
    for row in rows:
        if index >= len(row):
            skipped += 1
            continue
        counts[row[index]] += 1
    return counts, skipped


def format_table(counts, sort_by, ascending, limit):
    items = list(counts.items())
    if sort_by == "value":
        items.sort(key=lambda pair: pair[0], reverse=not ascending)
    else:
        items.sort(key=lambda pair: pair[1], reverse=not ascending)
    if limit is not None:
        items = items[:limit]
    return items


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="csvtally",
        description="Count occurrences of distinct values in one CSV column.",
    )
    parser.add_argument(
        "column",
        help="column name (or 0-based index with --no-header) to tally",
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="CSV file to read; omit or pass - to read from stdin",
    )
    parser.add_argument(
        "-d", "--delimiter", default=",", help="field delimiter (default: ,)"
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="treat the first row as data, not column names",
    )
    parser.add_argument(
        "--sort",
        choices=("count", "value"),
        default="count",
        help="sort results by count or by value (default: count)",
    )
    parser.add_argument(
        "--ascending",
        action="store_true",
        help="sort ascending instead of the default descending",
    )
    parser.add_argument(
        "-n", "--limit", type=int, default=None, help="show only the top N rows"
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    with open_input(args.file) as f:
        reader = csv.reader(f, delimiter=args.delimiter)
        rows = iter(reader)

        if not args.no_header:
            try:
                header = next(rows)
            except StopIteration:
                header = []
        else:
            header = []

        index = resolve_column(header, args.column, not args.no_header)
        counts, skipped = tally(rows, index)

    if not counts:
        print("no data rows found", file=sys.stderr)
        return 1

    for value, count in format_table(counts, args.sort, args.ascending, args.limit):
        print(f"{count}\t{value}")

    if skipped:
        print(f"skipped {skipped} row(s) missing that column", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
