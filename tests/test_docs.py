"""Consistency checks between the code, the docs, the READMEs and the packaging files."""
import ast
import glob
import json
import os
import re
import unittest

import fakes

MKDOCS = os.path.join(fakes.ROOT, "mkdocs.yml")
PI_FILES = sorted(glob.glob(os.path.join(fakes.PY_DIR, "pingoblin_ads1115", "*.py")))
MP_DRIVER = os.path.join(fakes.MP_DIR, "ads1115.py")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def docs_pages():
    return sorted(glob.glob(os.path.join(fakes.DOCS_DIR, "**", "*.md"), recursive=True))


def examples(folder):
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(folder, "*.py"))
                  if os.path.basename(p) != "ads1115.py")


class TestDocsSite(unittest.TestCase):
    def test_nav_pages_exist_and_every_page_is_in_nav(self):
        nav = read(MKDOCS)
        pages = re.findall(r"^\s*-\s+(?:[^:\n]+:\s+)?(\S+\.md)\s*$", nav, re.M)
        self.assertGreater(len(pages), 10)
        for page in pages:
            self.assertTrue(os.path.exists(os.path.join(fakes.DOCS_DIR, page)), page)
        for path in docs_pages():
            page = os.path.relpath(path, fakes.DOCS_DIR).replace(os.sep, "/")
            self.assertIn(page, nav)

    def test_snippet_includes_exist(self):
        for path in docs_pages():
            for include in re.findall(r'--8<-- "([^"]+)"', read(path)):
                with self.subTest(page=os.path.basename(path), include=include):
                    self.assertTrue(os.path.exists(os.path.join(fakes.ROOT, include)))

    def test_every_example_is_documented(self):
        for folder, page in ((fakes.PY_DIR, "examples-python.md"), (fakes.MP_DIR, "examples-micropython.md")):
            text = read(os.path.join(fakes.DOCS_DIR, "api", page))
            readme = read(os.path.join(folder, "README.md"))
            for script in examples(folder):
                with self.subTest(script=script):
                    self.assertIn('--8<-- "%s/%s"' % (os.path.basename(folder), script), text)
                    self.assertIn("`%s`" % script, readme)

    def test_removed_hardware_is_not_mentioned(self):
        """Rev G has no Qwiic connectors (J6/J7) and no power LED (D1/R12)."""
        files = docs_pages() + [os.path.join(fakes.ROOT, "README.md"), os.path.join(fakes.PY_DIR, "README.md"),
                                os.path.join(fakes.MP_DIR, "README.md")] + PI_FILES + [MP_DRIVER]
        files += [os.path.join(fakes.PY_DIR, s) for s in examples(fakes.PY_DIR)]
        files += [os.path.join(fakes.MP_DIR, s) for s in examples(fakes.MP_DIR)]
        pattern = re.compile(r"qwiic|stemma|\bJ6\b|\bJ7\b|\bD1\b|\bR12\b|PWR", re.I)
        for path in files:
            with self.subTest(file=os.path.relpath(path, fakes.ROOT)):
                self.assertEqual(pattern.findall(read(path)), [])

    def test_published_limits(self):
        spec = read(os.path.join(fakes.DOCS_DIR, "user-guide", "specifications.md"))
        self.assertIn("| VDD | −0.3 V to 5.5 V |", spec)
        self.assertIn("| Voltage on SDA, SCL and RDY | −0.3 V to 5.5 V |", spec)
        self.assertIn("−15 V to +15 V", spec)
        self.assertNotIn("24 V", spec)

    def test_micropython_examples_default_to_100_khz(self):
        for path in [MP_DRIVER] + [os.path.join(fakes.MP_DIR, s) for s in examples(fakes.MP_DIR)] + \
                [os.path.join(fakes.MP_DIR, "README.md"), os.path.join(fakes.DOCS_DIR, "api", "index.md")]:
            with self.subTest(file=os.path.basename(path)):
                self.assertNotIn("freq=400_000)", read(path))


def prose(path):
    """A page's text without code blocks, inline code, link targets, URLs or HTML."""
    text = read(path)
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"^:::.*(?:\n[ \t]+.*)*", "", text, flags=re.M)    # mkdocstrings directives
    text = re.sub(r"`[^`]*`", "Code", text)
    text = re.sub(r"\]\([^)]*\)", "]", text)
    text = re.sub(r"\]\[[^\]]*\]", "]", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text


class TestDocumentationStyle(unittest.TestCase):
    """The rules in "Documentation and API documentation preferences" that a test can check."""

    FILES = docs_pages() + [os.path.join(fakes.ROOT, "README.md"), os.path.join(fakes.PY_DIR, "README.md"),
                            os.path.join(fakes.MP_DIR, "README.md")]

    def check(self, pattern, flags=re.I, files=None):
        for path in files or self.FILES:
            with self.subTest(file=os.path.relpath(path, fakes.ROOT)):
                self.assertEqual(re.findall(pattern, prose(path), flags), [])

    def test_no_contractions(self):
        self.check(r"\b\w+n't\b|\b(?:it|that|there|you|we|they|what)'(?:s|re|ll|ve|d)\b")

    def test_no_filler(self):
        self.check(r"\b(?:note that|simply|in order to|as described above|please|it is worth noting)\b")

    def test_definitive_figures(self):
        self.check(r"\b(?:about|roughly|approximately|around|circa)\s+[−\-±~]?\d")

    def test_australian_spelling(self):
        self.check(r"\b(?:colou?r(?<!colour)|behavior|center|centered|favorite|aluminum|analog|grey(?!x))\b"
                   r"|\bcolor\b|\bbehavior\b", flags=0)

    def test_ticks_and_crosses_not_yes_and_no(self):
        self.check(r"\|\s*(?:Yes|No)\s*\|", flags=0)

    def test_space_between_number_and_unit(self):
        self.check(r"(?<![\w.])\d+(?:\.\d+)?(?:mA|µA|mV|µV|kΩ|MΩ|Ω|°C|kHz|MHz|mW|mm)\b", flags=0)

    def test_en_dash_for_numeric_ranges(self):
        self.check(r"(?<![\w.x])\d+(?:\.\d+)?-\d+(?:\.\d+)?\s?(?:V|mA|µA|kΩ|Ω|°C|kHz|mm|%|samples)\b", flags=0)

    def test_capital_after_colon(self):
        self.check(r"(?<![\w`])[A-Za-z][^:\n|]*?:\s+[a-z]\w", flags=0)

    def test_no_retailers(self):
        self.check(r"\b(?:Jaycar|Core Electronics|Adafruit|SparkFun|Digi-?Key|Mouser|LCSC|Amazon|eBay|AliExpress|Element14)\b")

    def test_customer_pages_have_no_development_notes(self):
        self.check(r"\b(?:CI|test suite|unit tests?|not yet|GitHub Actions|off-target|mock pins)\b",
                   flags=0, files=docs_pages())

    def test_product_name(self):
        for path in [os.path.join(fakes.DOCS_DIR, "index.md"), os.path.join(fakes.DOCS_DIR, "user-guide", "index.md"),
                     os.path.join(fakes.DOCS_DIR, "api", "index.md"), os.path.join(fakes.ROOT, "README.md")]:
            with self.subTest(file=os.path.relpath(path, fakes.ROOT)):
                self.assertIn("PinGoblin ADS1115", read(path).split("\n\n", 2)[0] + read(path).split("\n\n", 2)[1])
        self.check(r"\bbreakout\b", files=docs_pages())

    def test_troubleshooting_is_a_symptom_cause_fix_table(self):
        page = read(os.path.join(fakes.DOCS_DIR, "user-guide", "troubleshooting.md"))
        self.assertIn("| Symptom | Likely cause | Fix |", page)

    def test_host_connections_are_marked_required_or_optional(self):
        for page in ("board-layout.md", "quick-start.md"):
            text = read(os.path.join(fakes.DOCS_DIR, "user-guide", page))
            rows = [r for r in text.splitlines() if re.match(r"\| \d (?:\| )?(?:VDD|GND|SCL|SDA|RDY)", r)]
            with self.subTest(page=page):
                self.assertGreaterEqual(len(rows), 5)
                for row in rows:
                    self.assertRegex(row, r"\((?:Required|Optional)\)")

    def test_damaging_actions_have_danger_boxes_and_safety_rules(self):
        spec = read(os.path.join(fakes.DOCS_DIR, "user-guide", "specifications.md"))
        for rule in ("Never connect the board to mains", "Never power the board from 5 V", "Never swap VDD and GND",
                     "Never connect a supply to VDD on a sensor header", "Never put more than 5.5 V on VDD"):
            with self.subTest(rule=rule):
                self.assertIn("**" + rule, spec)
        layout = read(os.path.join(fakes.DOCS_DIR, "user-guide", "board-layout.md"))
        self.assertGreaterEqual(layout.count("!!! danger"), 3)

    def test_unverified_figures_are_marked(self):
        spec = read(os.path.join(fakes.DOCS_DIR, "user-guide", "specifications.md"))
        self.assertIn("−15 V to +15 V (final figure after prototype testing)", spec)


class TestDocstrings(unittest.TestCase):
    """Every public function and class documents each of its parameters (the API pages need it)."""

    def check(self, path):
        tree = ast.parse(read(path))
        self.assertTrue(ast.get_docstring(tree), "module docstring")
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.ClassDef)) or node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node) or ""
            with self.subTest(name=node.name):
                self.assertTrue(doc, "missing docstring")
            if isinstance(node, ast.ClassDef):
                init = next((n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"), None)
                names = [a.arg for a in init.args.args[1:]] if init else []
            else:
                names = [a.arg for a in node.args.args if a.arg != "self"]
                if node.args.kwarg:
                    names.append("**" + node.args.kwarg.arg)
            for name in names:
                with self.subTest(name=node.name, arg=name):
                    self.assertRegex(doc, r"\n\s+%s( \([^)]*\))?: " % re.escape(name))

    def test_pi_package(self):
        for path in PI_FILES:
            with self.subTest(file=os.path.basename(path)):
                self.check(path)

    def test_micropython_module(self):
        self.check(MP_DRIVER)


class TestMicroPythonCompatibility(unittest.TestCase):
    ALLOWED = {"machine", "time", "math", "sys", "ads1115", "micropython"}

    def test_only_micropython_modules_are_imported(self):
        for path in glob.glob(os.path.join(fakes.MP_DIR, "*.py")):
            for node in ast.walk(ast.parse(read(path))):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module] if isinstance(node, ast.ImportFrom) else []
                for name in names:
                    with self.subTest(file=os.path.basename(path), module=name):
                        self.assertIn(name.split(".")[0], self.ALLOWED)

    def test_driver_uses_no_fstrings(self):
        tree = ast.parse(read(MP_DRIVER))
        self.assertFalse([n for n in ast.walk(tree) if isinstance(n, ast.JoinedStr)])


class TestPackaging(unittest.TestCase):
    def test_mip_package(self):
        package = json.loads(read(os.path.join(fakes.MP_DIR, "package.json")))
        pyproject = read(os.path.join(fakes.PY_DIR, "pyproject.toml"))
        self.assertEqual(package["version"], re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1))
        for target, source in package["urls"]:
            with self.subTest(target=target):
                self.assertTrue(source.startswith("github:PinGoblin/ADS1115/"))
                self.assertTrue(os.path.exists(os.path.join(fakes.ROOT, source.split("ADS1115/", 1)[1])))

    def test_pyproject_lists_the_package(self):
        pyproject = read(os.path.join(fakes.PY_DIR, "pyproject.toml"))
        self.assertIn('packages = ["pingoblin_ads1115"]', pyproject)
        self.assertIn("smbus2", pyproject)


if __name__ == "__main__":
    unittest.main()
