"""脚本编码探测：GBK / UTF-8 / CP932 / Big5。

难点：CP932 是"能吃下任意双字节"的编码，单纯试解码判不出来，
一串 GBK 字节用 CP932 解也全是合法汉字。所以判据落在**用字分布**上：

  * 中文常用字（的/了/是/在/我/你/这/不…）出现得多的 → GBK
  * 假名（の/は/を/に…）出现得多的 → CP932
  * 能严格按 UTF-8 解码且有汉字 → UTF-8

这比"合法率"稳得多，也解释了为什么 JH 那种逐 16 位映射的引擎能直接吃 GBK。
"""
from __future__ import annotations

import re

ZH_COMMON = "的了是在我你他这那不有和人说就"
JA_COMMON = "のはをにでがますてとしれ"

KANA_RE = re.compile(r"[\u3040-\u30ff]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _profile(text: str) -> dict:
    n = max(len(text), 1)
    cjk = len(CJK_RE.findall(text))
    kana = len(KANA_RE.findall(text))
    zh = sum(text.count(c) for c in "的了是在我你他这那不有和人说就")
    ja = sum(text.count(c) for c in "のはをにでがますてとしれ")
    return {"n": n, "cjk": cjk, "kana": kana, "zh": zh, "ja": ja,
            "cjk_ratio": cjk / n, "kana_ratio": kana / n}


def _try_strict(data: bytes, enc: str) -> tuple[str | None, dict]:
    try:
        text = data.decode(enc)
    except UnicodeDecodeError:
        return None, {}
    return text, _profile(text)


def _score(enc: str, p: dict) -> float:
    if not p:
        return -1.0
    if enc in ("gbk", "gb2312", "big5"):
        return p["cjk_ratio"] * 3 + p["zh"] / p["n"] * 40 - p["kana_ratio"] * 20
    if enc == "cp932":
        return p["cjk_ratio"] * 3 + (p["ja"] + p["kana"]) / p["n"] * 40
    if enc == "utf-8":
        return p["cjk_ratio"] * 3 + p["zh"] / p["n"] * 40 + p["kana_ratio"] * 20
    return -1.0


def detect(path_or_bytes) -> tuple[str, dict]:
    data = path_or_bytes
    if isinstance(path_or_bytes, (str, bytes)) is False:
        raise TypeError("需要路径或 bytes")
    if isinstance(path_or_bytes, str):
        with open(path_or_bytes, "rb") as f:
            data = f.read()

    detail: dict[str, dict] = {}

    # 1) 严格可解码的优先：UTF-8 能严格解出来基本就不会错
    text, prof = _try_strict(data, "utf-8")
    detail["utf-8"] = {"strict": text is not None, **(prof or {})}
    # 严格解出来就基本可以确定：非 ASCII 内容（汉字或假名）任一存在即可。
    # 只看 cjk 会漏掉"纯假名"的日文脚本。
    if text is not None and (prof["cjk"] > 0 or prof["kana"] > 0):
        return "utf-8", detail

    # 2) 其余用 ignore 解码后再比用字分布
    best, best_score = "gbk", -9e9
    for enc in ("gbk", "cp932", "big5"):
        try:
            t = data.decode(enc, errors="ignore")
        except LookupError:
            continue
        p = _profile(t)
        s = _score(enc, p)
        detail[enc] = {"strict": False, **{k: v for k, v in p.items()}}
        if s > best_score:
            best, best_score = enc, s
    return best, detail
