#!/usr/bin/env python3
"""Regenerates docs/cost-report.md from cost-report.template.md and cost-model.py."""
import importlib.util
import pathlib

here = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("model", here / "cost-model.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

md = m.md()
summary, detail = md.split("\n#### Line items", 1)
detail = "#### Line items" + detail

_, a3n, a3e = m.table("a3")
_, a2n, a2e = m.table("a2")
a3y, a2y = 10 * a3n + 2 * a3e, 10 * a2n + 2 * a2e
bn, be, by = m.region_totals(m.MUMBAI_OVERRIDES)

values = {
    "MODEL": summary.strip(),
    "DETAIL": detail.strip(),
    "SGP_YEAR": f"{a3y:,.0f}", "SGP_MONTH": f"{a3y/12:,.0f}",
    "BOM_YEAR": f"{by:,.0f}", "BOM_MONTH": f"{by/12:,.0f}",
    "A3_N": f"{a3n:,.0f}", "A3_E": f"{a3e:,.0f}",
    "A2_YEAR": f"{a2y:,.0f}",
    "HEADROOM": f"{12000 - a3y:,.0f}",
    "PER_STUDENT": f"{a3y / m.STUDENTS:.2f}",
    "NET": f"{a2y - a3y:,.0f}", "NET_PCT": f"{(a2y - a3y) / a2y * 100:.0f}",
}
text = (here / "cost-report.template.md").read_text()
for k, v in values.items():
    text = text.replace("{{" + k + "}}", v)
assert "{{" not in text, "unfilled placeholder"
(here / "cost-report.md").write_text(text)
print("wrote docs/cost-report.md")
