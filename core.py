# -*- coding: utf-8 -*-
"""
元宝搜索 · 信源体检器（核心逻辑）
================================

只做三件事：调接口、判重聚簇、算指标。界面在 app.py + ui.html。
"""

import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib import error, request
from urllib.parse import urlparse

API_URL = "https://api.wsa.cloud.tencent.com/SearchPro"
DUP_SIM = 0.55          # 正文 3-gram 相似度阈值：超过就算同一篇
STOP_NONE = None


@dataclass
class Doc:
    title: str = ""
    url: str = ""
    site: str = ""
    date: str = ""
    passage: str = ""
    score: float = 0.0
    authority: float = 0.0


# --------------------------------------------------------------------------- #
# 调接口
# --------------------------------------------------------------------------- #
def search(query, api_key, cnt=20, mode=2, freshness="m1", industry=None,
           site=None, timeout=30):
    payload = {"Query": query, "Mode": mode, "Cnt": cnt}
    if freshness:
        payload["Freshness"] = freshness
    if industry:
        payload["Industry"] = industry
    if site:
        payload["Site"] = site

    req = request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json; charset=UTF-8"},
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"HTTP {e.code}：{body}") from e
    except error.URLError as e:
        raise RuntimeError(f"连不上接口：{e.reason}") from e


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def parse_pages(payload):
    resp = (payload or {}).get("Response") or payload or {}
    raw = resp.get("Pages") or []
    docs, seen = [], set()
    for item in raw:
        if isinstance(item, str):
            try:
                item = json.loads(item)
            except json.JSONDecodeError:
                continue
        if not isinstance(item, dict):
            continue
        body = (item.get("content") or "").strip()
        std = (item.get("passage") or "").strip()
        d = Doc(
            title=(item.get("title") or "").strip(),
            url=(item.get("url") or "").strip(),
            site=(item.get("site") or "").strip(),
            date=(item.get("date") or "").strip(),
            passage=body if len(body) >= len(std) else std,
            score=_f(item.get("score")),
            authority=_f(item.get("authority_level")),
        )
        key = d.url.split("#")[0] or d.title
        if not key or key in seen:
            continue
        seen.add(key)
        docs.append(d)
    meta = {"version": resp.get("Version", ""), "msg": resp.get("Msg", ""),
            "request_id": resp.get("RequestId", "")}
    return docs, meta


# --------------------------------------------------------------------------- #
# 判重
# --------------------------------------------------------------------------- #
def norm_text(s):
    return re.sub(r"[^\u4e00-\u9fffa-zA-Z0-9]+", "", s or "").lower()


def shingles(s, k=3):
    s = norm_text(s)
    if len(s) <= k:
        return {s} if s else set()
    return {s[i:i + k] for i in range(len(s) - k + 1)}


def sim(a, b):
    A, B = shingles(a), shingles(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def title_key(title):
    t = re.split(r"[_|｜]\s*[^_|｜]{0,12}$", title or "")[0]
    t = re.sub(r"\s*[-—–]\s*[^-—–]{0,12}$", "", t)
    return norm_text(t)


class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def cluster(docs):
    uf = _UF(len(docs))
    keys = [title_key(d.title) for d in docs]
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            if keys[i] and keys[i] == keys[j]:
                uf.union(i, j)
            elif sim(docs[i].passage, docs[j].passage) >= DUP_SIM:
                uf.union(i, j)
    groups = {}
    for i, d in enumerate(docs):
        groups.setdefault(uf.find(i), []).append((i, d))
    return list(groups.values())


# --------------------------------------------------------------------------- #
# 指标
# --------------------------------------------------------------------------- #
def domain_of(d):
    return d.site or (urlparse(d.url).netloc if d.url else "")


def parse_date(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime((s or "").strip(), fmt).date()
        except ValueError:
            continue
    return None


def tier_of(d):
    """分三层：官方/一手、高权威、其他。

    旗舰版有 authority_level(0~5) 就直接用；标准版没有这个字段，
    就退回到域名判断——.gov.cn 是政府网站，.edu.cn 是高校，这比 score 可靠得多。
    只看 score 会把政府网站判成"其他"，因为政府公告的标题往往不带关键词，相关度反而不高。
    """
    host = (urlparse(d.url).netloc or "").lower()
    if host.endswith(".gov.cn") or host.endswith(".gov") or ".gov.cn:" in host:
        return "官方"
    if d.authority >= 5:
        return "官方"
    if host.endswith(".edu.cn") or host.endswith(".edu"):
        return "高权威"
    if d.authority >= 3:
        return "高权威"
    if d.authority == 0 and d.score >= 0.85:
        return "高权威"
    return "其他"


def to_brief(query, rep):
    L = [f"【信源结构提示】围绕「{query}」，本次检索共 {rep['n']} 条结果，"
         f"去重后为 {rep['clusters']} 个独立信源（密度 {rep['density']:.0%}）。"]
    if rep["chains"]:
        top = "；".join(f"「{c['title'][:24]}」有 {c['size']} 条、覆盖 {len(c['domains'])} 个域名"
                       for c in rep["chains"][:3])
        L.append(f"其中存在同源转载：{top}。同一通稿无论出现几次，只计一票。")
    t = rep["tiers"]
    if t.get("官方", 0) or t.get("高权威", 0):
        L.append(f"信源分布：官方/一手 {t.get('官方', 0)} 条、高权威 {t.get('高权威', 0)} 条、"
                 f"其他 {t.get('其他', 0)} 条。")
    L.append("若某个结论只有 1 条结果支撑，请在回答中标注「单源，未交叉验证」。")
    return "\n".join(L)


def analyze(query, docs, today=None):
    today = today or date.today()
    groups = cluster(docs)
    cid = {}
    for gi, g in enumerate(groups):
        for i, _d in g:
            cid[i] = gi

    chains = []
    for g in groups:
        if len(g) < 2:
            continue
        ds = [d for _, d in g]
        domains = []
        for d in ds:
            dn = domain_of(d)
            if dn and dn not in domains:
                domains.append(dn)
        best = max(ds, key=lambda d: d.score)
        chains.append({"size": len(ds), "domains": domains,
                       "title": best.title, "url": best.url,
                       "max_auth": max(d.authority for d in ds)})
    chains.sort(key=lambda c: (c["size"], len(c["domains"])), reverse=True)

    tiers = {"官方": 0, "高权威": 0, "其他": 0}
    for d in docs:
        tiers[tier_of(d)] += 1

    dates = [parse_date(d.date) for d in docs]
    dates = [x for x in dates if x]
    has_auth = any(d.authority > 0 for d in docs)

    n = len(docs)
    c = len(groups)
    rep = {
        "query": query,
        "n": n, "clusters": c,
        "density": round(c / n, 3) if n else 0.0,
        "dup": n - c,
        "cross": len(chains),
        "chains": chains,
        "tiers": tiers,
        "has_authority": has_auth,
        "newest": max(dates).isoformat() if dates else "",
        "oldest": min(dates).isoformat() if dates else "",
        "fresh30": sum(1 for x in dates if (today - x).days <= 30),
        "date_count": len(dates),
    }
    rep["brief"] = to_brief(query, rep)

    flags = []
    if rep["density"] < 0.7:
        flags.append(["红", f"独立信源密度只有 {rep['density']:.0%}，这批结果里同源转载偏多"])
    elif rep["density"] < 0.85:
        flags.append(["黄", f"独立信源密度 {rep['density']:.0%}，有 {rep['dup']} 条疑似重复"])
    if chains and len(chains[0]["domains"]) >= 2:
        big = chains[0]
        flags.append(["黄", f"最大一组转载覆盖 {len(big['domains'])} 个域名（{big['size']} 条同源）"])
    if n and tiers["官方"] == 0:
        flags.append(["提示", "没有命中官方/一手信源，基本都是二手转述"])
    if not has_auth:
        flags.append(["提示", "权威度字段缺失（标准版不返回 authority_level），官方/一手是按 .gov.cn 等域名判断的"])
    if dates and rep["fresh30"] == 0:
        flags.append(["黄", "没有 30 天内的结果，时效性偏差"])
    rep["flags"] = flags

    out_docs = []
    for i, d in enumerate(docs):
        out_docs.append({
            "title": d.title, "url": d.url, "site": domain_of(d), "date": d.date,
            "score": round(d.score, 3), "authority": int(d.authority),
            "tier": tier_of(d), "cid": cid[i],
            "cluster_size": len(groups[cid[i]]),
            "passage": d.passage[:220],
        })
    rep["docs"] = out_docs
    return rep
