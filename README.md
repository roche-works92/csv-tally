# csvtally

Count how many times each distinct value shows up in one column of a CSV
file.

`cut -d, -f2 file.csv | sort | uniq -c` is the usual way people do this, and
it works right up until a field contains a quoted comma or an embedded
newline, at which point the column boundaries silently shift and the counts
are wrong. csvtally parses the file with Python's `csv` module instead of
splitting on the delimiter by hand, so quoting is handled correctly.

## Install

No dependencies beyond the standard library. Either run the module directly:

```
python -m csvtally.cli status orders.csv
```

or install it so the `csvtally` command is on your PATH:

```
pip install -e .
csvtally status orders.csv
```

## Usage

Given `orders.csv`:

```
id,status,region
1,shipped,us
2,pending,eu
3,shipped,us
4,"cancelled, refunded",us
```

Count values in the `status` column:

```
$ csvtally status orders.csv
2	shipped
1	pending
1	cancelled, refunded
```

Read from stdin instead of a file (omit the file argument, or pass `-`):

```
$ cat orders.csv | csvtally region
3	us
1	eu
```

This also means it composes with other tools:

```
$ grep 2024 orders.csv | csvtally status -
```

## Options

```
csvtally COLUMN [FILE] [-d DELIMITER] [--no-header] [--sort {count,value}]
                [--ascending] [-n LIMIT]
```

- `COLUMN` - column name, or a 0-based index when used with `--no-header`.
- `FILE` - path to a CSV file. Omit, or pass `-`, to read from stdin.
- `-d, --delimiter` - field delimiter, default `,`.
- `--no-header` - treat the first row as data instead of column names.
- `--sort {count,value}` - sort by occurrence count (default) or by the
  value itself.
- `--ascending` - reverse the default descending sort.
- `-n, --limit N` - show only the top N rows.

Output is `count<TAB>value`, one line per distinct value, to stdout.
