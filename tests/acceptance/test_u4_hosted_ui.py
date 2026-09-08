"""U4 — the hosted UI's measurable halves.

Reachability, filters, the Git link, the keyboard path and axe are measured in the live
Playwright suite (`ui/e2e/live/`, `pnpm test:e2e:live`), not here. What belongs in a pytest
run is the scale number the browser cannot honestly produce on its own — the API's own first
page over a 10 000-skill catalog — and the criteria that need people.
"""
from __future__ import annotations

import json
import time
import uuid

import pytest

from gf_acceptance_support import PASS, FAIL, NOT_MEASURED, percentile

pytestmark = pytest.mark.acceptance

SYNTHETIC_SKILLS = 10_000


@pytest.mark.slow
@pytest.mark.acc("U4-2")
def test_u4_2_the_first_catalog_page_over_ten_thousand_skills(fresh_org, report, bring_up,
                                                              gf_stack):
    """U4-2: p95 of the first `/skills` page with 10 000 skills in the repository.

    The rows are seeded straight into `gfm.skills` because importing 10 000 real SKILL.md files
    would measure the importer, not the page. They are the same shape the importer writes, and
    the read path is the product's own."""
    w = fresh_org("u4-scale")
    bring_up(w, publish=False)
    seeded_before = len(w.get("/skills?limit=1")["items"])

    gf_stack.sql(f"""
INSERT INTO gfm.skills (org_id, skill_id, repo_id, name, description, scope, owner, path,
                        source_layer, knowledge_layer, source_status, publication_status)
SELECT '{w.org_id}'::uuid,
       'urn:skill:acceptance:scale.s' || (n / 100) || ':skill-' || n,
       '{w.repo}',
       'scale-skill-' || n,
       '[scale.s' || (n / 100) || '] A synthetic catalog row written for the U4-2 scale '
         || 'measurement. Use when measuring the first catalog page. Do not use for anything else.',
       'scale.s' || (n / 100),
       'scale-team',
       'services/scale/s' || (n / 100) || '/skill-' || n || '/SKILL.md',
       'team', 'unclassified', 'active', 'draft'
FROM generate_series(1, {SYNTHETIC_SKILLS}) AS n
ON CONFLICT DO NOTHING""")
    total = int(gf_stack.sql(
        f"SELECT count(*) FROM gfm.skills WHERE org_id='{w.org_id}'::uuid")[0][0])

    timings, facet_timings = [], []
    for _ in range(30):
        start = time.monotonic()
        page = w.get("/skills?limit=50")
        timings.append((time.monotonic() - start) * 1000.0)
        start = time.monotonic()
        w.get("/skills/facets?field=scope")
        facet_timings.append((time.monotonic() - start) * 1000.0)

    p95 = percentile(timings, 95)
    facet_p95 = percentile(facet_timings, 95)
    ok = p95 <= 2000 and len(page["items"]) == 50 and total >= SYNTHETIC_SKILLS

    report.record("U4-2", prd_ac="U4 AC2 (first page p95 <= 2 s at 10 000 skills)",
                  scenario="10 000 synthetic catalog rows in one repository; 30 reads of the first "
                           "`/skills` page and of the facet endpoint the Library renders with it",
                  command_or_endpoint="GET {repo_base}/skills?limit=50; GET {repo_base}/skills/facets",
                  data_origin="27 imported Meridian skills plus 10 000 synthetic rows inserted into "
                              "gfm.skills [synthetic, n=10000]",
                  result=PASS if ok else FAIL,
                  evidence={"skills_in_repository": total,
                            "rows_returned": len(page["items"]),
                            "skills_page": {"n": len(timings),
                                            "p50_ms": round(percentile(timings, 50), 1),
                                            "p95_ms": round(p95, 1),
                                            "max_ms": round(max(timings), 1)},
                            "facets_field": "scope",
                            "facets": {"n": len(facet_timings),
                                       "p50_ms": round(percentile(facet_timings, 50), 1),
                                       "p95_ms": round(facet_p95, 1)},
                            "seeded_before": seeded_before},
                  limitation="Local measurement: API and PostgreSQL on one developer machine over "
                             "loopback, measured at the API rather than in the browser, and the "
                             "rows are synthetic. It is not the pilot network and it does not "
                             "include render time.")
    assert ok, (p95, len(page["items"]), total)


@pytest.mark.acc("U4-2 (pilot network)")
def test_u4_2_on_the_pilot_network_is_not_measured_here(report):
    report.record("U4-2 (pilot network)", prd_ac="U4 AC2 on the pilot's own network",
                  scenario="the same first page, in a real browser, over the design partner's "
                           "network, against a production build and a frozen 10 000-skill dataset",
                  command_or_endpoint="—", data_origin="—",
                  result=NOT_MEASURED, evidence={},
                  limitation="Needs the pilot deployment and its network. A loopback number on one "
                             "laptop is not a latency claim for anybody else "
                             "(docs/ui/pipeline/07-frontend.md, Budżety).")


@pytest.mark.acc("U4-5")
def test_u4_5_five_real_users_is_not_measured_here(report):
    report.record("U4-5", prd_ac="U4 AC5 Q (4 of 5 people complete the path unaided)",
                  scenario="five people who are not building Guidefold complete import -> review "
                           "-> decision without help, observed",
                  command_or_endpoint="—", data_origin="—",
                  result=NOT_MEASURED, evidence={},
                  limitation="Q-level usability: needs five real participants. Playwright proving "
                             "the path is reachable by keyboard is a different claim "
                             "(eval-evidence-rules).")
