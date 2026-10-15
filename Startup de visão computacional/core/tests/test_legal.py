import importlib.util
import json
import re

from django.conf import settings
from django.test import SimpleTestCase

from core.tests.test_api import show

ROOT = settings.BASE_DIR


def load_tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LEGAL = load_tool("build_legal")
REGISTRY = LEGAL.registry()
LICENCE_WORDS = ["CC0", "CC[ -]BY", "Creative " + "Commons", "domínio " + "público", "[Pp]ublic[ -]" + "domain", "Open Font " + "License", "MIT " + "License", "Apache[- ]2", "BSD-[0-9]", chr(169), "[(]c[)] 20[0-9]{2}", "[Cc]opy" + "right"]
CREDIT_NAMES = ["Wiki" + "media", "Make" + "rere", "Wilf" + "redor", "US" + "DA"]
LICENCE = re.compile("|".join(LICENCE_WORDS))
MENTION = re.compile("|".join(LICENCE_WORDS + CREDIT_NAMES))
TEXT_TYPES = {".py", ".js", ".mjs", ".vue", ".css", ".html", ".json", ".md", ".vtt", ".ps1", ".txt", ".webmanifest", ".toml", ".cfg"}
SKIPPED_FOLDERS = ("legal", "deliverables", "docs/reports", "docs/plans", "models", "datasets", "legacy", "var", "frontend/node_modules", "frontend/dist", "analytics/demo_output", ".git", "data/processed")
LEGAL_CODE = {"LICENSES.md", "tools/build_legal.py", "tools/fetch_media.py", "core/tests/test_legal.py", "frontend/package-lock.json"}


def scanned_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_TYPES or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel in LEGAL_CODE or rel.startswith(tuple(f"{folder}/" for folder in SKIPPED_FOLDERS)):
            continue
        if rel.startswith("data/") and not (rel == "data/label_map.json" or rel.endswith("/SOURCE.md")):
            continue
        yield rel, path


class LegalPlaceTests(SimpleTestCase):
    def test_generated_documents_match_the_registry(self):
        stale = [path.relative_to(ROOT).as_posix() for path, text in LEGAL.outputs().items() if not path.exists() or path.read_bytes() != text.encode("utf-8")]
        document = (ROOT / "LICENSES.md").read_text(encoding="utf-8")
        show(f"LICENSES.md: {len(document.splitlines())} lines; legal/site.json: {(ROOT / 'legal' / 'site.json').stat().st_size} B; out of date: {stale}")
        self.assertEqual(stale, [])
        for section in ("## 1. Material próprio", "## 2. Fotos e vídeos de terceiros", "## 3. Conjuntos de dados", "## 4. Tipografia", "## 5. Software de código aberto", "## 6. Regras", "## 7. Como manter"):
            self.assertIn(section, document)

    def test_every_entry_is_complete_and_its_licence_is_allowed(self):
        media = LEGAL.media()
        for entry in media:
            with self.subTest(media=entry["id"]):
                self.assertTrue(LEGAL.allowed_media(entry["license"]), entry["license"])
                for field in ("title", "author", "credit_name", "license_url", "source_url", "file_url", "retrieved", "attribution", "modifications", "used_in", "files"):
                    self.assertTrue(entry[field], field)
                self.assertEqual(entry["attribution"], LEGAL.attribution(entry["original_title"], entry["credit_name"], entry["author"], entry["license"], entry["source_url"]))
        for entry in REGISTRY["datasets"]:
            with self.subTest(dataset=entry["id"]):
                self.assertIn(entry["license"], REGISTRY["policy"]["datasets"])
                for field in ("title", "authors", "page", "license_url", "license_as_written", "commercial_use", "attribution", "citation", "use", "modifications"):
                    self.assertTrue(entry[field], field)
        for entry in REGISTRY["fonts"]:
            with self.subTest(font=entry["id"]):
                text = (ROOT / entry["text"]).read_text(encoding="utf-8")
                self.assertIn("SIL OPEN FONT LICENSE", text)
                self.assertIn(entry["title"].split()[0], text)
        for entry in REGISTRY["own"]:
            for field in ("id", "title", "license", "source", "note"):
                self.assertTrue(entry[field], (entry.get("id"), field))
        ids = [e["id"] for section in ("own", "media", "datasets", "fonts") for e in REGISTRY[section]]
        show(f"registry: {len(REGISTRY['own'])} own items, {len(media)} third-party media, {len(REGISTRY['datasets'])} datasets ({len(REGISTRY['datasets_not_used'])} rejected), {len(REGISTRY['fonts'])} fonts, {len(REGISTRY['software'])} software packages")
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_dependency_has_a_software_entry(self):
        deps = LEGAL.dependencies()
        missing = LEGAL.missing_software()
        show(f"dependencies: {len(deps['python'])} in requirements.txt, {len(deps['npm'])} in package.json; without an entry in the registry: {missing}")
        self.assertEqual(missing, [])
        for entry in REGISTRY["software"]:
            self.assertTrue(entry["license"] and entry["url"].startswith("https://") and entry["role"], entry["name"])

    def test_usage_points_only_to_registered_items(self):
        usage = LEGAL.usage()
        known = {e["id"] for section in ("own", "media") for e in REGISTRY[section]}
        show(f"usage entries {len(usage)}; published files listed {len(LEGAL.published())}")
        self.assertEqual(sorted(set(usage) - known), [])

    def test_no_licence_or_credit_text_lives_outside_the_legal_place(self):
        hits, files = {}, 0
        for rel, path in scanned_files():
            files += 1
            pattern = LICENCE if rel.startswith("docs/") else MENTION
            found = sorted(set(m.group(0) for m in pattern.finditer(path.read_text(encoding="utf-8", errors="ignore"))))
            if found:
                hits[rel] = found
        for rel, found in sorted(hits.items()):
            show(f"mention outside legal/: {rel}: {found}")
        show(f"{files} text files scanned (code, interface, documents, data cards, captions); files with a licence, credit or rights mention outside LICENSES.md and legal/: {len(hits)}")
        self.assertGreater(files, 150)
        self.assertEqual(hits, {})

    def test_old_scattered_files_are_gone(self):
        old = ["frontend/src/licenses.json", "frontend/src/fonts/OFL-fraunces.txt", "assets/brand/fonts/OFL-fraunces.txt", "assets/brand/fonts/OFL-inter.txt", "assets/brand/fonts/OFL-jetbrainsmono.txt"]
        left = [name for name in old if (ROOT / name).exists()]
        media = json.loads((ROOT / "frontend" / "src" / "media.json").read_text(encoding="utf-8"))["items"]
        with_credit = sorted(k for k, v in media.items() if "credit" in v)
        sources = json.loads((ROOT / "assets" / "media_src" / "sources.json").read_text(encoding="utf-8"))
        licence_keys = sorted({k for v in sources.values() for k in v if k in ("license", "author", "license_url", "credit")})
        show(f"old licence files still present: {left}; media items carrying a credit string: {with_credit}; licence keys in the media manifest: {licence_keys}")
        self.assertEqual((left, with_credit, licence_keys), ([], [], []))
