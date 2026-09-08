"""tests/test_portal.py -- the developer portal under portal/ has two renderers over one set of
Markdown files: Mintlify (portal/content/docs.json) and the self-hosted MkDocs build (portal/mkdocs.yml,
portal/Dockerfile). These checks keep the two navigations and the files in step, and hold the
writing to the plain-language rules the pages were written under (no em or en dashes, straight
quotes, sentence-case headings).
"""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PORTAL = ROOT / "portal" / "content"          # Mintlify root; mkdocs.yml sits one level up
MKDOCS = ROOT / "portal" / "mkdocs.yml"


def _mintlify_pages():
    cfg = json.loads((PORTAL / "docs.json").read_text(encoding="utf-8"))
    return [p for g in cfg["navigation"]["groups"] for p in g["pages"]]


def _mkdocs_pages():
    class _Loader(yaml.SafeLoader):
        pass
    _Loader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda loader, suffix, node: suffix)
    cfg = yaml.load(MKDOCS.read_text(encoding="utf-8"), Loader=_Loader)
    out = []
    for section in cfg["nav"]:
        for _title, entries in section.items():
            for entry in entries:
                out.extend(v for v in entry.values())
    return [p[:-3] for p in out]


def test_both_navigations_list_the_same_pages_in_the_same_order():
    assert _mintlify_pages() == _mkdocs_pages()


def test_every_navigation_page_exists_and_every_page_is_in_the_navigation():
    listed = set(_mintlify_pages())
    on_disk = {p.stem for p in PORTAL.glob("*.md") if p.name != "README.md"}
    assert listed == on_disk, (listed ^ on_disk)


def test_every_page_has_a_title_and_a_description():
    for page in _mintlify_pages():
        text = (PORTAL / f"{page}.md").read_text(encoding="utf-8")
        assert text.startswith("---\n"), page
        front = text.split("\n---\n", 1)[0]
        assert "\ntitle:" in front and "\ndescription:" in front, page


def test_pages_keep_to_the_plain_language_rules():
    for page in _mintlify_pages():
        raw = (PORTAL / f"{page}.md").read_text(encoding="utf-8")
        # Fenced blocks quote program output and config verbatim (the hook prints an em dash);
        # the rule is about the prose.
        text = re.sub(r"(?s)```.*?```", "", raw)
        assert "—" not in text and "–" not in text, f"{page}: em/en dash"
        assert "“" not in text and "”" not in text, f"{page}: curly quotes"
        for heading in re.findall(r"(?m)^#{2,3} (.+)$", text):
            words = heading.split()
            if re.fullmatch(r"\d+\.", words[0]):      # "1. Describe the tree": the step number is not a word
                words = words[1:]
            capitalised = [w for w in words[1:] if w[:1].isupper() and not w.isupper() and w not in ("Guidefold", "Mermaid", "Markdown", "MkDocs", "Mintlify", "Helm", "ArgoCD", "Kubernetes", "Python", "Claude", "Copilot", "Codex", "Gemini", "GitHub", "Postgres", "OpenRouter", "Material", "Mintlify's")]
            assert not capitalised, f"{page}: title-case heading {heading!r}"


def test_internal_links_point_at_real_pages():
    pages = set(_mintlify_pages())
    for page in pages:
        text = (PORTAL / f"{page}.md").read_text(encoding="utf-8")
        for target in re.findall(r"\]\(/([a-z0-9-]+)\)", text):
            assert target in pages, f"{page} links to /{target}"


def test_the_docker_build_and_the_chart_agree_on_the_port():
    dockerfile = (ROOT / "portal" / "Dockerfile").read_text(encoding="utf-8")
    template = (ROOT / "deploy/k8s/chart/templates/portal.yaml").read_text(encoding="utf-8")
    assert "EXPOSE 8080" in dockerfile and "containerPort: 8080" in template
    values = yaml.safe_load((ROOT / "deploy/k8s/chart/values.yaml").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "deploy/k8s/chart/values.schema.json").read_text(encoding="utf-8"))
    assert values["portal"]["enabled"] is False
    assert set(values["portal"]) == set(schema["properties"]["portal"]["properties"])
