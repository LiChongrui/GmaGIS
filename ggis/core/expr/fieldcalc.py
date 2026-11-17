# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import re
import threading

from ggis.core.app import i18n
from .expression import (GgsExpressionError, compile_expression, evaluate,
                         user_funcs)
from .label_expr import SAFE_BUILTINS, py_source
import logging
_log = logging.getLogger("gmagis")


__all__ = [
    "CompiledFieldCalc", "compile_field_calc", "eval_field_calc",
    "compile_code_block", "parse_cal", "dump_cal",
]


_CTX = threading.local()

_DEF_NAME_RE = re.compile(r"^[ \t]*def[ \t]+([A-Za-z_]\w*)[ \t]*\(", re.M)

_CB_CACHE = {}
_CB_CACHE_MAX = 64


def _field_lookup(name):
    d = getattr(_CTX, "attrs", None)
    if not d:
        raise KeyError(i18n.tr("当前没有要素属性，[%s] 无处可取") % name)
    if name not in d:
        raise KeyError(i18n.tr("字段「%s」不存在") % name)
    return d[name]


def compile_code_block(code):
    src = "" if code is None else str(code)
    if not src.strip():
        return {}, ""
    hit = _CB_CACHE.get(src)
    if hit is not None:
        return hit
    ns = {"__builtins__": dict(SAFE_BUILTINS), "_f": _field_lookup}
    try:
        exec(compile(py_source(src), "<字段计算器代码块>", "exec"), ns)
    except Exception as exc:
        _log.exception("silent exception in compile_code_block")
        res = (None, "%s: %s" % (type(exc).__name__, exc))
    else:
        fns = {}
        for nm in _DEF_NAME_RE.findall(src):
            f = ns.get(nm)
            if callable(f):
                fns[nm] = f
        res = ((fns, "") if fns else
               (None, i18n.tr("代码块里没有可调用的函数（请用 def 定义一个）")))
    if len(_CB_CACHE) >= _CB_CACHE_MAX:
        _CB_CACHE.clear()
    _CB_CACHE[src] = res
    return res


class CompiledFieldCalc:

    __slots__ = ("expr", "node", "user_fns")

    def __init__(self, expr, node, user_fns):
        self.expr = expr
        self.node = node
        self.user_fns = user_fns


def compile_field_calc(expr, code_block="", fields=None):
    src = "" if expr is None else str(expr)
    if not src.strip():
        return None, i18n.tr("表达式不能为空")
    try:
        node = compile_expression(src, fields)
    except GgsExpressionError as exc:
        exc_note("compile_field_calc @ ggis/core/expr/fieldcalc.py:145")
        return None, str(exc)
    fns, err = compile_code_block(code_block)
    if err:
        return None, err
    return CompiledFieldCalc(src, node, fns), ""


def eval_field_calc(compiled, attrs):
    if compiled is None:
        return None, i18n.tr("表达式尚未编译")
    row = attrs if isinstance(attrs, dict) else {}
    _CTX.attrs = row
    try:
        if compiled.user_fns:
            with user_funcs(compiled.user_fns):
                return evaluate(compiled.node, row), ""
        return evaluate(compiled.node, row), ""
    except GgsExpressionError as exc:
        exc_note("eval_field_calc @ ggis/core/expr/fieldcalc.py:170")
        return None, str(exc)
    except Exception as exc:
        _log.exception("silent exception in eval_field_calc")
        return None, "%s: %s" % (type(exc).__name__, exc)
    finally:
        _CTX.attrs = None


_CAL_HEADER = "#GmaGIS-FIELDCALC-1"
_SEC_RE = re.compile(r"^\[(.+)\][ \t]*$")


def dump_cal(expr, code_block=""):
    expr_s = ("" if expr is None else str(expr)).strip("\n")
    code_s = ("" if code_block is None else str(code_block)).strip("\n")
    return "\n".join([_CAL_HEADER, "[表达式]", expr_s,
                      "[代码块]", code_s]) + "\n"


def parse_cal(text):
    lines = ("" if text is None else str(text)).splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or lines[i].strip() != _CAL_HEADER:
        return "", "", i18n.tr("不是有效的 .cal 文件（文件头应为 %s）") % _CAL_HEADER
    got = {"表达式": [], "代码块": []}
    seen = set()
    cur = None
    for ln in lines[i + 1:]:
        m = _SEC_RE.match(ln)
        if m is not None:
            name = m.group(1).strip()
            if name not in got:
                return "", "", i18n.tr("无法识别的小节「%s」") % name
            seen.add(name)
            cur = name
            continue
        if cur is not None:
            got[cur].append(ln)
    if "表达式" not in seen:
        return "", "", i18n.tr("缺少「表达式」小节")
    return ("\n".join(got["表达式"]).strip("\n"),
            "\n".join(got["代码块"]).strip("\n"), "")
