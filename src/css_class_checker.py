"""css-class-checker-cli: check CSS files for class selectors never used by the project, fail CI when any are found.

Reads the CSS files in a project folder and extracts every class
selector (`.header`, `.btn:hover`, `.card .title`), then scans the
project's HTML, JS, JSX, TS, and TSX files for references to those
class names. Every class that is never referenced is reported with
the file and the line number where it is defined. Report-only: it
never rewrites a file. Exit 0 when every class is used, 1 when any
unused class is found, 2 for a usage error.

Only UNUSED classes are checked. Duplicate or similar classes are
a different job, owned by ruilisi/css-checker (588 stars) — this
tool does not check them.

References are plain text: a class name counts as used when it
appears as a whole word in any scanned file — in a class
attribute, a className, a template literal, a classList call, or
anywhere else the name is written out. A class built up at run
time from pieces (for example `'btn-' + size`) is not seen as
used; whitelist such classes with --ignore. A class name that
appears only in a comment still counts as used, because the scan
is plain text.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

CSS_SUFFIX = ".css"
REFERENCE_SUFFIXES = (".html", ".htm", ".js", ".jsx", ".ts", ".tsx")
SKIPPED_DIRS = (".git", "__pycache__", "node_modules")

CLASS_RE = re.compile(r"\.(-?[A-Za-z_][A-Za-z0-9_-]*)")
SELECTOR_RE = re.compile(r"([^{}]+)\{")
COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
STRING_RE = re.compile(r'"[^"\n]*"|\'[^\'\n]*\'')
WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


class ClassDef:
    """One class definition in one CSS file: name, path, line."""

    def __init__(self, name, path, line):
        self.name = name
        self.path = path
        self.line = line


class Problem:
    """One unused class: path, line number, plain reason."""

    def __init__(self, path, line, reason):
        self.path = path
        self.line = line
        self.reason = reason

    def text(self):
        return f"{self.path}:{self.line}: {self.reason}"

    def as_dict(self):
        return {"file": self.path, "line": self.line, "reason": self.reason}


def blank_out(match):
    """Replace a comment with spaces, keeping its newlines."""
    return "".join("\n" if char == "\n" else " "
                   for char in match.group(0))


def strip_comments(text):
    """Remove /* ... */ comments without moving later line numbers."""
    return COMMENT_RE.sub(blank_out, text)


def line_of(text, offset):
    """Line number (1-based) of a character offset in text."""
    return text.count("\n", 0, offset) + 1


def extract_classes(text, path):
    """Extract every class selector from one CSS document.

    Only the text before each '{' is a selector, so values in
    declaration bodies (like `margin: .5em`) are never read as
    classes. Quoted strings inside selectors (like
    `a[href$=".pdf"]`) are blanked out first, so a class-like
    word in an attribute value is not read as a definition.
    Returns a list of ClassDefs, in file order.
    """
    text = strip_comments(text)
    found = []
    for selector in SELECTOR_RE.finditer(text):
        segment = selector.group(1)
        start = selector.start(1)
        cleaned = STRING_RE.sub(
            lambda m: " " * len(m.group(0)), segment)
        for match in CLASS_RE.finditer(cleaned):
            found.append(ClassDef(
                match.group(1),
                path,
                line_of(text, start + match.start()),
            ))
    return found


def reference_words(text):
    """All word-like tokens in a reference file, as a set.

    A token is a letter or underscore followed by letters,
    digits, underscores, or hyphens — so `btn-primary` is one
    token and never counts as a reference to `btn`.
    """
    return set(WORD_RE.findall(text))


def check_files(css_files, reference_files, ignored=()):
    """Check CSS files against reference files.

    Returns (results, total_classes) where results is a list of
    (path, class_count, [Problem]) per CSS file, in path order.
    """
    used = set()
    for ref in reference_files:
        try:
            text = Path(ref).read_text(encoding="utf-8",
                                       errors="replace")
        except OSError:
            continue
        used |= reference_words(text)
    ignored = set(normalise_ignored(ignored))
    results = []
    total_classes = 0
    for css_path in css_files:
        try:
            text = Path(css_path).read_text(encoding="utf-8",
                                            errors="replace")
        except OSError as exc:
            results.append((css_path, 0, [Problem(
                css_path, 0,
                f"cannot read file: {exc.strerror or exc}",
            )]))
            continue
        defs = extract_classes(text, css_path)
        total_classes += len(defs)
        problems = [
            Problem(defn.path, defn.line,
                    f"unused class '.{defn.name}' — not referenced "
                    "in any HTML, JS, JSX, TS, or TSX file")
            for defn in defs
            if defn.name not in used and defn.name not in ignored
        ]
        results.append((css_path, len(defs), problems))
    return results, total_classes


def is_excluded(name, patterns):
    """True when a file name matches any --exclude glob pattern."""
    return any(fnmatch.fnmatchcase(name, pattern)
               for pattern in patterns)


def collect(paths, recursive=True, exclude=()):
    """Gather CSS files and reference files from the given paths.

    A folder contributes its .css files and its .html, .htm, .js,
    .jsx, .ts, and .tsx files (recursively unless --no-recursive).
    A CSS file passed directly is always checked, and only that
    file — its reference files come from the folder it sits in.
    .git, __pycache__, and node_modules folders are never walked,
    and directory links are never followed. Returns (css_files,
    reference_files, missing) with files sorted and deduplicated.
    """
    css_files = []
    reference_files = []
    missing = []
    folders = []
    ref_only_folders = []

    def walk(folder, want_css):
        for root, dirs, names in os.walk(folder):
            dirs[:] = sorted(
                name for name in dirs
                if name not in SKIPPED_DIRS
                and not os.path.islink(os.path.join(root, name))
            )
            if not recursive:
                dirs[:] = []
            for name in sorted(names):
                if is_excluded(name, exclude):
                    continue
                full = str(Path(root) / name)
                lower = name.lower()
                if lower.endswith(CSS_SUFFIX):
                    if want_css:
                        css_files.append(full)
                elif lower.endswith(REFERENCE_SUFFIXES):
                    reference_files.append(full)

    for raw in paths:
        path = Path(raw)
        if not path.exists():
            missing.append(raw)
            continue
        if path.is_file():
            if path.name.lower().endswith(CSS_SUFFIX):
                css_files.append(str(path))
                ref_only_folders.append(str(path.parent))
            elif path.name.lower().endswith(REFERENCE_SUFFIXES):
                reference_files.append(str(path))
            else:
                ref_only_folders.append(str(path.parent))
            continue
        folders.append(str(path))
    for folder in folders:
        walk(folder, want_css=True)
    for folder in ref_only_folders:
        walk(folder, want_css=False)
    return (sorted(set(css_files)), sorted(set(reference_files)),
            missing)


def normalise_ignored(names):
    """Strip a leading dot and whitespace from --ignore values."""
    cleaned = []
    for name in names:
        name = name.strip()
        if name.startswith("."):
            name = name[1:]
        if name:
            cleaned.append(name)
    return cleaned


def build_parser():
    parser = argparse.ArgumentParser(
        prog="css_class_checker",
        description="Check CSS files for classes never used by "
                    "the project's HTML, JS, JSX, TS, or TSX files.",
    )
    parser.add_argument(
        "paths", nargs="*", metavar="PATH",
        help="project folder(s) or CSS file(s) to check",
    )
    parser.add_argument(
        "--exclude", action="append", default=[], metavar="PATTERN",
        help="skip walked files whose name matches this glob "
             "(repeatable; direct files are always checked)",
    )
    parser.add_argument(
        "--ignore", action="append", default=[], metavar="CLASS",
        help="treat this class as used (repeatable; a leading "
             "dot is optional, for classes built up at run time)",
    )
    parser.add_argument(
        "--no-recursive", action="store_true",
        help="do not walk into subfolders",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="print the result as machine-readable JSON "
             "(the summary goes to standard error)",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__,
    )
    return parser


def report_text(results, checked, total_classes, total):
    """Print the plain-text report. Returns the exit code."""
    files_with_problems = sum(1 for _, _, probs in results if probs)
    for path, count, problems in results:
        if problems:
            for problem in problems:
                print(f"FAIL {problem.text()}")
        elif count == 0:
            print(f"{path}: OK — no classes found")
        else:
            print(f"{path}: OK — all {count} class(es) used")
    if total == 0:
        print(f"OK — {checked} CSS file(s) checked, "
              f"{total_classes} class(es), none unused.")
        return 0
    print(f"Checked {checked} CSS file(s) ({total_classes} class(es)), "
          f"{total} problem(s) in {files_with_problems} file(s).")
    return 1


def report_json(results, checked, total_classes, total):
    """Print the JSON report. Returns the exit code."""
    files_with_problems = sum(1 for _, _, probs in results if probs)
    payload = {
        "files": [
            {
                "file": path,
                "classes": count,
                "problems": [problem.as_dict() for problem in problems],
            }
            for path, count, problems in results
        ],
        "summary": {
            "checked": checked,
            "classes": total_classes,
            "files_with_problems": files_with_problems,
            "problems": total,
        },
    }
    print(json.dumps(payload, indent=2))
    print(f"Checked {checked} CSS file(s) ({total_classes} class(es)), "
          f"{total} problem(s) in {files_with_problems} file(s).",
          file=sys.stderr)
    return 1 if total else 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.paths:
        parser.error("give at least one PATH")
    css_files, reference_files, missing = collect(
        args.paths,
        recursive=not args.no_recursive,
        exclude=args.exclude,
    )
    if missing:
        for raw in missing:
            print(f"error: no such file or folder: {raw}",
                  file=sys.stderr)
        return 2
    if not css_files:
        print("error: no CSS files found", file=sys.stderr)
        return 2
    ignored = normalise_ignored(args.ignore)
    results, total_classes = check_files(
        css_files, reference_files, ignored)
    total = sum(len(problems) for _, _, problems in results)
    if args.json:
        return report_json(results, len(css_files),
                           total_classes, total)
    return report_text(results, len(css_files), total_classes, total)


if __name__ == "__main__":
    sys.exit(main())
