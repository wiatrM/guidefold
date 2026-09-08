"""docs/API-CONTRACT.md is the binding contract (§1: contract before code).

These tests keep the document parseable and keep the implementation from drifting away
from it. They run the same checker CI runs, `tools/contract/check_api_contract.py`, plus
structural assertions the checker itself relies on.

They skip only while nothing exists to compare against: no management OpenAPI file and no
`services/search/internal/` package. Once either exists, a skip would be a false pass.
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC = REPO_ROOT / "docs" / "API-CONTRACT.md"
CHECKER = REPO_ROOT / "tools" / "contract" / "check_api_contract.py"
OPENAPI = REPO_ROOT / "services" / "search" / "openapi" / "management-v1.yaml"
INTERNAL = REPO_ROOT / "services" / "search" / "internal"

REQUIRED_SECTIONS = [
    "Zasada nadrzędna",
    "Tożsamość i autoryzacja",
    "Koperta odpowiedzi",
    "Kody błędów",
    "Endpointy",
    "Schematy DTO",
    "Maszyny stanów",
    "Schemat bazy",
    "Kontrakt API–worker",
    "Inwarianty i testy obowiązkowe",
    "Wersjonowanie",
    "Changelog",
]


def _checker():
    """Import the checker as a module so the tests can reuse its parsers."""
    sys.path.insert(0, str(CHECKER.parent))
    try:
        import check_api_contract  # noqa: PLC0415

        return check_api_contract
    finally:
        sys.path.pop(0)


def _nothing_to_compare():
    return not OPENAPI.exists() and not any(INTERNAL.glob("*/*.go"))


skip_unless_comparable = pytest.mark.skipif(
    _nothing_to_compare(),
    reason="neither services/search/openapi/management-v1.yaml nor services/search/internal/**.go "
    "exists yet, so there is nothing to compare the contract against",
)


def test_contract_document_exists():
    assert DOC.exists(), "docs/API-CONTRACT.md is required by .agents/skills/api-contract"


def test_document_declares_version_and_sections():
    text = DOC.read_text(encoding="utf-8")
    doc = _checker().parse_doc(str(DOC))
    assert doc.contract_version, "the document must state contract_version: x.y.z"
    for section in REQUIRED_SECTIONS:
        assert section in text, f"missing section: {section}"
    # The changelog must mention the declared version.
    assert doc.contract_version in text.split("## 11.")[-1], (
        "the changelog must carry a row for the declared contract_version"
    )


def test_document_parses_into_endpoints_tables_and_error_codes():
    doc = _checker().parse_doc(str(DOC))
    assert len(doc.endpoints) >= 50, f"only {len(doc.endpoints)} endpoint rows parsed"
    assert all(p.startswith("/") for _, p in doc.endpoints), "an alias was left unexpanded"
    assert {"/v1/search", "/v1/use"} <= {p for _, p in doc.endpoints}
    assert len(doc.error_codes) >= 40, f"only {len(doc.error_codes)} error codes parsed"
    assert "gfm.jobs" in doc.tables and "gf.skills" in doc.tables
    assert {"org_id", "job_id", "generation", "lease_until"} <= doc.tables["gfm.jobs"]


def test_endpoint_rows_carry_one_method_each():
    """`GET/POST` in a single row would silently hide half the surface from the checker."""
    checker = _checker()
    for line in DOC.read_text(encoding="utf-8").splitlines():
        cells = checker._cells(line)
        if not cells or len(cells) < 2:
            continue
        first = checker._bare(cells[0])
        if any(first.startswith(m) for m in checker.METHODS):
            assert first in checker.METHODS, f"one method per row, got {first!r}"


@skip_unless_comparable
def test_no_contract_drift():
    args = [sys.executable, str(CHECKER)]
    if not OPENAPI.exists():
        args.append("--allow-missing-openapi")
    result = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)
    assert result.returncode == 0, (
        "docs/API-CONTRACT.md and the implementation disagree; the contract is the source "
        "of truth, so update it in the same change as the code.\n" + result.stdout + result.stderr
    )
