# -*- coding: utf-8 -*-

from __future__ import annotations

__all__ = [
    "VECTOR_WRITE_FORMATS", "RASTER_WRITE_FORMATS", "TABLE_WRITE_FORMATS",
    "vector_filter_for", "raster_filter_for", "table_filter_for",
    "vector_suffix_for_driver", "vector_format_by_driver",
    "vector_filters", "raster_filters", "table_filters",
]


VECTOR_WRITE_FORMATS = (
    (".gpkg", "GPKG", "GeoPackage", "GeoPackage (*.gpkg)"),
    (".shp", "ESRI Shapefile", "Shapefile", "Esri Shapefile (*.shp)"),
    (".geojson", "GeoJSON", "GeoJSON", "GeoJSON (*.geojson)"),
    (".jsonl", "GeoJSONSeq", "GeoJSON 序列", "GeoJSON 序列 (*.jsonl)"),
    (".fgb", "FlatGeobuf", "FlatGeobuf", "FlatGeobuf (*.fgb)"),
    (".gml", "GML", "GML", "GML (*.gml)"),
    (".kml", "KML", "KML", "KML (*.kml)"),
    (".csv", "CSV", "CSV（WKT 几何列）", "CSV（WKT 几何列）(*.csv)"),
    (".tab", "MapInfo File", "MapInfo TAB", "MapInfo TAB (*.tab)"),
    (".mif", "MapInfo File", "MapInfo MIF", "MapInfo MIF (*.mif)"),
    (".dxf", "DXF", "AutoCAD DXF", "AutoCAD DXF (*.dxf)"),
    (".dgn", "DGN", "MicroStation DGN", "MicroStation DGN (*.dgn)"),
    (".sqlite", "SQLite", "SQLite / SpatiaLite", "SQLite (*.sqlite)"),
    (".gdb", "OpenFileGDB", "Esri 文件地理数据库",
     "Esri 文件地理数据库 (*.gdb)"),
    (".xlsx", "XLSX", "Excel 工作簿", "Excel 工作簿 (*.xlsx)"),
    (".ods", "ODS", "OpenDocument 表格", "OpenDocument 表格 (*.ods)"),
)


TABLE_WRITE_FORMATS = (
    (".csv", "CSV", "CSV（纯属性）", "CSV（纯属性）(*.csv)"),
    (".xlsx", "XLSX", "Excel 工作簿", "Excel 工作簿 (*.xlsx)"),
    (".ods", "ODS", "OpenDocument 表格", "OpenDocument 表格 (*.ods)"),
)


RASTER_WRITE_FORMATS = (
    (".tif", "GTiff", "GeoTIFF", "GeoTIFF (*.tif)", False),
    (".tif", "COG", "Cloud Optimized GeoTIFF",
     "Cloud Optimized GeoTIFF (*.tif)", False),
    (".img", "HFA", "Erdas Imagine", "Erdas Imagine (*.img)", False),
    (".vrt", "VRT", "GDAL VRT（只记引用）", "GDAL VRT (*.vrt)", False),
    (".gpkg", "GPKG", "GeoPackage 栅格", "GeoPackage 栅格 (*.gpkg)", False),
    (".asc", "AAIGrid", "Arc/Info ASCII Grid",
     "Arc/Info ASCII Grid (*.asc)", False),
    (".xyz", "XYZ", "XYZ 文本网格", "XYZ 文本网格 (*.xyz)", False),
    (".bil", "EHdr", "ESRI .hdr Labelled",
     "ESRI .hdr Labelled (*.bil)", False),
    (".nc", "netCDF", "netCDF", "netCDF (*.nc)", False),
    (".ers", "ERS", "ER Mapper", "ER Mapper (*.ers)", False),
    (".rst", "RST", "Idrisi RST", "Idrisi RST (*.rst)", False),
    (".sdat", "SAGA", "SAGA GIS", "SAGA GIS (*.sdat)", False),
    (".jp2", "JP2OpenJPEG", "JPEG 2000", "JPEG 2000 (*.jp2)", False),
    (".png", "PNG", "PNG 图片", "PNG 图片 (*.png)", True),
    (".jpg", "JPEG", "JPEG 图片", "JPEG 图片 (*.jpg)", True),
    (".bmp", "BMP", "BMP 图片", "BMP 图片 (*.bmp)", True),
    (".webp", "WEBP", "WebP 图片", "WebP 图片 (*.webp)", True),
)

EIGHT_BIT_RASTER_DRIVERS = frozenset(
    d for _s, d, _n, _f, eight in RASTER_WRITE_FORMATS if eight)

VECTOR_LAYER_NAME_DRIVERS = frozenset({
    "GPKG", "SQLite", "OpenFileGDB", "GML",
})


def vector_supports_layer_name(driver):
    return str(driver or "").strip().lower() in (
        d.lower() for d in VECTOR_LAYER_NAME_DRIVERS)


def _first(fmt, suffix, index):
    for row in fmt:
        if str(row[index]).lower() == str(suffix or "").lower():
            return row
    return None


def vector_filter_for(suffix):
    row = _first(VECTOR_WRITE_FORMATS, suffix, 0)
    return row[3] if row else ""


def raster_filter_for(suffix):
    row = _first(RASTER_WRITE_FORMATS, suffix, 0)
    return row[3] if row else ""


def vector_format_by_driver(driver):
    d = str(driver or "").strip().lower()
    for row in VECTOR_WRITE_FORMATS:
        if row[1].strip().lower() == d:
            return row
    return None


def vector_suffix_for_driver(driver):
    row = vector_format_by_driver(driver)
    return row[0] if row else ".gpkg"


def vector_filters():
    return ";;".join(row[3] for row in VECTOR_WRITE_FORMATS)


def raster_filters():
    return ";;".join(row[3] for row in RASTER_WRITE_FORMATS)


def table_filter_for(suffix):
    row = _first(TABLE_WRITE_FORMATS, suffix, 0)
    return row[3] if row else ""


def table_filters():
    return ";;".join(row[3] for row in TABLE_WRITE_FORMATS)
