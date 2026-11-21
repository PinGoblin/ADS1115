"""Consistency checks between the code, the docs and the READMEs."""
import ast
import glob
import os
import re
import unittest

import fakes

MKDOCS = os.path.join(fakes.ROOT, "mkdocs.yml")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def example_scripts(folder):
    modules = {"breakout_ads.py", "ads1115.py"}
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(folder, "*.py"))
                  if os.path.basename(p) not in modules)


class TestDocsSite(unittest.TestCase):
    def test_nav_pages_exist(self):
        pages = re.findall(r"^\s*-\s+(?:[^:\n]+:\s+)?(\S+\.md)\s*$", read(MKDOCS), re.M)
        self.assertGreater(len(pages), 10)
        for page in pages:
            with self.subTest(page=page):
                self.assertTrue(os.path.exists(os.path.join(fakes.DOCS_DIR, page)))

    def test_every_docs_page_is_in_nav(self):
        nav = read(MKDOCS)
        for path in glob.glob(os.path.join(fakes.DOCS_DIR, "**", "*.md"), recursive=True):
            page = os.path.relpath(path, fakes.DOCS_DIR).replace(os.sep, "/")
            with self.subTest(page=page):
                self.assertIn(page, nav)

    def test_snippet_includes_exist(self):
        for path in glob.glob(os.path.join(fakes.DOCS_DIR, "**", "*.md"), recursive=True):
            for include in re.findall(r'--8<-- "([^"]+)"', read(path)):
                with self.subTest(page=path, include=include):
                    self.assertTrue(os.path.exists(os.path.join(fakes.ROOT, include)))

    def test_every_example_is_on_its_docs_page(self):
        for folder, page in ((fakes.PY_DIR, "examples-python.md"), (fakes.MP_DIR, "examples-micropython.md")):
            text = read(os.path.join(fakes.DOCS_DIR, "api", page))
            for script in example_scripts(folder):
                with self.subTest(script=script):
                    self.assertIn('--8<-- "%s/%s"' % (os.path.basename(folder), script), text)
                    self.assertIn("`%s`" % script, text)        # listed in the summary table

    def test_every_example_is_in_its_readme(self):
        for folder in (fakes.PY_DIR, fakes.MP_DIR):
            readme = read(os.path.join(folder, "README.md"))
            for script in example_scripts(folder):
                with self.subTest(script=script):
                    self.assertIn("`%s`" % script, readme)


class TestDocstrings(unittest.TestCase):
    """Every public function has a docstring that documents each of its parameters."""

    def check_module(self, path):
        tree = ast.parse(read(path))
        self.assertTrue(ast.get_docstring(tree), "module docstring")
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.ClassDef)) or node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node)
            with self.subTest(name=node.name):
                self.assertTrue(doc, "missing docstring")
            if isinstance(node, ast.ClassDef):
                init = next((n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"), None)
                args = init.args.args[1:] if init else []
            else:
                args = [a for a in node.args.args if a.arg != "self"]
            for arg in args:
                with self.subTest(name=node.name, arg=arg.arg):
                    self.assertRegex(doc, r"\n\s+%s( \([^)]*\))?: " % arg.arg)

    def test_breakout_ads(self):
        self.check_module(os.path.join(fakes.PY_DIR, "breakout_ads.py"))

    def test_ads1115(self):
        self.check_module(os.path.join(fakes.MP_DIR, "ads1115.py"))


class TestMicroPythonCompatibility(unittest.TestCase):
    """The MicroPython files must not use CPython-only modules."""

    ALLOWED = {"machine", "time", "math", "ads1115", "micropython"}

    def test_imports(self):
        for path in glob.glob(os.path.join(fakes.MP_DIR, "*.py")):
            tree = ast.parse(read(path))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module]
                for name in names:
                    with self.subTest(file=os.path.basename(path), module=name):
                        self.assertIn(name.split(".")[0], self.ALLOWED)

    def test_no_fstrings_in_module(self):
        # f-strings need MicroPython 1.20+, so the module sticks to % formatting.
        tree = ast.parse(read(os.path.join(fakes.MP_DIR, "ads1115.py")))
        self.assertFalse([n for n in ast.walk(tree) if isinstance(n, ast.JoinedStr)])


if __name__ == "__main__":
    unittest.main()
