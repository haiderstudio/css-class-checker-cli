# css-class-checker-cli

Check CSS files for classes nothing uses, fail CI when any are found.

[![CI](https://github.com/haiderstudio/css-class-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/css-class-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`css_class_checker` reads the CSS files in a project folder,
pulls out every class selector, and checks each one against
the project's HTML, JS, JSX, TS, and TSX files:

- Dead CSS classes pile up in every stylesheet — the site
  ships rules nothing uses, and nobody dares delete a class
  by hand in case something somewhere still references it.
  This tool reports every class that is never referenced,
  with the file and the line number where it is defined, so
  deleting it is a safe, mechanical step. It exits 1 when
  any unused class is found, so it can fail a CI run. A
  project with no unused classes exits 0.
- Classes come from the selector text only — the part before
  each `{` — so a value in a declaration body (like
  `margin: .5em`) is never read as a class. Comments are
  stripped first, so a class named in a comment is never
  reported. A class inside a media query is still checked,
  and a class defined twice is checked at both places.
- References are plain text: a class counts as used when its
  name appears as a whole word in any scanned file — in a
  `class` attribute, a `className`, a template literal, a
  `classList` call, or anywhere else the name is written out.
  `btn-primary` never counts as a reference to `btn`, because
  hyphenated names are read as one word.
- A project folder is given on the command line, and it is
  walked recursively by default (`--no-recursive` stops at
  the top level). A single CSS file can be given instead —
  only that file is checked, and its reference files come
  from the folder it sits in. `.git`, `__pycache__`, and
  `node_modules` folders are never walked, and directory
  links are never followed, so a link cycle cannot loop the
  check.
- `--ignore CLASS` treats a class as used, for classes built
  up at run time from pieces (for example `'btn-' + size`)
  that a plain-text scan cannot see. It can be repeated, and
  a leading dot is optional. Only use it for classes you
  know are used — every ignored class is one the tool stops
  checking.
- `--exclude PATTERN` skips walked files by glob, for example
  `--exclude 'vendor-*'`. It can be repeated. A file passed
  directly on the command line is always checked, even if it
  matches an exclude pattern.
- `--json` prints the result as machine-readable JSON (the
  summary goes to standard error, so standard output stays
  clean JSON).
- It is report-only and runs fully offline: it never edits a
  file, sends nothing anywhere, and needs no API key. Python
  standard library only — plain-text parsing, no CSS parser.

## What it does NOT do

- It does not check duplicate or similar classes. That job
  is owned by ruilisi/css-checker, 588 stars — a Go CLI
  built for it, installable via `go install` and released on
  npm as css-checker-kit. This tool's one job is unused
  classes, and it does not try to do the other one.
- It does not delete unused classes. An unused class is
  reported with its file and line; deleting it is your job.
- It does not render pages or run JavaScript, so a class
  that only appears after a script runs is invisible to it
  unless the name is written somewhere in the source. The
  `--ignore` flag covers classes you know are used that way.
- It does not read classes from a stylesheet loaded from a
  URL. Every input is a local file or folder.
- It does not understand escaped class names in CSS (like
  `.\31 23`) — those are not extracted and so are not
  checked. Plain class names, which is what stylesheets
  actually use, are all covered.

## Who it is for

Anyone with a stylesheet that has grown over time and wants
the dead weight out: a developer tidying a site before a
redesign, a team adding a CI step that fails the build when
a stylesheet gains a class nothing uses, or anyone who has
ever been afraid to delete a class in case something still
references it. Every unused class is named with its file
and line — the delete is safe.

## How this differs from similar tools

The exact name `css-class-checker-cli` matches 0
repositories on GitHub (checked Nov 10, 2026), and the
wider field is `css class checker` with 30 matches. The
top one is ruilisi/css-checker, 588 stars — "Reduce Similar
& Duplicated CSS Classes with Diff in Seconds!" Its unused
check is an alpha side feature (`-unused` flag), not its
core job: it prints each unused class with its file path
only — no line number — and it always exits 0, so it cannot
fail a CI run (verified against its own source, Nov 10,
2026: no line number in its unused report, no exit code
anywhere in its main program). The two dedicated
unused-class tools are kgoedecke/unused-css-parser, 3 stars
— "finds unused CSS classes in files and displays them",
with no test or CI claim — and
codewordcreative/unused-css-class-checker, 2 stars — it
checks classes in rendered HTML, so it needs a running
page. None of them is a tested Python CLI that checks a
project's CSS files for unused classes, reports each with
file and line, and exits 1 for CI. This tool does that one
job: a Python standard-library-only CLI that finds unused
CSS classes — no install beyond Python, no website, no
network, no rendered page.

## Install

Python standard library only — no packages to download. You need
Python 3.8 or newer. Clone the repo and run it in place:

```
git clone https://github.com/haiderstudio/css-class-checker-cli.git
cd css-class-checker-cli
python3 src/css_class_checker.py examples/site/clean.css
```

```
examples/site/clean.css: OK — all 2 class(es) used
OK — 1 CSS file(s) checked, 2 class(es), none unused.
```

## Usage

Check one clean stylesheet (its references come from the folder
it sits in):

```
python3 src/css_class_checker.py examples/site/clean.css
```

```
examples/site/clean.css: OK — all 2 class(es) used
OK — 1 CSS file(s) checked, 2 class(es), none unused.
```

Check a stylesheet with unused classes — `.title` (defined in
the `.card .title` rule, but no page uses a `title` class),
`.unused-banner`, `.unused-footer`, and `.sidebar` (inside the
media query):

```
python3 src/css_class_checker.py examples/site/styles.css
```

```
FAIL examples/site/styles.css:18: unused class '.title' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:21: unused class '.unused-banner' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:24: unused class '.unused-footer' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:28: unused class '.sidebar' — not referenced in any HTML, JS, JSX, TS, or TSX file
Checked 1 CSS file(s) (11 class(es)), 4 problem(s) in 1 file(s).
```

Check a whole project folder:

```
python3 src/css_class_checker.py examples/site
```

```
examples/site/clean.css: OK — all 2 class(es) used
FAIL examples/site/styles.css:18: unused class '.title' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:21: unused class '.unused-banner' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:24: unused class '.unused-footer' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:28: unused class '.sidebar' — not referenced in any HTML, JS, JSX, TS, or TSX file
Checked 2 CSS file(s) (13 class(es)), 4 problem(s) in 1 file(s).
```

Whitelist a class you know is used at run time:

```
python3 src/css_class_checker.py --ignore unused-banner examples/site/styles.css
```

```
FAIL examples/site/styles.css:18: unused class '.title' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:24: unused class '.unused-footer' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:28: unused class '.sidebar' — not referenced in any HTML, JS, JSX, TS, or TSX file
Checked 1 CSS file(s) (11 class(es)), 3 problem(s) in 1 file(s).
```

Machine-readable output with `--json` (the summary goes to
standard error, so standard output stays clean JSON):

```
python3 src/css_class_checker.py --json examples/site/styles.css
```

```
{
  "files": [
    {
      "file": "examples/site/styles.css",
      "classes": 11,
      "problems": [
        {
          "file": "examples/site/styles.css",
          "line": 18,
          "reason": "unused class '.title' \u2014 not referenced in any HTML, JS, JSX, TS, or TSX file"
        },
        {
          "file": "examples/site/styles.css",
          "line": 21,
          "reason": "unused class '.unused-banner' \u2014 not referenced in any HTML, JS, JSX, TS, or TSX file"
        },
        {
          "file": "examples/site/styles.css",
          "line": 24,
          "reason": "unused class '.unused-footer' \u2014 not referenced in any HTML, JS, JSX, TS, or TSX file"
        },
        {
          "file": "examples/site/styles.css",
          "line": 28,
          "reason": "unused class '.sidebar' \u2014 not referenced in any HTML, JS, JSX, TS, or TSX file"
        }
      ]
    }
  ],
  "summary": {
    "checked": 1,
    "classes": 11,
    "files_with_problems": 1,
    "problems": 4
  }
}
```

Exit codes: 0 when every class is used, 1 when any unused
class is found, 2 for a usage problem (no paths given, a bad
flag, or a missing file or folder).

## Examples

### 1. A small example site, whole folder

`examples/site/` holds two stylesheets, an HTML page, a JS
file, and a JSX file. One stylesheet is clean, the other has
four unused classes:

```
python3 src/css_class_checker.py examples/site
```

```
examples/site/clean.css: OK — all 2 class(es) used
FAIL examples/site/styles.css:18: unused class '.title' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:21: unused class '.unused-banner' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:24: unused class '.unused-footer' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:28: unused class '.sidebar' — not referenced in any HTML, JS, JSX, TS, or TSX file
Checked 2 CSS file(s) (13 class(es)), 4 problem(s) in 1 file(s).
```

### 2. One stylesheet, references from its folder

```
python3 src/css_class_checker.py examples/site/styles.css
```

```
FAIL examples/site/styles.css:18: unused class '.title' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:21: unused class '.unused-banner' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:24: unused class '.unused-footer' — not referenced in any HTML, JS, JSX, TS, or TSX file
FAIL examples/site/styles.css:28: unused class '.sidebar' — not referenced in any HTML, JS, JSX, TS, or TSX file
Checked 1 CSS file(s) (11 class(es)), 4 problem(s) in 1 file(s).
```

### 3. The bundled examples, all at once

```
sh examples/run-example.sh
```

The script checks the whole `examples/site/` folder (fail,
on purpose — the example stylesheet has four unused
classes). Its full output is in
`examples/sample-output.md`, ending with `Checked 2 CSS
file(s) (13 class(es)), 4 problem(s) in 1 file(s).` The
failing run exits 1, which is the expected result — the
script ends with exit 0 so it can be run as a demo.

## How it is tested

Tests, standard library `unittest` only, no packages to install:

```
python3 tests/test_css_class_checker.py
```

The tests cover: class extraction (simple rules, multiple
classes in one selector, pseudo-classes and pseudo-elements,
classes inside media queries, a class defined twice, a
class-like word in a comment, a class-like word in an
attribute-selector value, a decimal value that is not a
class, hyphenated and underscored names, a class starting
with a digit that is not a class, line numbers across a
multi-line file, an empty stylesheet), reference scanning
(class attributes, className, template literals, classList
calls, hyphenated names that do not count for their prefix,
case sensitivity, a class named only in a comment that still
counts as used), the check itself (all used, all unused, an
ignored class with and without a leading dot, an unreadable
CSS file), file collection (a folder walk, `.git` and
`node_modules` skipped, `--no-recursive`, `--exclude`, a
direct CSS file checked alone with references from its
folder, a direct reference file, a missing path, an empty
folder, uppercase `.CSS` extensions), the CLI (exit 0/1/2,
each flag, `--json` output, `--version`, bad flags, missing
paths, a folder summary count, and every bundled example
file read back with its expected problems), the bundled
examples (sample output compared byte-for-byte against a
fresh run, and the README-quoted outputs checked against
it), and hygiene checks (no placeholder text, no absolute
paths, stdlib imports only, `.env` first in `.gitignore`,
CI file runs the test file).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The idea
of checking CSS files for unused classes is not new — the
similar tools named above (the 588-star css-checker, the
3-star unused-css-parser, the 2-star rendered-HTML checker)
are listed in "How this differs" — but every line of code
here is original, and the tool builds on nothing but
Python's standard library. The duplicate/similar-classes
job is deliberately left to ruilisi/css-checker, which owns
it.
