"""Fill template.html from numbers.json and verdict.json, then print it to PDF with headless Chrome."""
import json, os, re, subprocess, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
n = json.load(open(os.path.join(HERE, "numbers.json")))
v = json.load(open(os.path.join(HERE, "verdict.json")))
t = n["tool"]
pct = lambda x: f"{100 * x:.1f}".removesuffix(".0")
values = {
    "date": datetime.date.today().strftime("%d %B %Y"),
    "laya_auc_sib": f"{n['pooled']['laya']['sibling']:.2f}",
    "oj_auc_sib": f"{n['pooled']['openjev']['sibling']:.2f}",
    "laya_top1": pct(t["laya"]["top1"]), "laya_top3": pct(t["laya"]["top3"]),
    "bm25_top1": pct(t["bm25"]["top1"]), "bm25_top3": pct(t["bm25"]["top3"]),
    "oj_top1": pct(t["openjev"]["top1"]), "oj_top3": pct(t["openjev"]["top3"]),
    "oj_secs": f"{t['openjev']['seconds_median']:.0f}",
    "laya_own": pct(t["laya"]["own_top1"]), "oj_own": pct(t["openjev"]["own_top1"]),
    "rand_own": pct(t["random"]["own_top1"]),
    "schema_all": f"{t['openjev']['schema_bytes_all20'] / 1000:.1f}",
    "schema_top3": f"{t['openjev']['schema_bytes_top3'] / 1000:.1f}",
    "prompt_cut": f"{100 * (1 - t['openjev']['schema_bytes_top3'] / t['openjev']['schema_bytes_all20']):.0f}",
    **v,
}
html = open(os.path.join(HERE, "template.html")).read()
html = re.sub(r"\{\{(\w+)\}\}", lambda m: str(values[m.group(1)]), html)
out_html = os.path.join(HERE, "report.html")
open(out_html, "w").write(html)
pdf = os.path.join(HERE, "Laya_vs_OpenJev_summary.pdf")
subprocess.run(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--headless", "--disable-gpu",
                "--no-pdf-header-footer", f"--print-to-pdf={pdf}", "file://" + out_html],
               check=True, capture_output=True)
print(pdf)
