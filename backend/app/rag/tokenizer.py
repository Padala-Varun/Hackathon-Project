"""BM25 tokenizer that keeps telecom identifiers whole: CMG-12, MOP-UPG-04, 7.11.1, %BGP-5-ADJCHANGE."""
import re

TOKEN_RE = re.compile(
    r"%[A-Za-z0-9_]+(?:-\d+-[A-Za-z0-9_]+)?"  # syslog mnemonic
    r"|[A-Za-z]+(?:-[A-Za-z]+)*-\d+[A-Za-z]?"  # CMG-12, MOP-UPG-04
    r"|\d+(?:\.\d+)+[A-Za-z0-9]*"  # 7.11.1, 23.4R2
    r"|[A-Za-z][A-Za-z0-9_/]*"  # words, var/log
    r"|\d+"
)
# 'up' / 'down' are deliberately not stop words: "session down" matters in networking.
STOP = set(
    """a an and are as at be been but by can could did do does for from had has have if in into is it its
    of on or our so such that the their then there these they this to was we were when which while will with
    after before during not no all any each also only than very via per out""".split()
)


def stem(t: str) -> str:
    if not t.isalpha() or len(t) <= 4:
        return t
    for suf, rep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            if suf == "es" and not t[:-2].endswith(("s", "x", "ch", "sh")):
                continue
            if suf == "s" and t.endswith("ss"):
                continue
            t = t[: -len(suf)] + rep
            if suf in ("ing", "ed") and len(t) > 3 and t[-1] == t[-2] and t[-1] not in "lsz":
                t = t[:-1]
            break
    return t


def tokenize(text: str) -> list[str]:
    out: list[str] = []
    for m in TOKEN_RE.finditer(text or ""):
        tok = m.group(0).lower()
        if tok in STOP:
            continue
        out.append(stem(tok))
        if "-" in tok and not tok.startswith("%"):
            out += [stem(p) for p in tok.split("-") if p and not p.isdigit() and p not in STOP]
    return out
