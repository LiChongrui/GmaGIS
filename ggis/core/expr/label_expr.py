# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import re
import threading
import logging
_log = logging.getLogger("gmagis")

_FIELD_RE = re.compile(r"\[([\w\u4e00-\u9fff]+)\]")
_CALL_RE = re.compile(r"\s*\.\s*([A-Za-z_]\w*)\s*\(([^()]*)\)")
_LITERAL_RE = re.compile(r"""^\s*(?:"([^"]*)"|'([^']*)')\s*$""")


def _to_int(a):
    try:
        return int(float(a))
    except (TypeError, ValueError):
        exc_note("_to_int @ ggis/core/expr/label_expr.py:64")
        return None


def _fill_args(args, n_max):
    if not args:
        return None, None
    w = _to_int(args[0])
    pad = args[1] if len(args) > 1 and args[1] else " "
    return w, (pad[:1] if pad else " ")


def _round(v, args):
    n = _to_int(args[0]) if args else 0
    if n is None:
        return v
    try:
        return ("%.*f" % (max(0, min(n, 10)), float(v)))
    except (TypeError, ValueError):
        exc_note("_round @ ggis/core/expr/label_expr.py:84")
        return v


def _pad(method):
    def f(v, args):
        w, pad = _fill_args(args, 2)
        if w is None:
            return v
        return getattr(v, method)(w, pad)
    return f


LABEL_METHODS = [
    (".capitalize()", 0, 0, "首字母大写、其余小写",
     lambda v, a: v.capitalize()),
    (".lower()", 0, 0, "全部小写", lambda v, a: v.lower()),
    (".upper()", 0, 0, "全部大写", lambda v, a: v.upper()),
    (".title()", 0, 0, "每个词首字母大写", lambda v, a: v.title()),
    (".swapcase()", 0, 0, "大小写互换", lambda v, a: v.swapcase()),
    (".strip()", 0, 0, "去掉首尾空白", lambda v, a: v.strip()),
    (".lstrip()", 0, 0, "去掉左侧空白", lambda v, a: v.lstrip()),
    (".rstrip()", 0, 0, "去掉右侧空白", lambda v, a: v.rstrip()),
    (".replace(旧, 新)", 2, 2, "把「旧」替换成「新」",
     lambda v, a: v.replace(a[0], a[1])),
    (".zfill(宽度)", 1, 1, "左侧补 0 到指定宽度（区划码常用）",
     lambda v, a: (v.zfill(_to_int(a[0])) if _to_int(a[0]) is not None else v)),
    (".center(宽度, 填充)", 1, 2, "居中并用填充字符补齐", _pad("center")),
    (".ljust(宽度, 填充)", 1, 2, "左对齐并用填充字符补齐", _pad("ljust")),
    (".rjust(宽度, 填充)", 1, 2, "右对齐并用填充字符补齐", _pad("rjust")),
    (".round(小数位)", 1, 1, "数值四舍五入到指定小数位（本项目扩展）", _round),
]

_BY_NAME = {}
for _disp, _lo, _hi, _doc, _fn in LABEL_METHODS:
    _BY_NAME[_disp[1:].split("(")[0]] = (_lo, _hi, _fn)


def method_names():
    return [d[1:].split("(")[0] for d, _lo, _hi, _doc, _fn in LABEL_METHODS]


def first_field(text):
    m = _FIELD_RE.search("" if text is None else str(text))
    return m.group(1) if m else ""


def has_function_call(text):
    s = "" if text is None else str(text)
    return bool(_CALL_RE.search(s))


def has_new_syntax(text):
    s = "" if text is None else str(text)
    return "+" in s or has_function_call(s)


def _split_plus(text):
    parts, buf = [], []
    quote = ""
    depth = 0
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            continue
        if ch == "[":
            depth += 1
            buf.append(ch)
            continue
        if ch == "]":
            depth = max(0, depth - 1)
            buf.append(ch)
            continue
        if ch == "+" and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    parts.append("".join(buf))
    return parts


def _parse_args(raw):
    out, buf, quote = [], [], ""
    for ch in raw:
        if quote:
            if ch == quote:
                quote = ""
            else:
                buf.append(ch)
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == ",":
            out.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail or out:
        out.append(tail)
    return [a for a in out]


def _value_of(attrs, name):
    try:
        if name in attrs:
            v = attrs[name]
        else:
            return ""
    except Exception:
        _log.exception("silent exception in _value_of")
        return ""
    return "" if v is None else str(v)


def _apply(name, raw_args, value):
    spec = _BY_NAME.get(name)
    if spec is None:
        return "%s.%s(%s)" % (value, name, raw_args)
    lo, hi, fn = spec
    args = _parse_args(raw_args)
    if len(args) < lo or (hi and len(args) > hi):
        return "%s.%s(%s)" % (value, name, raw_args)
    try:
        return str(fn(str(value), args))
    except Exception:
        _log.exception("silent exception in _apply")
        return str(value)


def _render_part(part, attrs, strip):
    if strip:
        part = part.strip()
    m = _LITERAL_RE.match(part)
    if m is not None:
        return m.group(1) if m.group(1) is not None else m.group(2)
    out, pos = [], 0
    for fm in _FIELD_RE.finditer(part):
        out.append(part[pos:fm.start()])
        val = _value_of(attrs, fm.group(1))
        end = fm.end()
        while True:
            cm = _CALL_RE.match(part, end)
            if cm is None:
                break
            val = _apply(cm.group(1), cm.group(2), val)
            end = cm.end()
        out.append(val)
        pos = end
    out.append(part[pos:])
    return "".join(out)


def eval_label_expression(expr, attrs):
    text = "" if expr is None else str(expr)
    if not text:
        return ""
    parts = _split_plus(text)
    if len(parts) == 1:
        return _render_part(parts[0], attrs, strip=False)
    return "".join(_render_part(p, attrs, strip=True) for p in parts)


_PY_DEF_RE = re.compile(r"^[ \t]*def[ \t]+([A-Za-z_]\w*)[ \t]*\(", re.M)

_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "chr": chr,
    "dict": dict, "divmod": divmod, "enumerate": enumerate, "filter": filter,
    "float": float, "format": format, "int": int, "len": len, "list": list,
    "map": map, "max": max, "min": min, "ord": ord, "pow": pow,
    "range": range, "repr": repr, "reversed": reversed, "round": round,
    "set": set, "sorted": sorted, "str": str, "sum": sum, "tuple": tuple,
    "zip": zip,
}

SAFE_BUILTINS = _SAFE_BUILTINS

_CTX = threading.local()

_NO_FN_MSG = "代码里没有可调用的函数（请用 def 定义一个）"

_PY_CACHE = {}
_PY_CACHE_MAX = 64


def _field_lookup(name):
    d = getattr(_CTX, "attrs", None)
    if not d:
        return ""
    try:
        if name not in d:
            return ""
        v = d[name]
    except Exception:
        _log.exception("silent exception in _field_lookup")
        return ""
    return "" if v is None else str(v)


def is_python_expr(text):
    return bool(_PY_DEF_RE.search("" if text is None else str(text)))


def py_source(code):
    out, i, n = [], 0, len(code)
    quote = ""
    prev = ""
    while i < n:
        ch = code[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(code[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            prev = ch
            i += 1
            continue
        if ch == "[" and not (prev.isalnum() or prev in "_)].}"):
            m = _FIELD_RE.match(code, i)
            if m is not None:
                out.append('_f("%s")' % m.group(1))
                i = m.end()
                prev = ")"
                continue
        out.append(ch)
        prev = ch
        i += 1
    return "".join(out)


def _pick_callable(ns, code):
    names = _PY_DEF_RE.findall(code)
    order = (["FindLabel"] if "FindLabel" in names else []) + \
        list(reversed(names))
    for nm in order:
        f = ns.get(nm)
        if callable(f):
            return f
    return None


def _compile_python(code):
    hit = _PY_CACHE.get(code)
    if hit is not None:
        return hit
    ns = {"__builtins__": dict(_SAFE_BUILTINS), "_f": _field_lookup}
    try:
        exec(compile(py_source(code), "<标注表达式>", "exec"), ns)
    except Exception as exc:
        _log.exception("silent exception in _compile_python")
        res = (None, "%s: %s" % (type(exc).__name__, exc))
    else:
        fn = _pick_callable(ns, code)
        res = ((fn, "") if fn is not None else (None, _NO_FN_MSG))
    if len(_PY_CACHE) >= _PY_CACHE_MAX:
        _PY_CACHE.clear()
    _PY_CACHE[code] = res
    return res


def python_error(text):
    if not is_python_expr(text):
        return ""
    return _compile_python(str(text))[1]


def _call_python(fn, attrs):
    _CTX.attrs = attrs
    try:
        try:
            n_args = int(fn.__code__.co_argcount)
        except Exception:
            _log.exception("silent exception in _call_python")
            n_args = 1
        r = fn() if n_args == 0 else fn(attrs)
    except Exception as exc:
        _log.exception("silent exception in _call_python")
        return None, "%s: %s" % (type(exc).__name__, exc)
    finally:
        _CTX.attrs = None
    return r, ""


def eval_label_python(text, attrs):
    fn, _err = _compile_python(str(text))
    if fn is None:
        return ""
    r, _err = _call_python(fn, attrs)
    return "" if r is None else str(r)


def verify_python(text, attrs):
    if not is_python_expr(text):
        return eval_label_expression(text, attrs), ""
    fn, err = _compile_python(str(text))
    if fn is None:
        return "", err or _NO_FN_MSG
    r, err = _call_python(fn, attrs)
    return ("" if r is None else str(r)), err


def eval_text(text, attrs):
    if is_python_expr(text):
        return eval_label_python(text, attrs)
    return eval_label_expression(text, attrs)
