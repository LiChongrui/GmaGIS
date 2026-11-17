# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import csv
import io
import os

from ..core.crs import GgsCoordinateReferenceSystem as GgsCrs
from ggis.core.model.field import build_fields
from ggis.core.model.layer import GgsVectorLayer

from ..exec import guard as _guard
import logging
_log = logging.getLogger("gmagis")

__all__ = ["TEXT_SUFFIXES", "is_text_table", "TableInfo", "sniff_table",
           "read_table_points", "guess_xy_fields", "XY_NAME_HINTS"]

TEXT_SUFFIXES = {".csv", ".tsv", ".txt", ".tab"}

_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "utf-16", "latin-1")

_DELIMITERS = (",", "\t", ";", "|")


def is_text_table(path):
    return os.path.splitext(str(path or ""))[1].lower() in TEXT_SUFFIXES


class TableInfo(object):

    __slots__ = ("path", "encoding", "delimiter", "headers", "rows",
                 "truncated")

    def __init__(self, path, encoding, delimiter, headers, rows, truncated):
        self.path = path
        self.encoding = encoding
        self.delimiter = delimiter
        self.headers = list(headers)
        self.rows = list(rows)
        self.truncated = bool(truncated)

    def describe(self):
        return ("编码 %s · 分隔符 %s · %d 列 · 抽样 %d 行"
                % (self.encoding, _show_delim(self.delimiter),
                   len(self.headers), len(self.rows)))

    def __repr__(self):
        return "TableInfo(%r, enc=%s, %d cols, %d rows)" % (
            os.path.basename(self.path), self.encoding,
            len(self.headers), len(self.rows))


def _show_delim(d):
    return {"\t": "制表符", ",": "逗号", ";": "分号", "|": "竖线"}.get(d, d)


def _decode(raw, encoding):
    return raw.decode(encoding)


def _detect_encoding(raw):
    for enc in _ENCODINGS:
        try:
            return enc, _decode(raw, enc)
        except (UnicodeDecodeError, UnicodeError):
            exc_note("_detect_encoding @ ggis/io/csv_io.py:93")
            continue
    return "latin-1", raw.decode("latin-1", errors="replace")


def _detect_delimiter(sample_lines):
    best, best_score = ",", -1.0
    for d in _DELIMITERS:
        counts = [ln.count(d) for ln in sample_lines if ln.strip()]
        counts = [c for c in counts if c > 0]
        if not counts:
            continue
        mode = max(set(counts), key=counts.count)
        agree = counts.count(mode) / float(len(counts))
        score = agree * 100 + min(mode, 40)
        if score > best_score:
            best, best_score = d, score
    return best


def _clean_headers(raw_headers):
    out, seen = [], {}
    for i, h in enumerate(raw_headers):
        name = str(h or "").replace("\ufeff", "").strip() \
            .replace("\r", "").replace("\n", " ")
        if not name:
            name = "列%d" % (i + 1)
        if name in seen:
            seen[name] += 1
            name = "%s_%d" % (name, seen[name])
        else:
            seen[name] = 1
        out.append(name)
    return out


def sniff_table(path, sample_rows=50, encoding=None, delimiter=None):
    p = str(path or "")
    if not p or not os.path.exists(p):
        raise OSError("文件不存在：%s" % p)
    with open(p, "rb") as f:
        raw = f.read()

    if not raw:
        raise ValueError("文件为空")

    enc = encoding
    if enc:
        try:
            text = _decode(raw, enc)
        except (UnicodeDecodeError, UnicodeError, LookupError):
            raise ValueError("按 %s 解码失败" % enc)
    else:
        enc, text = _detect_encoding(raw)

    lines = text.splitlines()
    head = [ln for ln in lines[:sample_rows + 1] if ln.strip()]
    if not head:
        raise ValueError("文件里没有可读的行")

    delim = delimiter or _detect_delimiter(head[:20])

    reader = csv.reader(io.StringIO("\n".join(head)), delimiter=delim)
    try:
        headers = _clean_headers(next(reader))
    except StopIteration:
        raise ValueError("文件里没有表头")

    rows = []
    for i, row in enumerate(reader):
        if i >= sample_rows:
            break
        rows.append([str(c) for c in row])

    return TableInfo(p, enc, delim, headers, rows,
                     truncated=len(lines) > sample_rows + 1)


XY_NAME_HINTS = (
    ("x", ("x", "lon", "lng", "long", "longitude", "经度", "东经", "x坐标")),
    ("y", ("y", "lat", "latitude", "纬度", "北纬", "y坐标")),
)


def _norm(name):
    return str(name or "").strip().lower().replace(" ", "").replace("_", "") \
        .replace("-", "")


def guess_xy_fields(headers):
    norms = [(_norm(h), h) for h in (headers or [])]
    picked = []
    for _axis, cands in XY_NAME_HINTS:
        hit = None
        for c in cands:
            for nh, h in norms:
                if nh == c:
                    hit = h
                    break
            if hit:
                break
        if hit is None:
            for c in cands:
                for nh, h in norms:
                    if c in nh and len(nh) <= len(c) + 4:
                        hit = h
                        break
                if hit:
                    break
        picked.append(hit)
    return picked[0], picked[1]


def _to_float(text):
    s = str(text or "").strip().replace("　", "").replace(",", "") \
        .replace("，", "")
    if not s:
        return None
    s = s.replace("−", "-").replace("－", "-")
    try:
        v = float(s)
    except ValueError:
        # 本函数是列类型探测/坐标解析的一环："转不成数值"是预期正常分支
        # （文本列、说明列），静默返回 None，不走 exc_note（弹用户提示）。
        return None
    if v != v:
        return None
    return v


_STR_LIKE_HINTS = (
    "code", "id", "no", "zip", "tel", "phone", "fax", "post",
    "编号", "代码", "编码", "邮编", "电话", "传真", "序号", "证件",
)


def _looks_like_code(name):
    n = _norm(name)
    return any(h in n for h in _STR_LIKE_HINTS)


def _coerce_columns(headers, attrs):
    if not attrs:
        return attrs
    n = len(attrs)

    for name in headers:
        col = [attrs[i].get(name) for i in range(n)]
        if _looks_like_code(name):
            for i in range(n):
                v = col[i]
                if isinstance(v, str) and not v.strip():
                    attrs[i][name] = None
            continue

        def _has_leading_zero(s):
            t = s.strip()
            if len(t) < 2 or not t[0].isdigit() or t[0] != "0":
                return False
            return t[1].isdigit()

        nonempty = [v for v in col
                    if isinstance(v, str) and v.strip()]
        if any(_has_leading_zero(v) for v in nonempty):
            for i in range(n):
                v = col[i]
                if isinstance(v, str) and not v.strip():
                    attrs[i][name] = None
            continue

        nums = [_to_float(v) if isinstance(v, str) else v for v in col]
        if not any(isinstance(v, (int, float)) and not isinstance(v, bool)
                   for v in nums):
            for i in range(n):
                if isinstance(col[i], str) and not col[i].strip():
                    attrs[i][name] = None
            continue

        all_int = all(
            v is None or (isinstance(v, float) and float(v).is_integer())
            for v in nums)
        for i in range(n):
            v = nums[i]
            if v is None:
                attrs[i][name] = None
            elif all_int:
                attrs[i][name] = int(v)
            else:
                attrs[i][name] = float(v)
    return attrs


@_guard.off_ui("io.csv_io.read_table_points")
def _read_table_points_sync(path, x_field, y_field, crs="EPSG:4326",
                            encoding=None, delimiter=None, name=None,
                            max_features=None):
    from shapely.geometry import Point

    p = str(path or "")
    fname = os.path.splitext(os.path.basename(p))[0] or p
    lname = name or fname

    try:
        info = sniff_table(p, encoding=encoding, delimiter=delimiter)
    except (OSError, ValueError) as e:
        exc_note("_read_table_points_sync @ ggis/io/csv_io.py:356")
        return GgsVectorLayer(lname, p)._fail(str(e))

    if not x_field or not y_field:
        return GgsVectorLayer(lname, p)._fail("未指定 X / Y 列")
    if x_field not in info.headers:
        return GgsVectorLayer(lname, p)._fail("表里没有列「%s」" % x_field)
    if y_field not in info.headers:
        return GgsVectorLayer(lname, p)._fail("表里没有列「%s」" % y_field)

    with open(p, "r", encoding=info.encoding, newline="") as f:
        reader = csv.reader(f, delimiter=info.delimiter)
        try:
            headers = _clean_headers(next(reader))
        except StopIteration:
            exc_note("_read_table_points_sync @ ggis/io/csv_io.py:370")
            return GgsVectorLayer(lname, p)._fail("文件里没有表头")
        xi = headers.index(x_field)
        yi = headers.index(y_field)

        geoms, attrs = [], []
        skipped = 0
        for row in reader:
            if not row or all(not str(c).strip() for c in row):
                continue
            if max_features is not None and len(geoms) >= max_features:
                break
            x = _to_float(row[xi]) if xi < len(row) else None
            y = _to_float(row[yi]) if yi < len(row) else None
            if x is None or y is None:
                skipped += 1
                continue
            geoms.append(Point(x, y))
            attrs.append({headers[i]: (row[i] if i < len(row) else "")
                          for i in range(len(headers))})

    _coerce_columns(headers, attrs)
    fields = build_fields(headers, attrs) if attrs else []
    try:
        crs_obj = GgsCrs.from_user_input(str(crs)) if crs else GgsCrs()
    except Exception:
        _log.exception("silent exception in _read_table_points_sync")
        crs_obj = GgsCrs()

    lyr = GgsVectorLayer(lname, p, crs_obj, "Point", geoms, attrs, fields)
    lyr._valid = True
    if skipped:
        lyr._error = "跳过 %d 行（坐标不是数字）" % skipped
    return lyr


@_guard.offloaded("io.csv_io.read_table_points", kind="io", name="读取文本表")
def read_table_points(path, x_field, y_field, crs="EPSG:4326",
                      encoding=None, delimiter=None, name=None,
                      max_features=None):
    return _read_table_points_sync(
        path, x_field, y_field, crs=crs, encoding=encoding,
        delimiter=delimiter, name=name, max_features=max_features)
