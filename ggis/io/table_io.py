# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import logging
import os
import zipfile
import xml.etree.ElementTree as ET

from ggis.core.model.field import build_fields, fields_from_layer
from ggis.core.model.layer import GgsVectorLayer
from ggis.common.util.exc_report import exc_note

from . import csv_io

__all__ = ["TABLE_SUFFIXES", "is_table_path", "read_table",
           "export_table", "table_to_layer"]

_log = logging.getLogger("gmagis")

TABLE_SUFFIXES = {".csv", ".tsv", ".txt", ".xlsx"}

_XNS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def is_table_path(path):
    return os.path.splitext(str(path or ""))[1].lower() in TABLE_SUFFIXES


def _fail(name, path, msg):
    return GgsVectorLayer(name, path)._fail(msg)


def _make_layer(path, headers, rows):
    headers = csv_io._clean_headers(headers)
    attrs = []
    for row in rows or []:
        if not row or all(not str(c).strip() for c in row):
            continue
        attrs.append({headers[i]: (row[i] if i < len(row) else "")
                      for i in range(len(headers))})
    csv_io._coerce_columns(headers, attrs)
    fields = [(str(f.name), str(f.ogr_type or f.type))
              for f in (build_fields(headers, attrs) if attrs else [])]
    name = os.path.splitext(os.path.basename(str(path)))[0] or str(path)
    return GgsVectorLayer(name, str(path), None, "", [], attrs, fields,
                          table=True)


def _read_delimited(path):
    info = csv_io.sniff_table(path)
    with open(path, "r", encoding=info.encoding, newline="") as f:
        reader = csv.reader(f, delimiter=info.delimiter)
        try:
            headers = list(next(reader))
        except StopIteration:
            return None, "文件里没有表头"
        rows = [list(r) for r in reader]
    return (headers, rows), None


def _col_index(ref):
    n = 0
    for ch in str(ref or ""):
        if not ch.isalpha():
            break
        n = n * 26 + (ord(ch.upper()) - 64)
    return max(0, n - 1)


def _read_xlsx(path):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(_XNS + "si"):
                shared.append("".join(
                    t.text or "" for t in si.iter(_XNS + "t")))
        sheet = "xl/worksheets/sheet1.xml"
        if sheet not in names:
            cands = sorted(n for n in names
                           if n.startswith("xl/worksheets/sheet")
                           and n.endswith(".xml"))
            if not cands:
                return None, "工作簿里没有工作表"
            sheet = cands[0]
        root = ET.fromstring(z.read(sheet))
        grid = []
        for row in root.iter(_XNS + "row"):
            cells = {}
            for c in row.findall(_XNS + "c"):
                ci = _col_index(c.get("r")) if c.get("r") else len(cells)
                typ = str(c.get("t") or "")
                if typ == "inlineStr":
                    val = "".join(t.text or ""
                                  for t in c.iter(_XNS + "t"))
                else:
                    v = c.find(_XNS + "v")
                    val = "" if v is None else (v.text or "")
                    if typ == "s" and val:
                        try:
                            val = shared[int(val)]
                        except (ValueError, IndexError):
                            val = ""
                cells[ci] = val
            width = (max(cells) + 1) if cells else 0
            grid.append([cells.get(i, "") for i in range(width)])
    if not grid:
        return None, "工作簿里没有数据"
    headers = list(grid[0])
    n = len(headers)
    rows = [(list(r) + [""] * n)[:n] for r in grid[1:]]
    return (headers, rows), None


def read_table(path):
    p = str(path or "")
    name = os.path.splitext(os.path.basename(p))[0] or p
    try:
        if os.path.splitext(p)[1].lower() == ".xlsx":
            data, err = _read_xlsx(p)
        else:
            data, err = _read_delimited(p)
        if err:
            return _fail(name, p, err)
        return _make_layer(p, data[0], data[1])
    except Exception as e:
        _log.exception("silent exception in read_table")
        exc_note("read_table @ ggis/io/table_io.py")
        return _fail(name, p, str(e))


def _cell_text(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        if v == int(v):
            return str(int(v))
        return repr(v)
    return str(v)


def export_table(layer, path, driver="CSV", fields=None):
    p = str(path or "")
    if not p:
        raise ValueError("未指定输出路径")
    drv = str(driver or "CSV").upper()
    headers = [f.name for f in fields_from_layer(layer)]
    if fields:
        sel = [h for h in fields if h in headers]
    else:
        sel = list(headers)
    rows = []
    for fid in range(layer.feature_count()):
        attrs, _ = layer.feature(fid)
        attrs = attrs or {}
        rows.append([_cell_text(attrs.get(h, "")) for h in sel])
    if drv == "XLSX":
        _write_xlsx(p, sel, rows)
    elif drv == "ODS":
        _write_ods(p, sel, rows)
    else:
        _write_csv(p, sel, rows)
    return p


def _write_csv(path, headers, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for row in rows:
            w.writerow(row)


def _xlsx_col(idx):
    s = ""
    i = idx
    while True:
        s = chr(65 + (i % 26)) + s
        i = i // 26 - 1
        if i < 0:
            break
    return s


def _xml_escape(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _xlsx_cell(ref, val):
    if isinstance(val, bool):
        val = 1 if val else 0
    if isinstance(val, (int, float)):
        s = (repr(val) if isinstance(val, float) else str(val))
        return '<c r="%s"><v>%s</v></c>' % (ref, s)
    txt = _xml_escape(val if val is not None else "")
    return ('<c r="%s" t="inlineStr"><is>'
            '<t xml:space="preserve">%s</t></is></c>' % (ref, txt))


def _write_xlsx(path, headers, rows):
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    sheet_rows = []
    for ri, row in enumerate([headers] + rows, start=1):
        cells = "".join(
            _xlsx_cell("%s%d" % (_xlsx_col(ci), ri), row[ci])
            for ci in range(len(row)))
        sheet_rows.append('<row r="%d">%s</row>' % (ri, cells))
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="%s"><sheetData>%s</sheetData></worksheet>'
             % (ns, "".join(sheet_rows)))
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>')
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="%s" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>' % ns)
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '</Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet)


def _ods_cell(val):
    if isinstance(val, bool):
        val = 1 if val else 0
    if isinstance(val, (int, float)):
        s = (repr(val) if isinstance(val, float) else str(val))
        return ('<table:table-cell office:value-type="float" office:value="%s">'
                '<text:p>%s</text:p></table:table-cell>' % (s, s))
    txt = _xml_escape(val if val is not None else "")
    return ('<table:table-cell office:value-type="string">'
            '<text:p>%s</text:p></table:table-cell>' % txt)


def _write_ods(path, headers, rows):
    body = "".join(
        '<table:table-row>%s</table:table-row>'
        % "".join(_ods_cell(c) for c in row)
        for row in ([headers] + rows))
    content = ('<?xml version="1.0" encoding="UTF-8"?>'
      '<office:document-content '
      'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
      'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
      'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
      'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
      'office:version="1.2">'
      '<office:body><office:spreadsheet>'
      '<table:table table:name="Sheet1">%s</table:table>'
      '</office:spreadsheet></office:body></office:document-content>' % body)
    manifest = ('<?xml version="1.0" encoding="UTF-8"?>'
      '<manifest:manifest '
      'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
      'manifest:version="1.2">'
      '<manifest:file-entry '
      'manifest:media-type="application/vnd.oasis.opendocument.spreadsheet" '
      'manifest:full-path="/"/>'
      '<manifest:file-entry manifest:media-type="text/xml" '
      'manifest:full-path="content.xml"/>'
      '</manifest:manifest>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, "application/vnd.oasis.opendocument.spreadsheet")
        z.writestr("META-INF/manifest.xml", manifest)
        z.writestr("content.xml", content)


def table_to_layer(layer, mode, x_field="", y_field="", wkt_field="", crs=""):
    from ggis.core.crs import GgsCoordinateReferenceSystem as GgsCrs

    headers = [f.name for f in fields_from_layer(layer)]
    geoms, attrs, skipped = [], [], 0

    if str(mode) == "xy":
        if not x_field or not y_field:
            return GgsVectorLayer(layer.name() + "_pt", "")._fail(
                "未指定 X / Y 字段")
        if x_field not in headers:
            return GgsVectorLayer(layer.name() + "_pt", "")._fail(
                "没有列「{0}」".format(x_field))
        if y_field not in headers:
            return GgsVectorLayer(layer.name() + "_pt", "")._fail(
                "没有列「{0}」".format(y_field))
        from shapely.geometry import Point
        for fid in range(layer.feature_count()):
            a, _ = layer.feature(fid)
            a = a or {}
            x = csv_io._to_float(a.get(x_field))
            y = csv_io._to_float(a.get(y_field))
            if x is None or y is None:
                skipped += 1
                continue
            geoms.append(Point(x, y))
            attrs.append(a)
        geom_type = "Point"
    else:
        if not wkt_field:
            return GgsVectorLayer(layer.name() + "_geom", "")._fail(
                "未指定 WKT 几何字段")
        if wkt_field not in headers:
            return GgsVectorLayer(layer.name() + "_geom", "")._fail(
                "没有列「{0}」".format(wkt_field))
        from shapely import wkt as shapely_wkt
        geom_type = None
        for fid in range(layer.feature_count()):
            a, _ = layer.feature(fid)
            a = a or {}
            txt = a.get(wkt_field)
            if not txt or not str(txt).strip():
                skipped += 1
                continue
            try:
                g = shapely_wkt.loads(str(txt))
            except Exception:
                skipped += 1
                continue
            if g is None or g.is_empty:
                skipped += 1
                continue
            if geom_type is None:
                geom_type = g.geom_type
            geoms.append(g)
            attrs.append(a)
        if geom_type is None:
            return GgsVectorLayer(layer.name() + "_geom", "")._fail(
                "没有可识别的几何")

    if not geoms:
        return GgsVectorLayer(layer.name(), "")._fail(
            "没有可转换为几何的数据行")

    csv_io._coerce_columns(headers, attrs)
    fields = build_fields(headers, attrs) if attrs else []
    try:
        crs_obj = (GgsCrs.from_user_input(str(crs)) if crs
                   else GgsCrs())
    except Exception:
        _log.exception("silent exception in table_to_layer")
        crs_obj = GgsCrs()
    name = "%s_geom" % layer.name()
    lyr = GgsVectorLayer(name, "", crs_obj, geom_type, geoms, attrs, fields)
    lyr._valid = True
    if skipped:
        lyr._error = "跳过 {0} 行（缺少或无效几何）".format(skipped)
    return lyr
