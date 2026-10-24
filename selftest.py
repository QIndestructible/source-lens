# -*- coding: utf-8 -*-
"""离线自检：不联网、不花额度，验证判重和分层逻辑没写坏。

    python selftest.py
"""

import sys
from datetime import date

import core


def D(title, url, passage="", score=0.8, authority=0.0, date_s="2026-10-20", site=""):
    return core.Doc(title=title, url=url, passage=passage, score=score,
                    authority=authority, date=date_s, site=site)


LONG = "辽宁省算力券政策正式落地实施，经营主体每年最高可申领二百万元补贴，申报期为三个月，逾期不再受理。"
LONG2 = "辽宁启动实施算力券政策 经营主体每年最高可申领200万元补贴，申报期三个月，逾期不再受理，各地同步执行。"

checks = []

# 1 同标题不同站点 → 合并
docs = [
    D("辽宁省算力券政策正式落地实施_新浪财经", "https://a.test/1", LONG),
    D("辽宁省算力券政策正式落地实施 - 网易", "https://b.test/2", "另一段完全不同的正文内容，讲的是别的事情。"),
    D("无关的一条新闻标题在这里", "https://c.test/3", "完全无关的内容，和算力券没有任何关系的一种表述。"),
]
g = core.cluster(docs)
checks.append(("同标题不同站点会被合并", len(g) == 2))

# 2 轻度改写（换标题、加导语、保留正文）→ 合并
docs = [
    D("政策落地", "https://a.test/1", LONG),
    D("政策正式实施", "https://b.test/2", "编辑整理：" + LONG),
]
g = core.cluster(docs)
checks.append(("只换标题/加导语的转载会被合并", len(g) == 1))

# 3 重度改写（换动词、改数字写法、加新句）→ 抓不住，这是方法上限，用例锁住它
docs = [
    D("政策落地", "https://a.test/1", LONG),
    D("政策正式实施", "https://b.test/2", LONG2),
]
g = core.cluster(docs)
checks.append(("重度改写会漏判（已知上限，见文章第九节）", len(g) == 2))

# 3 政府网站判为官方（没有 authority_level 时）
docs = [
    D("某市算力券申报通知", "https://www.huludao.gov.cn/a.html", score=0.76),
    D("算力券解读", "https://tech.test/b.html", score=0.78),
]
rep = core.analyze("算力券", docs, today=date(2026, 10, 23))
checks.append((".gov.cn 判为官方/一手", rep["tiers"]["官方"] == 1))
checks.append(("没有出现「未命中官方」的提示",
               all("没有命中官方" not in tx for _, tx in rep["flags"])))

# 4 高校域名判为高权威
checks.append((".edu.cn 判为高权威", core.tier_of(D("论文", "https://x.edu.cn/p")) == "高权威"))

# 5 日期三种写法都能解析
ds = [core.parse_date(s) for s in ("2026-10-20", "2026-10-20 09:37:00", "2025/02/26 09:37:00")]
checks.append(("date 三种格式都能解析", all(ds)))
checks.append(("非法日期返回 None", core.parse_date("昨天") is None))

# 6 密度计算
docs = [D(f"标题{i}", f"https://d{i}.test/x", f"第{i}条不同的内容，用来凑够数量。{i}") for i in range(4)]
rep = core.analyze("测试", docs, today=date(2026, 10, 23))
checks.append(("密度 = 独立信源 / 条数", abs(rep["density"] - rep["clusters"] / rep["n"]) < 1e-9))
checks.append(("删掉重复后条数守恒", rep["n"] - rep["clusters"] == rep["dup"]))

# 7 brief 生成
checks.append(("信源结构提示非空", "独立信源" in rep["brief"]))

# 8 相似度对称
checks.append(("相似度对称", abs(core.sim(LONG, LONG2) - core.sim(LONG2, LONG)) < 1e-9))

ok = True
for name, passed in checks:
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    ok &= bool(passed)

print(f"\n{sum(1 for _, p in checks if p)}/{len(checks)} 通过")
sys.exit(0 if ok else 1)
