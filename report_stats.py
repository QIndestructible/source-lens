# -*- coding: utf-8 -*-
"""把 data/evidence 里的 400 条真实结果重新算一遍，输出 data/real_stats.md。

这就是文章里所有数字的来源。改了阈值或算法，跑一遍就能看到变化。
"""

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import core  # noqa: E402

EVID = HERE / "data" / "evidence"
OUT = HERE / "data" / "real_stats.md"
POLICY = {"Q04", "Q08", "Q09", "Q10", "Q11", "Q12", "Q13", "Q14", "Q17", "Q18", "Q19"}

rows, dom = [], Counter()
tot_n = tot_c = tot_multi = 0
gov = 0
today = date.today()

for p in sorted(EVID.glob("Q*.json")):
    ev = json.loads(p.read_text(encoding="utf-8"))
    docs = [core.Doc(**d) for d in ev["docs"]]
    groups = core.cluster(docs)
    n, c = len(docs), len(groups)
    multi = sum(1 for g in groups if len(g) > 1)

    tot_n += n
    tot_c += c
    tot_multi += multi
    gov += sum(1 for d in docs if "gov.cn" in (d.url or ""))
    for d in docs:
        dom[core.domain_of(d)] += 1

    chains = []
    for g in groups:
        if len(g) > 1:
            ds = [x[1] if isinstance(x, tuple) else x for x in g]
            domains = []
            for d in ds:
                dn = core.domain_of(d)
                if dn and dn not in domains:
                    domains.append(dn)
            chains.append({"size": len(ds), "domains": domains,
                           "title": max(ds, key=lambda d: d.score).title})
    chains.sort(key=lambda x: x["size"], reverse=True)

    rows.append({"id": ev["id"], "query": ev["query"], "n": n, "c": c,
                 "dup": n - c, "density": c / n if n else 0,
                 "multi": multi, "chains": chains,
                 "policy": ev["id"] in POLICY})

overall = tot_c / tot_n
top3 = dom.most_common(3)
top3_n = sum(v for _, v in top3)

L = ["# 20 题真实检索质量统计", "",
     f"- 题目：{len(rows)} 道；结果：{tot_n} 条",
     f"- 独立信源：{tot_c} 个；密度：**{overall:.1%}**",
     f"- 疑似重复：{tot_n - tot_c} 条（{1 - overall:.1%}）",
     f"- 含转载的簇：{tot_multi} 个；平均 {tot_multi and (tot_n - tot_c + tot_multi) / tot_multi:.2f} 条/簇",
     f"- 前三大平台：{top3_n}/{tot_n}（{top3_n / tot_n:.1%}）——"
     + "、".join(f"{d} {v}" for d, v in top3),
     f"- gov.cn 域名：{gov} 条（{gov / tot_n:.1%}）", "",
     "| 题号 | 主题 | 条数 | 独立信源 | 密度 | 含转载簇 |",
     "| --- | --- | --- | --- | --- | --- |"]
for r in rows:
    L.append(f"| {r['id']} | {r['query']} | {r['n']} | {r['c']} | {r['density']:.0%} | {r['multi']} |")

pol = [r for r in rows if r["policy"]]
tec = [r for r in rows if not r["policy"]]
for name, g in (("政策类", pol), ("技术/发布类", tec)):
    n = sum(r["n"] for r in g)
    c = sum(r["c"] for r in g)
    L.append(f"\n{name}：{len(g)} 题 / {n} 条 / {c} 个信源，密度 {c / n:.1%}，"
             f"重复 {n - c} 条（{1 - c / n:.1%}）")

L += ["", "## 转载明细", ""]
for r in rows:
    if not r["chains"]:
        continue
    L.append(f"### {r['id']} {r['query']}")
    for ch in r["chains"]:
        L.append(f"- {ch['size']} 条 / {len(ch['domains'])} 个域名：{ch['title']}（{'、'.join(ch['domains'][:6])}）")
    L.append("")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(L), encoding="utf-8")

print(f"{tot_n} 条 / {tot_c} 信源 / 密度 {overall:.1%} / 重复 {tot_n - tot_c} 条 "
      f"/ 前三平台 {top3_n / tot_n:.1%}")
print(f"[ok] -> {OUT}")
