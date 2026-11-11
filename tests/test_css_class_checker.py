"""Tests for css_class_checker: extraction, references, CLI, examples, hygiene."""

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import css_class_checker as checker

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "css_class_checker.py"
EXAMPLES = ROOT / "examples"
README = ROOT / "README.md"


def defs(text, path="s.css"):
    return [(d.name, d.line)
            for d in checker.extract_classes(text, path)]


class TestExtraction(unittest.TestCase):
    def test_simple_rule(self):
        self.assertEqual(defs(".header {\n  color: red;\n}\n"),
                         [("header", 1)])

    def test_multiple_classes_one_selector(self):
        self.assertEqual(defs(".card .title {\n}\n"),
                         [("card", 1), ("title", 1)])

    def test_comma_selector(self):
        self.assertEqual(defs(".a, .b {\n}\n"),
                         [("a", 1), ("b", 1)])

    def test_pseudo_class(self):
        self.assertEqual(defs(".btn:hover {\n}\n"), [("btn", 1)])

    def test_pseudo_element(self):
        self.assertEqual(defs(".btn::after {\n}\n"), [("btn", 1)])

    def test_media_query_class(self):
        text = "@media (min-width: 600px) {\n  .sidebar {\n}\n}\n"
        self.assertEqual(defs(text), [("sidebar", 2)])

    def test_class_defined_twice(self):
        text = ".header {\n}\n.foo {\n}\n.header {\n}\n"
        self.assertEqual(defs(text), [("header", 1), ("foo", 3),
                                      ("header", 5)])

    def test_comment_class_not_extracted(self):
        text = "/* .fake-class lives here */\n.real {\n}\n"
        self.assertEqual(defs(text), [("real", 2)])

    def test_multiline_comment(self):
        text = "/* one\n.two\nthree */\n.real {\n}\n"
        self.assertEqual(defs(text), [("real", 4)])

    def test_attribute_selector_value_not_a_class(self):
        text = 'a[href$=".pdf"] {\n}\n'
        self.assertEqual(defs(text), [])

    def test_decimal_value_not_a_class(self):
        text = ".a {\n  margin: .5em;\n  opacity: .9;\n}\n"
        self.assertEqual(defs(text), [("a", 1)])

    def test_hyphenated_and_underscored_names(self):
        self.assertEqual(defs(".my-class_name-2 {\n}\n"),
                         [("my-class_name-2", 1)])

    def test_leading_dash_name(self):
        self.assertEqual(defs(".-off {\n}\n"), [("-off", 1)])

    def test_digit_start_not_a_class(self):
        self.assertEqual(defs(".5em {\n}\n"), [])

    def test_line_numbers_across_file(self):
        text = ".a {\n  color: red;\n}\n\n\n.b {\n}\n"
        self.assertEqual(defs(text), [("a", 1), ("b", 6)])

    def test_empty_stylesheet(self):
        self.assertEqual(defs(""), [])
        self.assertEqual(defs("/* nothing here */\n"), [])

    def test_id_selector_not_a_class(self):
        self.assertEqual(defs("#main {\n}\n"), [])

    def test_element_selector_not_a_class(self):
        self.assertEqual(defs("div p {\n}\n"), [])

    def test_class_after_combinator(self):
        self.assertEqual(defs("ul > .item + .other {\n}\n"),
                         [("item", 1), ("other", 1)])

    def test_keyframes_not_classes(self):
        text = "@keyframes spin {\n  from {\n}\n  to {\n}\n}\n"
        self.assertEqual(defs(text), [])


class TestReferenceWords(unittest.TestCase):
    def test_class_attribute(self):
        words = checker.reference_words('<div class="header main">')
        self.assertIn("header", words)
        self.assertIn("main", words)

    def test_class_name_jsx(self):
        words = checker.reference_words('<div className="card">')
        self.assertIn("card", words)

    def test_template_literal(self):
        words = checker.reference_words("`btn ${active ? 'on' : ''}`")
        self.assertIn("btn", words)
        self.assertIn("on", words)

    def test_class_list_call(self):
        words = checker.reference_words(
            "el.classList.add('sidebar');")
        self.assertIn("sidebar", words)

    def test_hyphenated_name_is_one_token(self):
        words = checker.reference_words('<div class="btn-primary">')
        self.assertIn("btn-primary", words)
        self.assertNotIn("btn", words)

    def test_case_sensitive(self):
        words = checker.reference_words('<div class="Header">')
        self.assertIn("Header", words)
        self.assertNotIn("header", words)

    def test_name_only_in_comment_counts_as_used(self):
        # Plain-text scan: a comment mention is still a mention.
        words = checker.reference_words("<!-- the old sidebar -->")
        self.assertIn("sidebar", words)


class TestCheckFiles(unittest.TestCase):
    def run_check(self, css_text, ref_texts, ignored=()):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            css_path = root / "s.css"
            css_path.write_text(css_text)
            refs = []
            for index, text in enumerate(ref_texts):
                ref = root / f"r{index}.html"
                ref.write_text(text)
                refs.append(str(ref))
            results, total = checker.check_files(
                [str(css_path)], refs, ignored)
            return results, total

    def test_all_used(self):
        results, total = self.run_check(
            ".a {\n}\n.b {\n}\n",
            ['<div class="a b">'])
        self.assertEqual(total, 2)
        self.assertEqual(results[0][2], [])

    def test_all_unused(self):
        results, total = self.run_check(
            ".a {\n}\n.b {\n}\n", ['<p>nothing here</p>'])
        self.assertEqual(total, 2)
        self.assertEqual([p.line for p in results[0][2]], [1, 3])

    def test_unused_reason_text(self):
        results, _ = self.run_check(".gone {\n}\n", ["<p>x</p>"])
        problem = results[0][2][0]
        self.assertEqual(problem.text(),
                         results[0][0] + ":1: unused class '.gone' — "
                         "not referenced in any HTML, JS, JSX, TS, "
                         "or TSX file")

    def test_ignored_class_with_dot(self):
        results, _ = self.run_check(
            ".built {\n}\n", ["<p>x</p>"], ignored=[".built"])
        self.assertEqual(results[0][2], [])

    def test_ignored_class_without_dot(self):
        results, _ = self.run_check(
            ".built {\n}\n", ["<p>x</p>"], ignored=["built"])
        self.assertEqual(results[0][2], [])

    def test_ignored_only_ignores_that_class(self):
        results, _ = self.run_check(
            ".built {\n}\n.gone {\n}\n", ["<p>x</p>"],
            ignored=["built"])
        self.assertEqual(len(results[0][2]), 1)
        self.assertIn("gone", results[0][2][0].reason)

    def test_problem_as_dict(self):
        results, _ = self.run_check(".gone {\n}\n", ["<p>x</p>"])
        problem = results[0][2][0]
        self.assertEqual(problem.as_dict()["line"], 1)
        self.assertIn("gone", problem.as_dict()["reason"])

    def test_unreadable_css_file(self):
        results, _ = checker.check_files(
            ["/nonexistent-dir-xyz/s.css"], [])
        self.assertEqual(len(results[0][2]), 1)
        self.assertIn("cannot read file", results[0][2][0].reason)

    def test_missing_reference_file_skipped(self):
        results, total = checker.check_files(
            [str(EXAMPLES / "site" / "clean.css")],
            ["/nonexistent-dir-xyz/page.html"])
        self.assertEqual(total, 2)
        self.assertEqual(len(results[0][2]), 2)

    def test_normalise_ignored(self):
        self.assertEqual(
            checker.normalise_ignored([".a", "b", "  ", ".c "]),
            ["a", "b", "c"])


class TestCollection(unittest.TestCase):
    def test_folder_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.css").write_text(".a {\n}\n")
            (root / "b.html").write_text('<div class="a">')
            (root / "c.js").write_text("x();")
            (root / "d.txt").write_text(".a")
            (root / "sub").mkdir()
            (root / "sub" / "e.css").write_text(".e {\n}\n")
            css, refs, missing = checker.collect([str(root)])
            self.assertEqual(missing, [])
            self.assertEqual(css, [str(root / "a.css"),
                                   str(root / "sub" / "e.css")])
            self.assertEqual(refs, [str(root / "b.html"),
                                    str(root / "c.js")])

    def test_git_and_node_modules_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "g.css").write_text(".g {\n}\n")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "n.css").write_text(".n {\n}\n")
            (root / "a.css").write_text(".a {\n}\n")
            css, _, _ = checker.collect([str(root)])
            self.assertEqual(css, [str(root / "a.css")])

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.css").write_text(".a {\n}\n")
            (root / "sub").mkdir()
            (root / "sub" / "b.css").write_text(".b {\n}\n")
            css, _, _ = checker.collect([str(root)], recursive=False)
            self.assertEqual(css, [str(root / "a.css")])

    def test_exclude_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "vendor-x.css").write_text(".v {\n}\n")
            (root / "main.css").write_text(".m {\n}\n")
            css, _, _ = checker.collect([str(root)],
                                        exclude=["vendor-*"])
            self.assertEqual(css, [str(root / "main.css")])

    def test_direct_css_file_checked_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one.css").write_text(".one {\n}\n")
            (root / "two.css").write_text(".two {\n}\n")
            (root / "page.html").write_text('<div class="one two">')
            css, refs, _ = checker.collect([str(root / "one.css")])
            self.assertEqual(css, [str(root / "one.css")])
            self.assertEqual(refs, [str(root / "page.html")])

    def test_direct_reference_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "page.html").write_text("hi")
            css, refs, _ = checker.collect([str(root / "page.html")])
            self.assertEqual(css, [])
            self.assertEqual(refs, [str(root / "page.html")])

    def test_missing_path_reported(self):
        css, refs, missing = checker.collect(["/no-such-path-xyz"])
        self.assertEqual(css, [])
        self.assertEqual(refs, [])
        self.assertEqual(missing, ["/no-such-path-xyz"])

    def test_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            css, refs, _ = checker.collect([tmp])
            self.assertEqual(css, [])
            self.assertEqual(refs, [])

    def test_uppercase_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "UP.CSS").write_text(".a {\n}\n")
            css, _, _ = checker.collect([str(root)])
            self.assertEqual(css, [str(root / "UP.CSS")])

    def test_reference_suffixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ["a.html", "b.htm", "c.js", "d.jsx",
                         "e.ts", "f.tsx", "g.vue"]:
                (root / name).write_text("x")
            _, refs, _ = checker.collect([str(root)])
            self.assertEqual(len(refs), 6)
            self.assertNotIn(str(root / "g.vue"), refs)


class TestCLI(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SRC), *args],
            capture_output=True, text=True, cwd=ROOT,
        )

    def test_clean_file_exit_0(self):
        result = self.run_cli("examples/site/clean.css")
        self.assertEqual(result.returncode, 0)
        self.assertIn("all 2 class(es) used", result.stdout)
        self.assertIn("none unused", result.stdout)

    def test_bad_file_exit_1(self):
        result = self.run_cli("examples/site/styles.css")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL examples/site/styles.css:18:", result.stdout)

    def test_folder_exit_1_and_summary(self):
        result = self.run_cli("examples/site")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Checked 2 CSS file(s) (13 class(es)), "
                      "4 problem(s) in 1 file(s).", result.stdout)

    def test_no_args_exit_2(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)

    def test_missing_path_exit_2(self):
        result = self.run_cli("no-such-file.css")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no such file or folder", result.stderr)

    def test_folder_without_css_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "page.html").write_text("hi")
            result = self.run_cli(tmp)
        self.assertEqual(result.returncode, 2)
        self.assertIn("no CSS files found", result.stderr)

    def test_bad_flag_exit_2(self):
        result = self.run_cli("--nope", "examples/site")
        self.assertEqual(result.returncode, 2)

    def test_ignore_flag(self):
        result = self.run_cli("--ignore", "unused-banner",
                              "examples/site/styles.css")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("unused-banner", result.stdout)
        self.assertIn("3 problem(s)", result.stdout)

    def test_ignore_with_dot(self):
        result = self.run_cli("--ignore", ".unused-banner",
                              "examples/site/styles.css")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("unused-banner", result.stdout)

    def test_exclude_flag(self):
        result = self.run_cli("--exclude", "styles.css",
                              "examples/site")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("styles.css", result.stdout)

    def test_json_output(self):
        result = self.run_cli("--json", "examples/site/styles.css")
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["problems"], 4)
        self.assertEqual(payload["summary"]["classes"], 11)
        self.assertEqual(payload["files"][0]["file"],
                         "examples/site/styles.css")
        self.assertEqual(payload["files"][0]["problems"][0]["line"], 18)
        self.assertIn("Checked 1 CSS file(s)", result.stderr)

    def test_json_clean(self):
        result = self.run_cli("--json", "examples/site/clean.css")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["problems"], 0)

    def test_version(self):
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("1.0.0", result.stdout)


class TestExamples(unittest.TestCase):
    def test_styles_expected_problems(self):
        text = (EXAMPLES / "site" / "styles.css").read_text()
        refs = [str(EXAMPLES / "site" / "index.html"),
                str(EXAMPLES / "site" / "app.js"),
                str(EXAMPLES / "site" / "App.jsx")]
        results, total = checker.check_files(
            [str(EXAMPLES / "site" / "styles.css")], refs)
        self.assertEqual(total, 11)
        got = [(p.line, p.reason.split(" ")[2])
               for p in results[0][2]]
        self.assertEqual(got, [(18, "'.title'"), (21, "'.unused-banner'"),
                               (24, "'.unused-footer'"),
                               (28, "'.sidebar'")])

    def test_clean_expected_no_problems(self):
        text = (EXAMPLES / "site" / "clean.css").read_text()
        refs = [str(EXAMPLES / "site" / "index.html")]
        results, total = checker.check_files(
            [str(EXAMPLES / "site" / "clean.css")], refs)
        self.assertEqual(total, 2)
        self.assertEqual(results[0][2], [])

    def test_fake_class_in_comment_not_extracted(self):
        text = (EXAMPLES / "site" / "styles.css").read_text()
        names = [d.name for d in checker.extract_classes(
            text, "styles.css")]
        self.assertNotIn("fake-class", names)

    def test_sample_output_matches_fresh_run(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)
        sample = (EXAMPLES / "sample-output.md").read_text()
        block = sample.split("```\n")[1]
        self.assertEqual(result.stdout, block)

    def test_readme_quoted_outputs_are_real(self):
        readme = README.read_text()
        for line in [
            "examples/site/clean.css: OK — all 2 class(es) used",
            "OK — 1 CSS file(s) checked, 2 class(es), none unused.",
            "FAIL examples/site/styles.css:18: unused class '.title'",
            "FAIL examples/site/styles.css:21: unused class '.unused-banner'",
            "FAIL examples/site/styles.css:24: unused class '.unused-footer'",
            "FAIL examples/site/styles.css:28: unused class '.sidebar'",
            "Checked 1 CSS file(s) (11 class(es)), 4 problem(s) in 1 file(s).",
            "Checked 2 CSS file(s) (13 class(es)), 4 problem(s) in 1 file(s).",
        ]:
            self.assertIn(line, readme, line)

    def test_readme_json_matches_real_json(self):
        result = subprocess.run(
            [sys.executable, str(SRC), "--json",
             "examples/site/styles.css"],
            capture_output=True, text=True, cwd=ROOT,
        )
        readme = README.read_text()
        start = readme.index("```\n{\n  \"files\": [")
        end = readme.index("```", start + 10)
        block = readme[start + 4:end].strip()
        self.assertEqual(result.stdout.strip(), block)


class TestHygiene(unittest.TestCase):
    def test_no_placeholder_text(self):
        banned = ["TODO", "FIXME", "XXX", "coming soon", "lorem"]
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="replace")
            for word in banned:
                self.assertNotIn(word, text,
                                 f"{word} in {path.relative_to(ROOT)}")

    def test_no_absolute_paths(self):
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="replace")
            self.assertNotIn("/home/hatch", text,
                             f"absolute path in {path.relative_to(ROOT)}")
            self.assertNotIn("/Users/", text,
                             f"absolute path in {path.relative_to(ROOT)}")
            self.assertNotIn("/tmp/", text,
                             f"absolute path in {path.relative_to(ROOT)}")

    def test_stdlib_only_imports(self):
        allowed_src = {
            "argparse", "fnmatch", "json", "os", "re", "sys", "pathlib",
        }
        allowed_tests = allowed_src | {
            "ast", "json", "subprocess", "tempfile", "unittest",
            "css_class_checker",
        }
        for path, allowed in [(SRC, allowed_src),
                              (Path(__file__), allowed_tests)]:
            tree = ast.parse(path.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imported.add(node.module.split(".")[0])
            self.assertTrue(imported <= allowed,
                            f"{path.name} imports non-stdlib: "
                            f"{imported - allowed}")
            self.assertNotIn("yaml", imported)

    def test_no_yaml_anywhere_in_source(self):
        text = SRC.read_text()
        self.assertNotIn("yaml", text)

    def test_no_secrets_in_repo(self):
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="replace").lower()
            for marker in ["api_key", "api-key", "password =", "secret ="]:
                self.assertNotIn(marker, text,
                                 f"possible secret in {path.relative_to(ROOT)}")

    def test_gitignore_env_first(self):
        lines = (ROOT / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        self.assertIn("test_css_class_checker.py", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)


if __name__ == "__main__":
    unittest.main()
