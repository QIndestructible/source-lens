# -*- coding: utf-8 -*-
"""命令行入口：不打开界面，直接出一份体检报告。

    python cli.py "算力券 政策 最新进展"
    python cli.py "房贷利率 下调 最新" --cnt 30 --fresh d7 --out report.md
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    import config
except ImportError:
    print("找不到 config.py，请把 config.example.py 复制一份改名为 config.py 并填入 key。")
    raise SystemExit(2)

import core


def to_markdown(rep):
    L = [f"# 信源体检：{rep['query']}", "",
         "| 指标 | 数值 |", "| --- | --- |",
         f"| 结果条数 | {rep['n']} |",
         f"| 独立信源 | {rep['clusters']} |",
         f"| 独立信源密度 | **{rep['density']:.1%}** |",
         f"| 疑似重复 | {rep['dup']} 条 |",
         f"| 含转载的簇 | {rep['cross']} 个 |", ""]
    if rep["chains"]:
        L += ["## 同源转载", ""]
        for c in rep["chains"][:8]:
            L.append(f"- {c['size']} 条 / {len(c['domains'])} 个域名：{c['title']}")
            L.append(f"  {c['url']}")
        L.append("")
    L += ["## 信源结构提示", "", "```", rep["brief"], "```", ""]
    if rep["flags"]:
        L += ["## 提示", ""] + [f"- **{lv}** {tx}" for lv, tx in rep["flags"]]
    return "\n".join(L) + "\n"


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="元宝搜索 · 信源体检（命令行）")
    ap.add_argument("query", help="要查的问题")
    ap.add_argument("--cnt", type=int, default=config.DEFAULT_CNT)
    ap.add_argument("--mode", type=int, default=config.DEFAULT_MODE)
    ap.add_argument("--fresh", default=config.DEFAULT_FRESHNESS)
    ap.add_argument("--out", default=None, help="把报告写成 Markdown")
    a = ap.parse_args(argv)

    key = (config.WSA_API_KEY or "").strip()
    if not key or "your-key" in key:
        print("还没填 key：打开 config.py，把 WSA_API_KEY 换成你的服务密钥。")
        return 2

    payload = core.search(a.query, key, cnt=a.cnt, mode=a.mode, freshness=a.fresh)
    docs, meta = core.parse_pages(payload)
    if not docs:
        print(f"没有返回结果。Msg={meta.get('msg') or '（无）'}")
        return 1

    rep = core.analyze(a.query, docs)
    md = to_markdown(rep)
    print(md)
    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md, encoding="utf-8")
        print(f"[ok] -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
