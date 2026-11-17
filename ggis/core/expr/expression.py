# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import contextlib
import math
import re
import threading

from ggis.exec import guard as _guard
import logging
_log = logging.getLogger("gmagis")


__all__ = [
    "GgsExpressionError", "tokenize", "parse", "compile_expression",
    "evaluate", "select_mask", "check_expression", "referenced_fields",
    "list_functions", "FUNCTION_CATALOG", "function_catalog", "user_funcs",
]


class GgsExpressionError(ValueError):
    pass


_T_NUM = "num"
_T_STR = "str"
_T_IDENT = "ident"
_T_OP = "op"
_T_LP = "("
_T_RP = ")"
_T_COMMA = ","

_OPERATORS = ("<=", ">=", "<>", "!=", "==", "=", "<", ">", "+", "-",
               "*", "/", "%", "^", "||")

_KEYWORDS = {"AND", "OR", "NOT", "LIKE", "IN", "BETWEEN", "IS", "NULL",
             "TRUE", "FALSE"}

_NUM_RE = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_IDENT_RE = re.compile(r"[A-Za-z_\u4e00-\u9fff][A-Za-z0-9_.\u4e00-\u9fff]*")


def tokenize(text):
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "(":
            out.append((_T_LP, c, i))
            i += 1
            continue
        if c == ")":
            out.append((_T_RP, c, i))
            i += 1
            continue
        if c == ",":
            out.append((_T_COMMA, c, i))
            i += 1
            continue
        if c == "'" or c == '"':
            q = c
            j = i + 1
            buf = []
            closed = False
            while j < n:
                if text[j] == q:
                    if j + 1 < n and text[j + 1] == q:
                        buf.append(q)
                        j += 2
                        continue
                    closed = True
                    break
                buf.append(text[j])
                j += 1
            if closed:
                out.append((_T_STR, "".join(buf), i))
                i = j + 1
                continue
            if q == '"':
                out.append((_T_IDENT, text[i + 1:].strip(), i))
                break
            raise GgsExpressionError("第 %d 个字符起字符串未闭合" % (i + 1))
        m = _NUM_RE.match(text, i)
        if m and (c.isdigit() or c == "." or
                  (c in "+-" and i + 1 < n and
                   (text[i + 1].isdigit() or text[i + 1] == "."))):
            out.append((_T_NUM, float(m.group()), i))
            i = m.end()
            continue
        for op in _OPERATORS:
            if text.startswith(op, i):
                out.append((_T_OP, op, i))
                i += len(op)
                break
        else:
            m = _IDENT_RE.match(text, i)
            if not m:
                raise GgsExpressionError(
                    "第 %d 个字符「%s」无法识别" % (i + 1, c))
            word = m.group()
            up = word.upper()
            if up in _KEYWORDS:
                out.append((_T_OP, up, i))
            else:
                out.append((_T_IDENT, word, i))
            i = m.end()
    return out


class _Node:
    __slots__ = ("kind", "a", "b", "c", "pos")

    def __init__(self, kind, a=None, b=None, c=None, pos=0):
        self.kind = kind
        self.a = a
        self.b = b
        self.c = c
        self.pos = pos


class _Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def next(self):
        t = self.peek()
        if t is None:
            raise GgsExpressionError("表达式意外结束")
        self.i += 1
        return t

    def at_op(self, *ops):
        t = self.peek()
        return t is not None and t[0] == _T_OP and t[1] in ops

    def eat_op(self, *ops):
        if self.at_op(*ops):
            return self.next()
        return None

    def expect(self, kind, what):
        t = self.peek()
        if t is None or t[0] != kind:
            raise GgsExpressionError("需要%s" % what)
        return self.next()

    def parse(self):
        node = self.parse_or()
        t = self.peek()
        if t is not None:
            raise GgsExpressionError("第 %d 个字符起有多余内容"
                                     % (t[2] + 1))
        return node

    def parse_or(self):
        left = self.parse_and()
        while self.at_op("OR"):
            self.next()
            right = self.parse_and()
            left = _Node("or", left, right)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.at_op("AND"):
            self.next()
            right = self.parse_not()
            left = _Node("and", left, right)
        return left

    def parse_not(self):
        if self.at_op("NOT"):
            self.next()
            return _Node("not", self.parse_not())
        return self.parse_primary()

    def parse_primary(self):
        t = self.peek()
        if t is None:
            raise GgsExpressionError("表达式意外结束")
        if t[0] == _T_LP:
            self.next()
            node = self.parse_or()
            self.expect(_T_RP, "右括号")
            return node
        return self.parse_predicate()

    def parse_expr(self):
        return self.parse_concat()

    def parse_concat(self):
        left = self.parse_add()
        while self.at_op("||"):
            self.next()
            left = _Node("concat", left, self.parse_add())
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.at_op("+", "-"):
            op = self.next()[1]
            left = _Node("arith", left, self.parse_mul(), op)
        return left

    def parse_mul(self):
        left = self.parse_pow()
        while self.at_op("*", "/", "%"):
            op = self.next()[1]
            left = _Node("arith", left, self.parse_pow(), op)
        return left

    def parse_pow(self):
        left = self.parse_unary()
        if self.at_op("^"):
            self.next()
            left = _Node("arith", left, self.parse_pow(), "^")
        return left

    def parse_unary(self):
        if self.at_op("-", "+"):
            op = self.next()[1]
            node = self.parse_unary()
            return _Node("neg", node) if op == "-" else node
        return self.parse_atom()

    def parse_atom(self):
        t = self.next()
        if t[0] == _T_NUM:
            return ("lit", float(t[1]))
        if t[0] == _T_STR:
            return ("lit", t[1])
        if t[0] == _T_OP:
            up = t[1]
            if up == "NULL":
                return ("lit", None)
            if up == "TRUE":
                return ("lit", True)
            if up == "FALSE":
                return ("lit", False)
            if up == "NOT":
                raise GgsExpressionError("NOT 不能直接作为操作数")
            raise GgsExpressionError("第 %d 个字符「%s」无法识别"
                                     % (t[2] + 1, t[1]))
        if t[0] == _T_LP:
            node = self.parse_or()
            self.expect(_T_RP, "右括号")
            return node
        if t[0] == _T_IDENT:
            up = t[1].upper()
            if up in ("TRUE", "FALSE"):
                return ("lit", up == "TRUE")
            nxt = self.peek()
            if nxt is not None and nxt[0] == _T_LP:
                return self.parse_func(t[1])
            return ("field", t[1])
        raise GgsExpressionError("第 %d 个字符处需要字段名或字面量"
                                 % (t[2] + 1))

    def parse_func(self, name):
        self.next()
        args = []
        if self.peek() is None or self.peek()[0] != _T_RP:
            while True:
                args.append(self.parse_expr())
                nt = self.peek()
                if nt is not None and nt[0] == _T_COMMA:
                    self.next()
                    continue
                break
        self.expect(_T_RP, "右括号")
        return _Node("func", name, args)

    def parse_predicate(self):
        left = self.parse_expr()
        t = self.peek()
        if isinstance(left, tuple) and left[0] == "lit" and \
                isinstance(left[1], bool) and (
                t is None or t[0] == _T_RP
                or (t[0] == _T_OP and t[1] in ("AND", "OR"))):
            return _Node("const", left)
        if t is None or (t[0] == _T_RP):
            return left
        if t[0] == _T_OP and t[1] == "IS":
            self.next()
            neg = bool(self.eat_op("NOT"))
            nt = self.peek()
            if nt is None or not (nt[0] == _T_OP and nt[1] == "NULL"):
                raise GgsExpressionError("IS 后面需要 NULL")
            self.next()
            return _Node("isnull", left, neg)
        neg = False
        if t[0] == _T_OP and t[1] == "NOT":
            nxt = self.toks[self.i + 1] if self.i + 1 < len(self.toks) else None
            if nxt is not None and nxt[0] == _T_OP and \
                    nxt[1] in ("LIKE", "IN", "BETWEEN"):
                self.next()
                neg = True
                t = self.peek()
        if t is not None and t[0] == _T_OP and t[1] == "LIKE":
            self.next()
            pat = self.parse_expr()
            return _Node("like", left, pat, neg)
        if t is not None and t[0] == _T_OP and t[1] == "IN":
            self.next()
            self.expect(_T_LP, "左括号")
            items = []
            if not (self.peek() and self.peek()[0] == _T_RP):
                while True:
                    items.append(self.parse_expr())
                    nt = self.peek()
                    if nt is not None and nt[0] == _T_COMMA:
                        self.next()
                        continue
                    break
            self.expect(_T_RP, "右括号")
            return _Node("in", left, items, neg)
        if t is not None and t[0] == _T_OP and t[1] == "BETWEEN":
            self.next()
            lo = self.parse_expr()
            if not self.eat_op("AND"):
                raise GgsExpressionError("BETWEEN 需要 AND")
            hi = self.parse_expr()
            return _Node("between", left, lo, (hi, neg))
        if t[0] == _T_OP and t[1] in ("=", "==", "!=", "<>", "<", "<=",
                                      ">", ">="):
            op = self.next()[1]
            right = self.parse_expr()
            return _Node("cmp", left, right, op)
        raise GgsExpressionError("第 %d 个字符「%s」处语法错误"
                                 % (t[2] + 1, t[1]))

    def parse_operand(self):
        return self.parse_expr()


def parse(text):
    s = (text or "").strip()
    if not s:
        return None
    return _Parser(tokenize(s)).parse()


def compile_expression(text, fields=None):
    node = parse(text)
    if node is None or fields is None:
        return node
    known = set()
    for f in fields:
        if isinstance(f, str):
            known.add(f)
        elif isinstance(f, (tuple, list)):
            known.add(str(f[0]))
        else:
            known.add(str(getattr(f, "name", f)))
    for name in referenced_fields(node):
        if name not in known:
            raise GgsExpressionError("字段「%s」不存在" % name)
    return node


def referenced_fields(node):
    out = []

    def walk(nd):
        if nd is None:
            return
        if isinstance(nd, tuple):
            if nd[0] == "field" and nd[1] not in out:
                out.append(nd[1])
            return
        if isinstance(nd, list):
            for it in nd:
                walk(it)
            return
        if isinstance(nd, _Node):
            if nd.kind == "between":
                walk(nd.a)
                walk(nd.b)
                if isinstance(nd.c, tuple):
                    walk(nd.c[0])
                return
            for kid in (nd.a, nd.b, nd.c):
                walk(kid)

    walk(node)
    return out


def check_expression(text, fields=None):
    try:
        compile_expression(text, fields)
        return None
    except GgsExpressionError as e:
        exc_note("check_expression @ ggis/core/expr/expression.py:485")
        return str(e)
    except Exception as e:
        _log.exception("silent exception in check_expression")
        return str(e)


def _is_null(v):
    return v is None or (v.__class__ is float and v != v)


_MISS = object()
_STR_NUM_CACHE = {}
_STR_NUM_MAX = 4096


def _number(v):
    c = v.__class__
    if c is float:
        return None if v != v else v
    if c is int:
        return float(v)
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if c is str:
        r = _STR_NUM_CACHE.get(v, _MISS)
        if r is not _MISS:
            return r
        try:
            r = float(v.strip())
        except ValueError:
            exc_note("_number @ ggis/core/expr/expression.py:535")
            r = None
        if len(_STR_NUM_CACHE) < _STR_NUM_MAX:
            _STR_NUM_CACHE[v] = r
        return r
    try:
        n = float(v)
    except (TypeError, ValueError):
        exc_note("_number @ ggis/core/expr/expression.py:542")
        return None
    return None if n != n else n


def _text(v):
    if v.__class__ is str:
        return v
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)


def _resolve(operand, attrs):
    if operand[0] == "lit":
        return operand[1]
    return (attrs or {}).get(operand[1])


def _val(node, attrs):
    if isinstance(node, _Node):
        return evaluate(node, attrs)
    return _resolve(node, attrs)


def _cmp_values(a, b, op):
    an, bn = _number(a), _number(b)
    if an is not None and bn is not None:
        x, y = an, bn
    else:
        ax, bx = _is_null(a), _is_null(b)
        if op in ("=", "=="):
            if ax and bx:
                return True
            if ax or bx:
                return False
        if op in ("!=", "<>"):
            return ax != bx
        if ax or bx:
            return False
        x, y = _text(a).lower(), _text(b).lower()
    try:
        if op in ("=", "=="):
            return x == y
        if op in ("!=", "<>"):
            return x != y
        if op == "<":
            return x < y
        if op == "<=":
            return x <= y
        if op == ">":
            return x > y
        if op == ">=":
            return x >= y
    except TypeError:
        exc_note("_cmp_values @ ggis/core/expr/expression.py:602")
        return False
    return False


_LIKE_CACHE = {}


def _like_to_regex(pattern):
    rx = _LIKE_CACHE.get(pattern)
    if rx is not None:
        return rx
    buf = ["^"]
    for ch in str(pattern):
        if ch in ("%", "*"):
            buf.append(".*")
        elif ch == "_":
            buf.append(".")
        else:
            buf.append(re.escape(ch))
    buf.append("$")
    rx = re.compile("".join(buf), re.IGNORECASE | re.DOTALL)
    if len(_LIKE_CACHE) > 512:
        _LIKE_CACHE.clear()
    _LIKE_CACHE[pattern] = rx
    return rx


def evaluate(node, attrs):
    if node is None:
        return True
    if isinstance(node, tuple):
        return _resolve(node, attrs)
    if not isinstance(node, _Node):
        raise GgsExpressionError("内部错误：语法树节点类型异常 %r" % (node,))
    k = node.kind
    if k == "const":
        return bool(_resolve(node.a, attrs))
    if k == "and":
        return evaluate(node.a, attrs) and evaluate(node.b, attrs)
    if k == "or":
        return evaluate(node.a, attrs) or evaluate(node.b, attrs)
    if k == "not":
        return not evaluate(node.a, attrs)
    if k == "isnull":
        return _is_null(_val(node.a, attrs)) != bool(node.b)
    if k == "cmp":
        return _cmp_values(_val(node.a, attrs),
                           _val(node.b, attrs), node.c)
    if k == "like":
        val = _val(node.a, attrs)
        pat = _val(node.b, attrs)
        if pat is None:
            return False
        hit = bool(_like_to_regex(pat).match(_text(val)))
        return (not hit) if node.c else hit
    if k == "in":
        val = _val(node.a, attrs)
        hit = False
        for item in node.b:
            if _cmp_values(val, _val(item, attrs), "="):
                hit = True
                break
        return (not hit) if node.c else hit
    if k == "between":
        val = _val(node.a, attrs)
        lo = _val(node.b, attrs)
        hi, neg = node.c
        hi = _val(hi, attrs)
        vn, lon, hin = _number(val), _number(lo), _number(hi)
        if vn is not None and lon is not None and hin is not None:
            hit = lon <= vn <= hin
        else:
            hit = (_cmp_values(val, lo, ">=") and
                   _cmp_values(val, hi, "<="))
        return (not hit) if neg else hit
    if k == "neg":
        v = _number(evaluate(node.a, attrs))
        return None if v is None else -v
    if k == "arith":
        x = _number(evaluate(node.a, attrs))
        y = _number(evaluate(node.b, attrs))
        if x is None or y is None:
            return None
        op = node.c
        if op == "+":
            return x + y
        if op == "-":
            return x - y
        if op == "*":
            return x * y
        if op == "/":
            return None if y == 0 else x / y
        if op == "%":
            return None if y == 0 else x % y
        if op == "^":
            return x ** y
    if k == "concat":
        a = evaluate(node.a, attrs)
        b = evaluate(node.b, attrs)
        if a is None or b is None:
            return None
        return _text(a) + _text(b)
    if k == "func":
        args = [evaluate(c, attrs) for c in node.b]
        return _call_func(node.a, args)
    raise GgsExpressionError("未知节点类型 %s" % k)


@_guard.off_ui("core.expression.select_mask")
def select_mask(node, attrs_list, errors=None):
    import numpy as np
    n = len(attrs_list) if attrs_list is not None else 0
    if node is None:
        return np.ones(n, dtype=bool)
    flags = []
    push = flags.append
    ev = evaluate
    empty = {}
    err = None if errors is None else errors.append
    for i, a in enumerate(attrs_list or []):
        try:
            push(ev(node, a if isinstance(a, dict) else empty))
        except Exception as e:
            _log.exception("silent exception in select_mask")
            push(False)
            if err is not None:
                err((i, e))
    return np.array(flags, dtype=bool)


def _fn_abs(args):
    x = _number(args[0]) if args else None
    return None if x is None else abs(x)

def _fn_sqrt(args):
    x = _number(args[0]) if args else None
    return None if (x is None or x < 0) else math.sqrt(x)

def _fn_exp(args):
    x = _number(args[0]) if args else None
    return None if x is None else math.exp(x)

def _fn_ln(args):
    x = _number(args[0]) if args else None
    return None if (x is None or x <= 0) else math.log(x)

def _fn_log10(args):
    x = _number(args[0]) if args else None
    return None if (x is None or x <= 0) else math.log10(x)

def _fn_log(args):
    if len(args) >= 2:
        b = _number(args[0])
        x = _number(args[1])
        if b is None or x is None or b <= 0 or b == 1 or x <= 0:
            return None
        return math.log(x, b)
    x = _number(args[0]) if args else None
    return None if (x is None or x <= 0) else math.log(x)

def _fn_round(args):
    x = _number(args[0]) if args else None
    if x is None:
        return None
    n = int(_number(args[1])) if len(args) >= 2 and \
        _number(args[1]) is not None else 0
    if n <= 0:
        from decimal import Decimal, ROUND_HALF_UP
        return float(Decimal(str(x)).quantize(Decimal("1"), ROUND_HALF_UP))
    factor = 10 ** n
    return math.floor(x * factor + 0.5) / factor

def _fn_floor(args):
    x = _number(args[0]) if args else None
    return None if x is None else math.floor(x)

def _fn_ceil(args):
    x = _number(args[0]) if args else None
    return None if x is None else math.ceil(x)

def _fn_sin(args):
    x = _number(args[0]) if args else None
    return None if x is None else math.sin(x)

def _fn_cos(args):
    x = _number(args[0]) if args else None
    return None if x is None else math.cos(x)

def _fn_tan(args):
    x = _number(args[0]) if args else None
    return None if x is None else math.tan(x)

def _fn_asin(args):
    x = _number(args[0]) if args else None
    return None if (x is None or x < -1 or x > 1) else math.asin(x)

def _fn_acos(args):
    x = _number(args[0]) if args else None
    return None if (x is None or x < -1 or x > 1) else math.acos(x)

def _fn_atan(args):
    x = _number(args[0]) if args else None
    return None if x is None else math.atan(x)

def _fn_atan2(args):
    y = _number(args[0]) if len(args) >= 1 else None
    x = _number(args[1]) if len(args) >= 2 else None
    return None if (y is None or x is None) else math.atan2(y, x)

def _fn_pow(args):
    x = _number(args[0]) if len(args) >= 1 else None
    y = _number(args[1]) if len(args) >= 2 else None
    return None if (x is None or y is None) else x ** y

def _fn_min(args):
    vals = [v for v in (_number(a) for a in args) if v is not None]
    return min(vals) if vals else None

def _fn_max(args):
    vals = [v for v in (_number(a) for a in args) if v is not None]
    return max(vals) if vals else None

def _fn_pi(args):
    return math.pi

def _fn_length(args):
    v = args[0] if args else None
    return None if v is None else len(_text(v))

def _fn_lower(args):
    v = args[0] if args else None
    return None if v is None else _text(v).lower()

def _fn_upper(args):
    v = args[0] if args else None
    return None if v is None else _text(v).upper()

def _fn_title(args):
    v = args[0] if args else None
    return None if v is None else _text(v).title()

def _fn_trim(args):
    v = args[0] if args else None
    return None if v is None else _text(v).strip()

def _fn_ltrim(args):
    v = args[0] if args else None
    return None if v is None else _text(v).lstrip()

def _fn_rtrim(args):
    v = args[0] if args else None
    return None if v is None else _text(v).rstrip()

def _fn_replace(args):
    if len(args) < 3:
        return None
    s, old, new = args[0], args[1], args[2]
    if s is None or old is None or new is None:
        return None
    return _text(s).replace(_text(old), _text(new))

def _fn_substr(args):
    if len(args) < 2:
        return None
    s = args[0]
    if s is None:
        return None
    s = _text(s)
    start = _number(args[1])
    if start is None:
        return None
    start = int(start)
    length = int(_number(args[2])) if len(args) >= 3 and \
        _number(args[2]) is not None else None
    if start < 0:
        start2 = len(s) + start
    else:
        start2 = start - 1
    if length is None:
        return s[start2:]
    return s[start2:start2 + length]

def _fn_coalesce(args):
    for a in args:
        if not _is_null(a):
            return a
    return None

def _fn_concat(args):
    parts = [_text(a) for a in args
             if a is not None and not (isinstance(a, float) and a != a)]
    return "".join(parts)

def _fn_int(args):
    x = _number(args[0]) if args else None
    return None if x is None else int(x)

def _fn_real(args):
    x = _number(args[0]) if args else None
    return None if x is None else float(x)

def _fn_string(args):
    v = args[0] if args else None
    return None if v is None else _text(v)


_FUNC_TABLE = {
    "abs": _fn_abs, "sqrt": _fn_sqrt, "exp": _fn_exp, "ln": _fn_ln,
    "log": _fn_log, "log10": _fn_log10, "round": _fn_round,
    "floor": _fn_floor, "ceil": _fn_ceil,
    "sin": _fn_sin, "cos": _fn_cos, "tan": _fn_tan,
    "asin": _fn_asin, "acos": _fn_acos, "atan": _fn_atan, "atan2": _fn_atan2,
    "pow": _fn_pow, "min": _fn_min, "max": _fn_max, "pi": _fn_pi,
    "length": _fn_length, "lower": _fn_lower, "upper": _fn_upper,
    "title": _fn_title, "trim": _fn_trim, "ltrim": _fn_ltrim, "rtrim": _fn_rtrim,
    "replace": _fn_replace, "substr": _fn_substr, "coalesce": _fn_coalesce,
    "concat": _fn_concat, "int": _fn_int, "real": _fn_real, "string": _fn_string,
}


FUNCTION_CATALOG = (
    ("数学", (
        ("abs", "abs(x)", "绝对值"),
        ("sqrt", "sqrt(x)", "平方根（负数→空）"),
        ("exp", "exp(x)", "自然指数"),
        ("ln", "ln(x)", "自然对数"),
        ("log", "log(x) 或 log(底, x)", "对数"),
        ("log10", "log10(x)", "常用对数"),
        ("round", "round(x[, 小数位])", "四舍五入"),
        ("floor", "floor(x)", "向下取整"),
        ("ceil", "ceil(x)", "向上取整"),
        ("sin", "sin(x)", "正弦"), ("cos", "cos(x)", "余弦"),
        ("tan", "tan(x)", "正切"),
        ("asin", "asin(x)", "反正弦"), ("acos", "acos(x)", "反余弦"),
        ("atan", "atan(x)", "反正切"),
        ("atan2", "atan2(y, x)", "四象限反正切"),
        ("pow", "pow(x, y)", "幂（同 x ^ y）"),
        ("min", "min(a, b, …)", "最小值"),
        ("max", "max(a, b, …)", "最大值"),
        ("pi", "pi()", "常数 π"),
    )),
    ("文本", (
        ("length", "length(s)", "字符串长度"),
        ("lower", "lower(s)", "转小写"),
        ("upper", "upper(s)", "转大写"),
        ("title", "title(s)", "首字母大写"),
        ("trim", "trim(s)", "去首尾空白"),
        ("ltrim", "ltrim(s)", "去左空白"),
        ("rtrim", "rtrim(s)", "去右空白"),
        ("replace", "replace(s, 旧, 新)", "替换"),
        ("substr", "substr(s, 起始[, 长度])", "子串（起始 1-based，可为负）"),
        ("coalesce", "coalesce(a, b, …)", "取首个非空"),
        ("concat", "concat(a, b, …)", "拼接（空值跳过）"),
    )),
    ("转换", (
        ("int", "int(x)", "转整数（截断）"),
        ("real", "real(x)", "转实数"),
        ("string", "string(x)", "转文本"),
    )),
)

_cat_names = [e[0] for _cat, _items in FUNCTION_CATALOG for e in _items]
if sorted(_cat_names) != sorted(_FUNC_TABLE):
    raise RuntimeError(
        "expression.FUNCTION_CATALOG 与 _FUNC_TABLE 不一致，差异：%s"
        % (sorted(set(_cat_names) ^ set(_FUNC_TABLE)),))


def function_catalog():
    return FUNCTION_CATALOG


_CTX = threading.local()


@contextlib.contextmanager
def user_funcs(funcs):
    old = getattr(_CTX, "user_funcs", None)
    _CTX.user_funcs = funcs or None
    try:
        yield
    finally:
        _CTX.user_funcs = old


def _call_func(name, args):
    key = name.lower()
    uf = getattr(_CTX, "user_funcs", None)
    if uf:
        fn = uf.get(name) or uf.get(key)
        if fn is not None:
            try:
                return fn(*args)
            except GgsExpressionError:
                raise
            except Exception as e:
                raise GgsExpressionError("函数 %s 执行出错：%s" % (name, e))
    fn = _FUNC_TABLE.get(key)
    if fn is None:
        raise GgsExpressionError("未知函数「%s」" % name)
    try:
        return fn(args)
    except GgsExpressionError:
        raise
    except Exception as e:
        raise GgsExpressionError("函数 %s 执行出错：%s" % (name, e))


def list_functions():
    return sorted((name, doc)
                  for _cat, items in FUNCTION_CATALOG
                  for name, _sig, doc in items)
