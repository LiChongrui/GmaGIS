# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import QByteArray, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (QColor, QGuiApplication, QIcon, QImage, QPainter,
                           QPixmap)
from PySide6.QtWidgets import QAbstractButton, QStyle
from PySide6.QtSvg import QSvgRenderer


import os
import re
import weakref

_BODY = {
    "eyedropper": '<path stroke-width="1.25" '
                  'd="M9.6 6.2a1.9 1.9 0 0 1 1.9-1.9h1.0a1.9 1.9 0 0 1 1.9 '
                  '1.9v2.8l-1.1 0.7L12 20.2 10.7 9.7 9.6 9z"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.5" stroke-width="1.6"/>'
              '<path d="M15.5 15.5L21 21" stroke-width="1.6"/>',
    "pan": '<path d="M12 3v18M3 12h18"/><path d="M12 3l-2.5 2.5M12 3l2.5 2.5M12 21l-2.5-2.5M12 21l2.5-2.5M3 12l2.5-2.5M3 12l2.5 2.5M21 12l-2.5-2.5M21 12l-2.5 2.5"/>',
    "zoom_in": '<path d="M10 10L4 4"/><path d="M4 9V4h5"/><path d="M14 14l6 6"/><path d="M20 15v5h-5"/>',
    "zoom_out": '<path d="M4 4l6 6"/><path d="M10 5v5H5"/><path d="M20 20l-6-6"/><path d="M14 19v-5h5"/>',
    "zoom_full": '<path d="M4 9V5.5A1.5 1.5 0 015.5 4H9M15 4h3.5A1.5 1.5 0 0120 5.5V9M20 15v3.5a1.5 1.5 0 01-1.5 1.5H15M9 20H5.5A1.5 1.5 0 014 18.5V15"/><path d="M9 9h6v6H9z"/>',
    "zoom_layer": '<path d="M12 3l8 4.5-8 4.5-8-4.5L12 3z"/><path d="M4 12.5l8 4.5 8-4.5"/><path d="M4 17l8 4.5 8-4.5"/>',
    "measure_length": '<path d="M3 19l5.4-7.8 4.2 3.2L21 4.5"/><circle cx="3" cy="19" r="2"/><circle cx="21" cy="4.5" r="2"/><circle cx="12.6" cy="14.4" r="1.8"/>',
    "measure_area": '<path d="M5 16l6-9 8 3-3 8z"/><circle cx="5" cy="16" r="1.6"/><circle cx="11" cy="7" r="1.6"/><circle cx="19" cy="10" r="1.6"/><circle cx="16" cy="18" r="1.6"/>',
    "measure_angle": '<path d="M4 18L12 5l8 13"/><path d="M7.2 18A5.6 5.6 0 0 1 12 12.4" stroke-dasharray="2 1.6"/><circle cx="12" cy="5" r="1.7"/>',
    "select": '<path d="M4 4h4.5M4 4v4.5M20 4h-4.5M20 4v4.5M4 20h4.5M4 20v-4.5M20 20h-4.5M20 20v-4.5" stroke-dasharray="2.5 2.5"/><path d="M11 11l3.2 8 1.4-3.4L19 14.2z"/>',
    "identify": '<path d="M5 3.5l14.5 6.2-6.3 2.2-2.2 6.3z"/><circle cx="17.5" cy="17.5" r="3.6"/><path d="M17.5 16.2v2.8"/>',
    "open": '<path d="M3 7.5A1.5 1.5 0 014.5 6h4l2 2.5h7A1.5 1.5 0 0119 10v7.5a1.5 1.5 0 01-1.5 1.5h-13A1.5 1.5 0 013 17.5v-10z"/>',
    "add_vector": '<path d="M4 17.5l4.8-7.6 3.9 4.9 2.9-3.7 4.4 6.4z"/><path d="M17.5 2.8v6M14.5 5.8h6"/>',
    "add_data": '<path d="M11.5 3.5l7 3.9-7 3.9-7-3.9z"/>'
                '<path d="M4.5 11.3l7 3.9 3.5-1.95"/>'
                '<path d="M4.5 15.2l7 3.9 2.3-1.28"/>'
                '<path d="M19 13.5v6.5M15.75 16.75h6.5"/>',
    "add_raster": '<rect x="3.5" y="7.5" width="13" height="11" rx="1.2"/><path d="M6.7 7.5v11M10 7.5v11M13.3 7.5v11M3.5 11h13M3.5 14.8h13"/><path d="M18.5 2.8v6M15.5 5.8h6"/>',
    "toolbox": '<circle cx="12" cy="12" r="3.1"/><path d="M12 2.8l1.2 2.6 2.8.6 2-2 1.9 1.9-2 2 .6 2.8 2.6 1.2v.2l-2.6 1.2-.6 2.8 2 2-1.9 1.9-2-2-2.8.6L12 21.2h-.2l-1.2-2.6-2.8-.6-2 2-1.9-1.9 2-2-.6-2.8L2.8 12v-.2l2.6-1.2.6-2.8-2-2L5.9 4l2 2 2.8-.6L11.9 2.8z"/>',
    "save": '<path d="M4.5 5.5A1.5 1.5 0 016 4h9l5 5v9.5a1.5 1.5 0 01-1.5 1.5H6a1.5 1.5 0 01-1.5-1.5v-13z"/><path d="M8 4v5h7"/><rect x="7.5" y="13" width="9" height="7"/>',
    "save_modified": '<path d="M4.5 5.5A1.5 1.5 0 016 4h9l5 5v9.5a1.5 1.5 0 01-1.5 1.5H6a1.5 1.5 0 01-1.5-1.5v-13z"/><path d="M8 4v5h7"/><rect x="7.5" y="13" width="9" height="7"/><circle cx="20.4" cy="20.4" r="3.2" fill="currentColor" stroke="none"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
            '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "logo": '<circle cx="12" cy="12" r="8.5"/>'
            '<path d="M3.5 12h17"/>'
            '<path d="M12 3.5c3.2 2.5 3.2 14.5 0 17"/>'
            '<path d="M12 3.5c-3.2 2.5-3.2 14.5 0 17"/>',
    "new": '<path d="M5.5 4.5h8l5 5v10a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 015 19.5v-15z"/><path d="M13 4.5V9a.5.5 0 00.5.5H19"/>',
    "new_file": '<path d="M3.5 6.5A1.5 1.5 0 015 5h6.5l4 4v9.5a1.5 1.5 0'
                ' 01-1.5 1.5H5a1.5 1.5 0 01-1.5-1.5v-12z"/>'
                '<path d="M11.5 5v4h4"/>'
                '<path d="M19 4v5.5M16.25 6.75h5.5"/>',
    "new_shape": '<path d="M12 3.8l8 5.4-3 9.4H7l-3-9.4z"/>'
                 '<path d="M12 9.6v4.8M9.6 12h4.8"/>',
    "remove": '<path d="M5 7h14M9.5 7V4.5h5V7M7 7l1 12.5A1.5 1.5 0 009.5 21h5a1.5 1.5 0 001.5-1.5L17 7"/>',
    "refresh": '<path d="M19.5 12a7.5 7.5 0 11-2.6-5.7"/><path d="M19.5 4v4.5H15"/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5"/><circle cx="12" cy="8" r="0.8" fill="currentColor" stroke="none"/>',
    "keyboard": '<rect x="2.5" y="6.5" width="19" height="11" rx="1.5"/>'
                '<path d="M5.5 9.5h.01M8.5 9.5h.01M11.5 9.5h.01M14.5 9.5h.01M17.5 9.5h.01'
                'M5.5 12.5h.01M8.5 12.5h.01M11.5 12.5h.01M14.5 12.5h.01M17.5 12.5h.01'
                'M5.5 15.5h.01M8 15.5h8M18.5 15.5h.01"/>',
    "crs": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.4 2.5 14.1 0 17M12 3.5c-2.5 2.4-2.5 14.1 0 17"/>',
    "crs_geo": '<circle cx="12" cy="12" r="8.5"/>'
               '<path d="M3.5 12h17"/>'
               '<path d="M5.3 7.4c3.8 1.7 9.6 1.7 13.4 0"/>'
               '<path d="M5.3 16.6c3.8-1.7 9.6-1.7 13.4 0"/>',
    "crs_proj": '<path d="M6.6 4h12.4l-2.4 10.8H4.2z"/>'
                '<path d="M5.8 7.6h12.4M5 11.2h12.4"/>'
                '<path d="M10.6 4l-2.4 10.8M15 4l-2.4 10.8"/>',
    "project_props": '<path d="M4 7h9M17 7h3"/><circle cx="15" cy="7" r="2.2"/><path d="M4 12h3M11 12h9"/><circle cx="9" cy="12" r="2.2"/><path d="M4 17h9M17 17h3"/><circle cx="15" cy="17" r="2.2"/>',
    "add_feature": '<circle cx="12" cy="12" r="8.5"/><path d="M12 8v8M8 12h8"/>',
    "settings": '<circle cx="12" cy="12" r="3.2"/><circle cx="12" cy="12" r="7.8" stroke-dasharray="3.1 2.7"/>',
    "quit": '<path d="M14 4.5H6.5A1.5 1.5 0 005 6v12a1.5 1.5 0 001.5 1.5H14"/><path d="M10 12h10M17 9l3 3-3 3"/>',
    "edit": '<path d="M4 20l1-4L16.5 4.5a2.1 2.1 0 013 3L8 19l-4 1z"/><path d="M14.5 6.5l3 3"/>',
    "move_feature": '<path d="M12 3v18M3 12h18"/><path d="M12 3l-2.5 2.5M12 3l2.5 2.5M12 21l-2.5-2.5M12 21l2.5-2.5M3 12l2.5-2.5M3 12l2.5 2.5M21 12l-2.5-2.5M21 12l-2.5 2.5"/><circle cx="12" cy="12" r="2.6"/>',
    "delete_feature": '<circle cx="12" cy="12" r="8.5"/><path d="M8.5 8.5l7 7M15.5 8.5l-7 7"/>',
    "multipart_single": '<path d="M4 12a5.5 5.5 0 015.5-5.5h2V10"/><path d="M20 12a5.5 5.5 0 01-5.5 5.5h-2V14"/><circle cx="11.5" cy="12" r="2.2"/><path d="M13.7 12H20M4 12h3.6"/>',
    "combine_features": '<rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/><path d="M11 7.5h5.5V13M7.5 11v5.5H13"/>',
    "centroid": '<path d="M5 8l7-4.2 7 4.2v8L12 20.2 5 16z"/>'
                '<circle cx="12" cy="12" r="2"/><path d="M12 6.6v3.4M12 14v3.4M6.6 12H10M14 12h3.4"/>',
    "align": '<rect x="3" y="4" width="7" height="5" rx="1"/>'
             '<rect x="14" y="15" width="7" height="5" rx="1"/>'
             '<path d="M2.5 12h19" stroke-dasharray="3.2 2.4"/>'
             '<path d="M6.5 9v2.6M17.5 12.4V15"/>',
    "simplify": '<path d="M3 19l4-8 3 4 4-10 3 6 4-7" stroke-dasharray="2.4 2.2"/>'
                '<path d="M3 19l6-8 7 3 5-10"/>',
    "break": '<path d="M2.5 12h6.5M15 12h6.5"/>'
             '<path d="M11 7.5L9.5 16.5M14.5 7.5L13 16.5"/>',
    "buffer": '<circle cx="12" cy="12" r="2.4"/>'
              '<circle cx="12" cy="12" r="6.2" stroke-dasharray="3 2.2"/>'
              '<circle cx="12" cy="12" r="9.6" stroke-dasharray="3 2.2"/>',
    "overlay": '<rect x="3.5" y="3.5" width="11" height="11" rx="1"/>'
               '<rect x="9.5" y="9.5" width="11" height="11" rx="1"/>',
    "intersect": '<rect x="3.5" y="3.5" width="11" height="11" rx="1"/>'
                 '<rect x="9.5" y="9.5" width="11" height="11" rx="1"/>'
                 '<path d="M9.5 9.5h5v5h-5z" fill="currentColor" '
                 'stroke="none" opacity="0.55"/>',
    "difference": '<rect x="3.5" y="3.5" width="11" height="11" rx="1"/>'
                  '<rect x="9.5" y="9.5" width="11" height="11" rx="1" '
                  'stroke-dasharray="2.6 2.2"/>',
    "sym_difference": '<rect x="3.5" y="3.5" width="11" height="11" rx="1"/>'
                      '<rect x="9.5" y="9.5" width="11" height="11" rx="1"/>'
                      '<path d="M10 10l4.5 4.5M14.5 10l-4.5 4.5" '
                      'stroke-width="1.1"/>',
    "identity": '<rect x="3.5" y="3.5" width="17" height="17" rx="1"/>'
                '<path d="M3.5 12h9l4 8.5" stroke-dasharray="2.6 2.2"/>',
    "convex_hull": '<path d="M5.6 13.8L9.8 5.6l7.6 1.6 2.2 6.8-6.4 4z" '
                   'fill="currentColor" stroke="none" opacity="0.22"/>'
                   '<path d="M5.6 13.8L9.8 5.6l7.6 1.6 2.2 6.8-6.4 4z"/>'
                   '<circle cx="9.8" cy="5.6" r="1.2" fill="currentColor" '
                   'stroke="none"/>'
                   '<circle cx="17.4" cy="7.2" r="1.2" fill="currentColor" '
                   'stroke="none"/>'
                   '<circle cx="19.6" cy="14" r="1.2" fill="currentColor" '
                   'stroke="none"/>'
                   '<circle cx="13.2" cy="18" r="1.2" fill="currentColor" '
                   'stroke="none"/>'
                   '<circle cx="5.6" cy="13.8" r="1.2" fill="currentColor" '
                   'stroke="none"/>',
    "bounding_box": '<rect x="4" y="4.4" width="16" height="15.2" rx="1" '
                    'stroke-dasharray="2.8 2.2"/>'
                    '<circle cx="8.6" cy="9" r="1.2" fill="currentColor" '
                    'stroke="none"/>'
                    '<circle cx="15.8" cy="8" r="1.2" fill="currentColor" '
                    'stroke="none"/>'
                    '<circle cx="12.6" cy="15.8" r="1.2" fill="currentColor" '
                    'stroke="none"/>',
    "delete_duplicates": '<rect x="4" y="4" width="11" height="11" rx="1"/>'
                         '<rect x="9" y="9" width="11" height="11" rx="1" '
                         'stroke-dasharray="2.6 2.2"/>'
                         '<path d="M14.6 4.4l4.4 4.4M19 4.4l-4.4 4.4" '
                         'stroke-width="1.1"/>',
    "densify": '<path d="M4.2 17.6l6-9.2 4.6 4.2 5-7.4"/>'
               '<circle cx="7.2" cy="13" r="1.1" fill="currentColor" '
               'stroke="none"/>'
               '<circle cx="12.4" cy="10.6" r="1.1" fill="currentColor" '
               'stroke="none"/>'
               '<circle cx="15.4" cy="8.2" r="1.1" fill="currentColor" '
               'stroke="none"/>',
    "round_coordinates": '<rect x="4.4" y="4.4" width="15.2" height="15.2" '
                         'rx="1" opacity="0.45"/>'
                         '<path d="M9.5 4.4v15.2M14.5 4.4v15.2M4.4 9.5h15.2'
                         'M4.4 14.5h15.2" opacity="0.4"/>'
                         '<circle cx="9.5" cy="9.5" r="1.6" fill="currentColor" '
                         'stroke="none"/>'
                         '<circle cx="14.5" cy="14.5" r="1.6" '
                         'fill="currentColor" stroke="none"/>',
    "clip": '<rect x="3.5" y="3.5" width="17" height="17" rx="1"/>'
            '<path d="M12 3.5v17M3.5 12h17" stroke-dasharray="2.6 2.2"/>'
            '<path d="M3.5 3.5h8.5v8.5H3.5z" fill="currentColor" '
            'stroke="none" opacity="0.35"/>',
    "dissolve": '<circle cx="9.2" cy="12" r="5.4"/>'
                '<circle cx="14.8" cy="12" r="5.4"/>',
    "batch": '<rect x="3" y="4" width="13" height="3.6" rx="1"/>'
             '<rect x="3" y="10.2" width="18" height="3.6" rx="1"/>'
             '<rect x="3" y="16.4" width="10" height="3.6" rx="1"/>',
    "layout": '<rect x="3.5" y="4" width="17" height="16" rx="1.6"/>'
              '<rect x="6" y="6.6" width="8.6" height="7.6"/>'
              '<path d="M16.4 6.6h2.2M16.4 9.4h2.2M16.4 12.2h2.2"/>'
              '<path d="M6 16.6h12.6"/>',
    "layout_map": '<rect x="3.5" y="4.5" width="17" height="15" rx="1.4"/>'
                  '<path d="M3.5 12.5l4-3.4 3.2 3.6 3-2.6 4.3 4"/>'
                  '<rect x="3.5" y="4.5" width="17" height="15" rx="1.4"/>',
    "layout_legend": '<rect x="3.4" y="5" width="5.2" height="3.2" rx="0.6"/>'
                     '<rect x="3.4" y="10.4" width="5.2" height="3.2" rx="0.6"/>'
                     '<rect x="3.4" y="15.8" width="5.2" height="3.2" rx="0.6"/>'
                     '<path d="M10.6 6.6h9.8M10.6 12h9.8M10.6 17.4h9.8"/>',
    "layout_scale": '<path d="M2.6 9.4h18.8v5.2H2.6z"/>'
                    '<path d="M7.3 9.4v5.2M12 9.4v5.2M16.7 9.4v5.2"/>'
                    '<path d="M2.6 9.4h4.7v5.2H2.6zM12 9.4h4.7v5.2H12z" '
                    'fill="currentColor" stroke="none"/>',
    "layout_north": '<path d="M12 3.2l2.6 6.2 6.2 2.6-6.2 2.6L12 20.8'
                    'l-2.6-6.2L3.2 12l6.2-2.6z"/>',
    "layout_grid": '<rect x="3.5" y="4.5" width="17" height="15" rx="1.2"/>'
                   '<path d="M3.5 9.5h17M3.5 14.5h17M9.2 4.5v15M14.8 4.5v15"/>',
    "layout_text": '<path d="M5 5.4h14M12 5.4v13.2"/>'
                   '<path d="M8.6 18.6h6.8"/>',
    "layout_image": '<rect x="3.5" y="4.8" width="17" height="14.4" rx="1.4"/>'
                    '<circle cx="8.6" cy="9.6" r="1.7"/>'
                    '<path d="M4.6 17.6l4.6-4.4 3.2 3.1 2.8-2.4 4.2 3.7"/>',
    "zoom_100": '<rect x="3.5" y="5.5" width="17" height="13" rx="1.6"/>'
                '<path d="M9 5.5v13M15 5.5v13"/>',
    "view_prev": '<path d="M19 12H7"/><path d="M11.5 7.5L7 12l4.5 4.5"/>',
    "view_next": '<path d="M5 12h12"/><path d="M12.5 7.5L17 12l-4.5 4.5"/>',
    "ruler": '<rect x="2.5" y="8.2" width="19" height="7.6" rx="1.2"/>'
             '<path d="M6 8.2v3M9 8.2v4.6M12 8.2v3M15 8.2v4.6M18 8.2v3"/>',
    "guide": '<path d="M3.5 8.5h17" stroke-dasharray="3 2.4"/>'
             '<path d="M3.5 15.5h17" stroke-dasharray="3 2.4"/>',
    "margin": '<rect x="3.4" y="4.6" width="17.2" height="14.8" rx="1.4"/>'
              '<rect x="6.6" y="7.8" width="10.8" height="8.4" rx="0.8"'
              ' stroke-dasharray="2.6 2.2"/>',
    "zoom_map": '<rect x="3.4" y="5.4" width="12.6" height="12.6" rx="1.4"/>'
                '<circle cx="17.4" cy="15.6" r="3.2"/>'
                '<path d="M19.7 17.9l2 2"/>',
    "page_orient": '<rect x="3.4" y="6.6" width="9.4" height="13" rx="1.3"/>'
                   '<rect x="16" y="9.6" width="4.8" height="7.8" rx="1"/>',
    "export_pdf": '<path d="M6 3.5h8L19 8.5v12H6z"/>'
                  '<path d="M14 3.5V9h5"/>'
                  '<path d="M12 11.6v6.4M9.4 15.4L12 18l2.6-2.6"/>',
    "export_image": '<rect x="3.5" y="4" width="13.5" height="11" rx="1.3"/>'
                    '<path d="M4.6 14l3.6-3.5 2.6 2.5 2.2-1.9 3.2 2.9"/>'
                    '<path d="M19 10.5v9M16.4 17l2.6 2.6L21.6 17"/>',
    "print": '<path d="M7 9V3.6h10V9"/>'
             '<rect x="3.5" y="9" width="17" height="7.4" rx="1.4"/>'
             '<rect x="7" y="13.4" width="10" height="7" rx="0.8"/>',
    "page_setup": '<rect x="4.5" y="3.5" width="11.5" height="15" rx="1.3"/>'
                  '<path d="M7.4 7.4h5.6M7.4 10.6h5.6M7.4 13.8h3.4"/>'
                  '<circle cx="17.6" cy="17.4" r="3.2"/>'
                  '<path d="M17.6 13.4v1.2M17.6 20.2v1.2M13.6 17.4h1.2'
                  'M20.4 17.4h1.2"/>',
    "layer": '<path d="M12 3.5l8.5 4.5-8.5 4.5L3.5 8z"/>'
             '<path d="M4.5 12l7.5 4 7.5-4"/>'
             '<path d="M4.5 16l7.5 4 7.5-4"/>',
    "log": '<rect x="4.5" y="3.5" width="15" height="17" rx="1.5"/>'
           '<path d="M8 8h8M8 11.5h8M8 15h5"/>',
    "task": '<rect x="4.5" y="3.5" width="15" height="17" rx="1.5"/>'
            '<path d="M8 8h8M8 11.5h8M8 15h4"/>'
            '<path d="M13.5 15.5h5" stroke-width="2.4"/>',
    "message": '<path d="M3.5 5.5A1.5 1.5 0 015 4h14a1.5 1.5 0 011.5 1.5v9a1.5 1.5 0 01-1.5 1.5H10l-4.5 4v-4H5a1.5 1.5 0 01-1.5-1.5v-9z"/>'
               '<circle cx="8" cy="10" r="1" fill="currentColor" stroke="none"/>'
               '<circle cx="12" cy="10" r="1" fill="currentColor" stroke="none"/>'
               '<circle cx="16" cy="10" r="1" fill="currentColor" stroke="none"/>',
    "new_shapefile": '<path d="M13.5 3.5H7A1.5 1.5 0 005.5 5v14A1.5 1.5 0 007 20.5h10a1.5 1.5 0 001.5-1.5V8.5l-5-5z"/>'
                     '<path d="M13.5 3.5V8.5H18.5"/>'
                     '<path d="M8 15.5l2.5-3.5 2 2.5 1.5-2 2.5 3"/>',
    "vertex_edit": '<path d="M6.5 14.5l4.5-7 6 9"/><rect x="3.5" y="13" width="4" height="4" rx="0.8"/><rect x="9" y="4" width="4" height="4" rx="0.8"/><rect x="15" y="15" width="4" height="4" rx="0.8"/>',
    "vertex_select": '<rect x="3" y="3" width="18" height="18" rx="1.5" stroke-dasharray="2.5 2.5"/><rect x="6" y="6" width="4.5" height="4.5" rx="0.8" fill="currentColor" stroke="none"/><rect x="13.5" y="13.5" width="4.5" height="4.5" rx="0.8" fill="currentColor" stroke="none"/>',
    "snap_midpoint": '<path d="M4 18.5L20 5.5"/><circle cx="12" cy="12" r="2.4" fill="currentColor" stroke="none"/>',
    "snap_edge": '<path d="M3.5 17.5L20.5 6.5"/><rect x="8.8" y="8.8" width="6.4" height="6.4" rx="1"/>',
    "fix_geometry": '<path d="M3.5 4.5h9.5l4 4.5-3.2 9.5H4.5z"/><path d="M13.2 15.6l2.1 2.1 4.3-5"/>',
    "vertex_add": '<path d="M3.5 17.5l6-7 5 5"/><rect x="2.5" y="15.5" width="4" height="4" rx="0.8"/><rect x="12" y="13" width="4" height="4" rx="0.8"/><path d="M17.5 5.5v6M14.5 8.5h6"/>',
    "vertex_move": '<rect x="3" y="15" width="5" height="5" rx="0.8"/>'
                   '<path d="M15.5 11.5V4M12.6 6.9L15.5 4l2.9 2.9"/>'
                   '<path d="M15.5 19v-7.5M12.6 16.1l2.9 2.9 2.9-2.9"/>'
                   '<path d="M15.5 11.5H8M10.9 8.6L8 11.5l2.9 2.9"/>'
                   '<path d="M23 11.5h-7.5M20.1 8.6L23 11.5l-2.9 2.9"/>',
    "vertex_delete": '<rect x="3" y="12" width="4.5" height="4.5" rx="0.8"/><path d="M5 10.5V5.5M3.2 7.3L5 5.5l1.8 1.8"/><path d="M12.5 9.5l7 7M19.5 9.5l-7 7"/>',
    "split_features": '<path d="M4 10.5V6a2 2 0 012-2h4.5"/><path d="M13.5 4H18a2 2 0 012 2v4.5"/><path d="M20 13.5V18a2 2 0 01-2 2h-4.5"/><path d="M10.5 20H6a2 2 0 01-2-2v-4.5"/><path d="M20 4L4 20"/>',
    "reshape": '<path d="M5 19.5V9l7-4.5 7 4.5v4"/><path d="M13.5 20.5l7-7"/>',
    "bookmark": '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9L12 3.5z"/>',
    "expand": '<path d="M4 6.5h9M4 12h16M4 17.5h16"/><path d="M16.5 4.5l3 2-3 2"/>',
    "collapse": '<path d="M4 6.5h9M4 12h16M4 17.5h16"/><path d="M16.5 8.5l3-2 3 2" transform="translate(-2 0)"/>',
    "expand_all": '<path d="M7 5.5l5 5 5-5"/><path d="M7 12.5l5 5 5-5"/>',
    "collapse_all": '<path d="M7 18.5l5-5 5 5"/><path d="M7 11.5l5-5 5 5"/>',
    "visible": '<path d="M2.5 12S6 5.6 12 5.6 21.5 12 21.5 12 18 18.4 12 18.4'
               ' 2.5 12 2.5 12z"/>'
               '<circle cx="12" cy="12" r="3.2"/>',
    "hidden": '<path d="M4.4 7.2A15.5 15.5 0 002.5 12S6 18.4 12 18.4c1.5 0 '
              '2.9-.4 4.1-1"/>'
              '<path d="M9.2 6c.9-.25 1.8-.4 2.8-.4 6 0 9.5 6.4 9.5 6.4a17 '
              '17 0 01-2.6 3.3"/>'
              '<path d="M4 20L20 4"/>',
    "new_group": '<path d="M3 7.5A1.5 1.5 0 014.5 6h4l2 2.5h7A1.5 1.5 0 0119 10v7.5a1.5 1.5 0 01-1.5 1.5h-13A1.5 1.5 0 013 17.5v-10z"/><path d="M12 12v5M9.5 14.5h5"/>',
    "browser": '<path d="M3 6.5A1.5 1.5 0 014.5 5h4l2 2.5h8A1.5 1.5 0 0120 9v8.5a1.5 1.5 0 01-1.5 1.5h-14A1.5 1.5 0 013 17.5v-11z"/><path d="M8 12h8M8 15h5"/>',
    "styling": '<path d="M12 3a9 9 0 000 18c1.7 0 2-1.2 1.4-2.2-.7-1.2.1-2.8 1.7-2.8H17a4 4 0 004-4c0-5-4-9-9-9z"/><circle cx="7.5" cy="11" r="1.1"/><circle cx="10" cy="7.5" r="1.1"/><circle cx="14.5" cy="7.5" r="1.1"/>',
    "overview": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.4 2.5 14.1 0 17M12 3.5c-2.5 2.4-2.5 14.1 0 17"/>',
    "results": '<rect x="3.5" y="4.5" width="17" height="15" rx="1.5"/><path d="M6.5 8.5h4M6.5 12h7M6.5 15.5h5"/>',
    "camera": '<rect x="3.5" y="7" width="17" height="12.5" rx="1.5"/><path d="M8.5 7l1.2-2.5h4.6L15.5 7"/><circle cx="12" cy="13" r="3.2"/>',
    "fullscreen": '<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/>',
    "dock_close": (
        '<path d="M7.85 6.15 17.85 16.15 16.15 17.85 6.15 7.85z" '
        'fill="currentColor" stroke="none"/>'
        '<path d="M16.15 6.15 17.85 7.85 7.85 17.85 6.15 16.15z" '
        'fill="currentColor" stroke="none"/>'
        '<circle cx="7" cy="7" r="1.2" fill="currentColor" stroke="none"/>'
        '<circle cx="17" cy="7" r="1.2" fill="currentColor" stroke="none"/>'
        '<circle cx="7" cy="17" r="1.2" fill="currentColor" stroke="none"/>'
        '<circle cx="17" cy="17" r="1.2" fill="currentColor" stroke="none"/>'
    ),
    "project_open": '<path d="M3 7.5A1.5 1.5 0 014.5 6h4l2 2.5h7A1.5 1.5 0 0119 10v1.5H6.2a1.5 1.5 0 00-1.45 1.1L3 19V7.5z"/><path d="M6.5 13.5h14l-2 6.5h-14l2-6.5z"/>',
    "project": '<path d="M9 4 3.5 6v14L9 18l6 2 5.5-2V4L15 6 9 4z"/>'
               '<path d="M9 4v14M15 6v14"/>',
    "map_street": '<path d="M3 6.5 9 4l6 2.5L21 4v13.5L15 20l-6-2.5L3 20V6.5z"/>'
                  '<path d="M9 4v13.5M15 6.5V20"/>'
                  '<path d="M5.5 9.5h2M12 10.5h2M16.5 9h2M5.5 14h2M12 15h2"/>',
    "map_satellite": '<rect x="9.2" y="9.2" width="5.6" height="5.6" rx="1"/>'
                     '<path d="M9.2 9.2 5.6 5.6M14.8 14.8l3.6 3.6"/>'
                     '<path d="M16.5 3.5a6.2 6.2 0 014 4M18.6 5.6a3.4 3.4 0 011.9 1.9"/>'
                     '<path d="M7.5 20.5a6.2 6.2 0 01-4-4M5.4 18.4a3.4 3.4 0 01-1.9-1.9"/>',
    "map_terrain": '<path d="M3 19l5.5-9 3.5 5.5L15 10l6 9H3z"/>'
                   '<circle cx="17.5" cy="6" r="1.6"/>',
    "map_topo": '<path d="M12 4.5c4.7 0 8 2.9 8 7s-3.3 8-8 8-8-3.9-8-8 3.3-7 8-7z"/>'
                '<path d="M12 8.5c2.6 0 4.5 1.5 4.5 3.5s-1.9 4-4.5 4-4.5-2-4.5-4 1.9-3.5 4.5-3.5z"/>'
                '<circle cx="12" cy="12.2" r="0.9" fill="currentColor" stroke="none"/>',
    "map_light": '<circle cx="12" cy="12" r="4"/>'
                 '<path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4"/>',
    "map_dark": '<path d="M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z"/>',
    "finish": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "cancel": '<path d="M7.2 7.2l9.6 9.6M16.8 7.2l-9.6 9.6"/>',
    "reset_edit": '<path d="M8.2 21.2H20"/>'
                  '<path d="M13.4 4.8l5.6 5.6a1.5 1.5 0 010 2.1l-6.5 6.5'
                  'a1.5 1.5 0 01-2.1 0l-5.6-5.6a1.5 1.5 0 010-2.1l6.5-6.5'
                  'a1.5 1.5 0 012.1 0z"/>'
                  '<path d="M8.8 15.1l3.4-3.4"/>',
    "feature_new": '<rect x="2.8" y="3" width="12.6" height="18" rx="1.8"/>'
                   '<circle cx="6.8" cy="7.6" r="1.5"/>'
                   '<path d="M9.6 7.6h3.6"/>'
                   '<path d="M4.8 13.2l1.35-2.2 1.35 2.2 1.35-2.2"/>'
                   '<path d="M9.6 12h2.6"/>'
                   '<rect x="5.3" y="14.9" width="3" height="3" rx="0.5"/>'
                   '<path d="M9.6 16.4h3.2"/>'
                   '<g transform="rotate(38 17.2 11.1)">'
                   '<path d="M15.4 13.6h3.6L17.2 17.2z" fill="currentColor"'
                   ' stroke="none"/>'
                   '<rect x="15.4" y="7.6" width="3.6" height="6" rx="0.3"/>'
                   '<rect x="15.4" y="5" width="3.6" height="2.6" rx="0.8"/>'
                   '</g>',
    "discard": '<path d="M5.5 6.5v11"/>'
               '<path d="M19 12H9.5"/>'
               '<path d="M13.5 7.5L9 12l4.5 4.5"/>',
    "database": '<ellipse cx="10" cy="6" rx="6.5" ry="2.8"/>'
                '<path d="M3.5 6v11c0 1.5 2.9 2.8 6.5 2.8s6.5-1.3 6.5-2.8V6"/>'
                '<path d="M3.5 11.5c0 1.5 2.9 2.8 6.5 2.8s6.5-1.3 6.5-2.8"/>'
                '<path d="M18.5 13.5v6M15.5 16.5h6"/>',
    "sel_rect": '<rect x="4" y="5" width="16" height="14" rx="1" stroke-dasharray="3 2.4"/>'
                '<path d="M10.5 11l3 7.6 1.4-3.4 3.4-1.2z" fill="currentColor" stroke="none"/>',
    "sel_poly": '<path d="M12 4l7 5-2.5 8h-9L5 9z" stroke-dasharray="3 2.4"/>'
                '<path d="M10.5 11l3 7.6 1.4-3.4 3.4-1.2z" fill="currentColor" stroke="none"/>',
    "sel_lasso": '<path d="M4 12c0-4.4 3.6-7 8-7s8 2.6 8 6.4c0 3.4-3 5.6-6.4 5.6-2.4 0-4.1-1-4.6-2.4"/>'
                 '<path d="M9 15c0 2.4 1 4.5 3 4.5s2-1.6 1.2-2.7"/>'
                 '<path d="M10.5 11l3 7.6 1.4-3.4 3.4-1.2z" fill="currentColor" stroke="none"/>',
    "sel_circle": '<circle cx="12" cy="12" r="8" stroke-dasharray="3 2.4"/>'
                  '<path d="M10.5 11l3 7.6 1.4-3.4 3.4-1.2z" fill="currentColor" stroke="none"/>',
    "sel_line": '<path d="M4 18L9 9l4 5 7-10" stroke-dasharray="3 2.4"/>'
                '<path d="M10.5 11l3 7.6 1.4-3.4 3.4-1.2z" fill="currentColor" stroke="none"/>',
    "sel_bylocation": '<path d="M4 4h4.5M4 4v4.5M20 4h-4.5M20 4v4.5M4 20h4.5M4 20v-4.5M20 20h-4.5M20 20v-4.5" stroke-dasharray="2.5 2.5"/>'
                      '<rect x="7.5" y="9.5" width="8" height="8" rx="0.8"/><circle cx="16" cy="7.5" r="2.8"/>',
    "coord_transform": '<path d="M5.2 9a8 8 0 0113.2-2.6"/><path d="M18.8 2.6v4h-4"/>'
                       '<path d="M18.8 15a8 8 0 01-13.2 2.6"/><path d="M5.2 21.4v-4h4"/>'
                       '<circle cx="12" cy="12" r="2.2"/>',
    "ins_point": '<circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none"/>'
                 '<path d="M12 2.5v4.2M12 17.3v4.2M2.5 12h4.2M17.3 12h4.2"/>',
    "ins_line": '<path d="M3.5 17.5L9 9.5l4.5 3L20.5 4"/>'
                '<circle cx="3.5" cy="17.5" r="1.7"/><circle cx="9" cy="9.5" r="1.7"/>'
                '<circle cx="13.5" cy="12.5" r="1.7"/><circle cx="20.5" cy="4" r="1.7"/>',
    "ins_poly": '<path d="M12 3.5l8 5.5-3 9.5H7.5L4 9z"/>'
                '<circle cx="12" cy="3.5" r="1.7"/><circle cx="20" cy="9" r="1.7"/>'
                '<circle cx="17" cy="18.5" r="1.7"/><circle cx="7.5" cy="18.5" r="1.7"/>'
                '<circle cx="4" cy="9" r="1.7"/>',
    "locate": '<circle cx="12" cy="12" r="6.2"/>'
              '<circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none"/>'
              '<path d="M12 2.6v3.4M12 18v3.4M2.6 12H6M18 12h3.4"/>',
    "lock": '<rect x="6" y="10.5" width="12" height="9" rx="1.5"/>'
            '<path d="M8.5 10.5V8a3.5 3.5 0 017 0v2.5"/>'
            '<circle cx="12" cy="15" r="1.2" fill="currentColor" stroke="none"/>',
    "lock_open": '<rect x="6" y="10.5" width="12" height="9" rx="1.5"/>'
                 '<path d="M8.5 10.5V8a3.5 3.5 0 016.9-0.9"/>'
                 '<circle cx="12" cy="15" r="1.2" fill="currentColor" stroke="none"/>',
    "chevron_up": '<path d="M6 14.5L12 8.5l6 6"/>',
    "chevron_down": '<path d="M6 9.5l6 6 6-6"/>',
    "sample": '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.8"/><path d="M4.5 5.5v13c0 1.55 3.36 2.8 7.5 2.8s7.5-1.25 7.5-2.8v-13"/><path d="M4.5 12c0 1.55 3.36 2.8 7.5 2.8s7.5-1.25 7.5-2.8"/>',
    "processing": '<path d="M20.5 6.7a5 5 0 01-6.6 6.3l-6.5 6.5a2 2 0 01-2.9-2.9l6.5-6.5a5 5 0 016.3-6.6l-3 3 2.9 2.9 3-3z"/>',
    "color_swatch": '<rect x="3.5" y="3.5" width="8" height="8" rx="1.2"/><rect x="12.5" y="3.5" width="8" height="8" rx="1.2"/><rect x="3.5" y="12.5" width="8" height="8" rx="1.2"/><path d="M16.5 12.8l3.7 3.7a1.7 1.7 0 010 2.4l-1.3 1.3a1.7 1.7 0 01-2.4 0l-3.7-3.7z"/>',
    "opacity": '<rect x="3.5" y="8" width="10" height="10" rx="1"/><rect x="9" y="4.5" width="11" height="9" rx="1" stroke-dasharray="2.6 2.2"/>',
    "fill": '<path d="M12 3l7.5 7.5a1.5 1.5 0 010 2.2l-6.3 6.3a1.9 1.9 0 01-2.7 0L4.3 12.8a1.5 1.5 0 010-2.2L9.8 5z"/><path d="M5.5 11.5h13"/><path d="M20.5 16.5c.9 1.3 1.5 2.3 1.5 3a1.5 1.5 0 01-3 0c0-.7.6-1.7 1.5-3z" fill="currentColor" stroke="none"/>',
    "style_library": ('<path d="M12 3.6c4.6 0 8.4 3.3 8.4 7.4 0 2.6-1.9 3.9'
                      '-3.6 4.1-1.5.2-2.4.6-2.4 1.8 0 1.3 1 1.9 1 3.1 0 .9'
                      '-.9 1.4-2 1.4-4.8 0-9.8-4.5-9.8-9.1 0-4.4 3.9-8.7 '
                      '8.4-8.7z"/>'
                      '<circle cx="8.2" cy="10.2" r="1.25" '
                      'fill="currentColor" stroke="none"/>'
                      '<circle cx="12.4" cy="7.6" r="1.25" '
                      'fill="currentColor" stroke="none"/>'
                      '<circle cx="16.4" cy="10.8" r="1.25" '
                      'fill="currentColor" stroke="none"/>'),
    "stroke": '<circle cx="12" cy="12" r="7.5" stroke-width="1.8"/><path d="M19.5 4.5l1 1" stroke-width="1.6"/>',
    "label": '<path d="M3.5 11V5.5a1.5 1.5 0 011.5-1.5h5.5L20 13.5a1.5 1.5 0 010 2.2l-5.3 5.3a1.5 1.5 0 01-2.2 0L3.5 11z"/><circle cx="8" cy="8" r="1.2"/>',
    "checkbox_on": ('<rect x="4" y="4" width="16" height="16" rx="3"/>'
                    '<path d="M8 12.4l2.6 2.6L16.2 9.2"/>'),
    "checkbox_off": '<rect x="4" y="4" width="16" height="16" rx="3"/>',
    "stretch": '<path d="M4 19c6 0 4-14 10-14h6"/><path d="M17 2.5L20 5l-3 2.5"/><path d="M7 16.5L4 19l3 2.5"/>',
    "rgb": '<circle cx="9" cy="9" r="4.2"/><circle cx="15" cy="9" r="4.2"/><circle cx="12" cy="14.5" r="4.2"/>',
    "stats": '<path d="M4 20V10M9.5 20V4.5M15 20v-8M20.5 20V7"/><path d="M3 20.5h18"/>',
    "export": '<rect x="3.5" y="8.5" width="12" height="12" rx="1.5"/><path d="M7.5 8.5V6a1.5 1.5 0 011.5-1.5h9.5A1.5 1.5 0 0120 6v9.5a1.5 1.5 0 01-1.5 1.5H16"/><path d="M16.5 3.5L20 7l-3.5 3.5"/>',
    "pause": '<path d="M9.5 5.5v13M14.5 5.5v13"/>',
    "render": '<path d="M19.5 12a7.5 7.5 0 11-2.2-5.3"/><path d="M19.7 3.8v4.4h-4.4"/>',
    "undo": '<path d="M4 8.5h8.5a5.5 5.5 0 010 11H8"/><path d="M8 4.5L4 8.5l4 4"/>',
    "redo": '<path d="M20 8.5h-8.5a5.5 5.5 0 000 11H16"/><path d="M16 4.5l4 4-4 4"/>',
    "select_attr": '<path d="M4 4h4.5M4 4v4.5M20 4h-4.5M20 4v4.5M4 20h4.5M4 20v-4.5M20 20h-4.5M20 20v-4.5" stroke-dasharray="2.5 2.5"/><path d="M8.5 10.5h7M8.5 13.5h4.5"/>',
    "deselect": '<path d="M4 4h4.5M4 4v4.5M20 4h-4.5M20 4v4.5M4 20h4.5M4 20v-4.5M20 20h-4.5M20 20v-4.5" stroke-dasharray="2.5 2.5"/><path d="M9.5 9.5l5 5M14.5 9.5l-5 5"/>',
    "invert_sel": '<path d="M4 4h4.5M4 4v4.5M20 20h-4.5M20 20v-4.5" stroke-dasharray="2.5 2.5"/><rect x="9.5" y="9.5" width="5" height="5" rx="0.8"/><path d="M14 4.5h5.5V10M5 19.5H4.5"/>' ,
    "recent": '<path d="M4.5 12a7.5 7.5 0 112.2 5.3"/><path d="M4.3 20.2v-4.4h4.4"/><path d="M12 8.5V12l2.6 1.6"/>',
    "compass": '<circle cx="12" cy="12" r="8.5"/><path d="M14.8 9.2l-2 5.6-3.6 0 5.6-5.6z"/><circle cx="12" cy="12" r="0.9" fill="currentColor" stroke="none"/>',
    "project_btn": '<path d="M3 7.5A1.5 1.5 0 014.5 6h4l2 2.5h7A1.5 1.5 0 0119 10v7.5a1.5 1.5 0 01-1.5 1.5h-13A1.5 1.5 0 013 17.5v-10z"/><circle cx="15.5" cy="15" r="3.4"/>',
    "copy_path": '<rect x="8.5" y="3.5" width="11" height="14" rx="1.5"/><path d="M11.5 7.5h5M11.5 10.5h5"/><path d="M3.5 19.5h7"/><path d="M14.5 17l2.5 2.5-2.5 2.5"/>',
    "units": '<rect x="2.5" y="8" width="19" height="8" rx="1.5"/><path d="M7 8v3M10.5 8v4.5M14 8v3M17.5 8v4.5"/>',
    "model": '<rect x="3" y="3" width="7" height="5.5" rx="1.2"/>'
             '<rect x="14" y="15.5" width="7" height="5.5" rx="1.2"/>'
             '<path d="M6.5 8.5v5a2 2 0 002 2H14"/>'
             '<circle cx="6.5" cy="8.5" r="1.1" fill="currentColor" stroke="none"/>'
             '<circle cx="14" cy="15.5" r="1.1" fill="currentColor" stroke="none"/>',
    "expression": '<path d="M13.5 4.5c-.8-.7-1.9-1-3-.6C9 4.4 8.2 5.7 8 7.2L6.6 16.5c-.3 1.8-1.2 3-3.1 3"/>'
                  '<path d="M5 11.5h8.5"/>'
                  '<path d="M14.5 11.5l5.5 8.5M20 11.5L14.5 20"/>',
    "histogram": '<path d="M3.5 3.5v17h17"/><path d="M7 20.5v-6"/><path d="M12 20.5V9"/><path d="M17 20.5v-9.5"/>',
    "spectrum": '<path d="M3 20.5C6 17 9 13 12 13s6 3 9 4.5"/>'
                '<path d="M3 16C6 12 9 8 12 8s6-2 9-3.5"/>'
                '<path d="M3 12.5C6 9 9 5 12 5s6 1 9 0"/>',
    "basemap_main": '<path d="M3 6l6-2.5 6 2.5 6-2.5v14l-6 2.5-6-2.5-6 2.5z"/>'
                    '<path d="M9 3.5v14"/>'
                    '<path d="M15 6v14"/>',
    "add_data_main": '<path d="M12 3.5 20 7.2 12 10.9 4 7.2 Z"/>'
                     '<path d="M4 7.2v5.2l8 3.7 8-3.7V7.2"/>'
                     '<path d="M19.2 14.6v6.2M16.1 17.7h6.2"/>',
    "cut_features": '<circle cx="6" cy="6" r="2.7"/>'
                    '<circle cx="6" cy="18" r="2.7"/>'
                    '<path d="M8.2 8.2L12 12"/>'
                    '<path d="M20 4.5L8.2 16.3"/>'
                    '<path d="M14.6 14.6L20 20"/>',
    "copy_features": '<rect x="8.6" y="8.6" width="11" height="11" rx="1.6"/>'
                     '<path d="M6 15.4V5.6A1.6 1.6 0 017.6 4h9.8"/>',
    "paste_features": '<path d="M15.6 4.6h2.4A1.4 1.4 0 0119.4 6v13.6a1.4 1.4 0 '
                      '01-1.4 1.4H6A1.4 1.4 0 014.6 19.6V6a1.4 1.4 0 011.4-1.4h2.4"/>'
                      '<rect x="9.3" y="3" width="5.4" height="3.2" rx="1"/>'
                      '<path d="M8.6 10.4h6.8M8.6 13.6h4.6"/>',
    "paste_special": '<rect x="3.4" y="4.8" width="10.6" height="15.2" rx="1.4"/>'
                     '<rect x="6.4" y="3.4" width="4.6" height="2.8" rx="0.9"/>'
                     '<path d="M6 11.4h5.4M6 14.6h3.6"/>'
                     '<path d="M16.8 9.4h4.6M16.8 12.6h4.6M16.8 15.8h4.6"/>',
    "add": '<rect x="4" y="4" width="16" height="16" rx="3.2"/>'
           '<path d="M12 8.6v6.8M8.6 12h6.8"/>',
    "plus": '<path d="M12 5.2v13.6M5.2 12h13.6" stroke-width="2.2"/>',
    "folder": '<path d="M3 7.5A1.5 1.5 0 014.5 6h4l2 2.5h7A1.5 1.5 0 0119 10'
              'v7.5a1.5 1.5 0 01-1.5 1.5h-13A1.5 1.5 0 013 17.5v-10z"/>',
    "folder_add": '<path d="M3 7.5A1.5 1.5 0 014.5 6h4l2 2.5h7A1.5 1.5 0 0119 10'
                  'v7.5a1.5 1.5 0 01-1.5 1.5h-13A1.5 1.5 0 013 17.5v-10z"/>'
                  '<path d="M11.6 11.4v5.2M9 14h5.2"/>',
    "arrow_up": '<path d="M12 19.5V5.5"/><path d="M6.5 11L12 5.5 17.5 11"/>'
                '<path d="M4.5 20.5h15"/>',
    "arrow_down": '<path d="M12 4.5v14"/><path d="M6.5 13L12 18.5 17.5 13"/>'
                  '<path d="M4.5 3.5h15"/>',
    "arrange_up": '<rect x="3.6" y="13.4" width="16.8" height="7.2" rx="1.4"/>'
                  '<path d="M12 10.2V2.6"/>'
                  '<path d="M8.4 6.2L12 2.6 15.6 6.2"/>',
    "arrange_down": '<rect x="3.6" y="3.4" width="16.8" height="7.2" rx="1.4"/>'
                    '<path d="M12 13.8v7.6"/>'
                    '<path d="M8.4 17.8L12 21.4 15.6 17.8"/>',
    "distribute": '<rect x="2.6" y="9" width="4.8" height="6" rx="1.2"/>'
                  '<rect x="9.6" y="9" width="4.8" height="6" rx="1.2"/>'
                  '<rect x="16.6" y="9" width="4.8" height="6" rx="1.2"/>',
    "delete": '<rect x="4" y="4" width="16" height="16" rx="3.2"/>'
              '<path d="M8.6 8.6l6.8 6.8M15.4 8.6l-6.8 6.8"/>',
    "stop": '<circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" '
            'stroke-width="2"/>'
            '<rect x="8.4" y="8.4" width="7.2" height="7.2" rx="1.4" '
            'fill="#d4553f" stroke="none"/>',

    "crs_enabled": '<path d="M6.6 4h12.4l-2.4 10.8H4.2z"/>'
                   '<path d="M5.8 7.6h12.4M5 11.2h12.4"/>'
                   '<path d="M10.6 4l-2.4 10.8M15 4l-2.4 10.8"/>'
                   '<path d="M14.5 16.5l2.2 2.2 4.3-5.4"/>',
    "crs_disabled": '<circle cx="12" cy="12" r="7.3"/>'
                    '<path d="M4.7 12h14.6M12 4.7c2.1 2 2.1 12.6 0 14.6'
                    'M12 4.7c-2.1 2-2.1 12.6 0 14.6"/>'
                    '<path d="M7.1 16.9l9.8-9.8"/>',
    "new_crs": '<circle cx="9" cy="9" r="6.8"/>'
               '<path d="M2.2 9h13.6M9 2.2v13.6"/>'
               '<circle cx="16.9" cy="16.9" r="5.1"/>'
               '<path d="M16.9 13.7v6.4M13.7 16.9h6.4" stroke-width="2"/>',
    "confirm": '<circle cx="12" cy="12" r="8.4"/>'
               '<path d="M8.1 12.3l2.7 2.7 5.3-6"/>',
    "render_done": (
        '<circle cx="12" cy="12" r="7.5" fill="none" stroke="currentColor" '
        'stroke-width="1.4"/>'
        '<path d="M8.2 12.2 11 14.9 15.8 9" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'),
    "clear": '<circle cx="12" cy="12" r="8.4"/>'
             '<path d="M9.3 9.3l5.4 5.4M14.7 9.3l-5.4 5.4"/>',
    "log_clear": '<path d="M4.6 6.6h14.8"/>'
                 '<path d="M9.6 6.6V4.9h4.8v1.7"/>'
                 '<path d="M6.8 6.6l1 12.9h8.4l1-12.9"/>'
                 '<path d="M10.2 10.4v5.8M13.8 10.4v5.8"/>',
    "broom": '<path d="M20 4L12 12"/>'
             '<path d="M10.8 10.8L5.7 13.5Q8.1 17.5 10.5 18.3L13.2 13.2z"/>',
    "merge_features": '<path d="M4 4.6h4.4v4.6H4zM4 14.8h4.4v4.6H4z"/>'
                      '<path d="M9.6 12h3.9"/>'
                      '<path d="M16.2 6.6h3.9v11.8h-3.9z"/>',
    "filter": '<path d="M3.9 5.5h16.2l-6.1 7.5v5.4l-4 2.6v-8z"/>',
    "export_raster": '<rect x="3.5" y="5.6" width="10.8" height="10.8" '
                     'rx="1.2"/>'
                     '<path d="M3.5 11h10.8M8.9 5.6v10.8"/>'
                     '<path d="M16.2 11h4.3M18.2 8.9l2.3 2.1-2.3 2.1"/>',
    "input_file": '<path d="M13.4 3.6H6.9A1.4 1.4 0 0 0 5.5 5v14'
                  'A1.4 1.4 0 0 0 6.9 20.4h10.2a1.4 1.4 0 0 0 '
                  '1.4-1.4V8.6z"/>'
                  '<path d="M13.4 3.6v5h5.1"/>'
                  '<path d="M9.4 13.2h5.2M12.3 10.6l2.3 2.6-2.3 2.6"/>',
    "intersection": '<path d="M3.6 7.8l16.8 8.4M3.6 16.2l16.8-8.4"/>'
                    '<circle cx="12" cy="12" r="2.3" fill="currentColor" '
                    'stroke="none"/>',
    "notices": '<path d="M13.4 3.6H6.9A1.4 1.4 0 0 0 5.5 5v14'
               'A1.4 1.4 0 0 0 6.9 20.4h10.2a1.4 1.4 0 0 0 '
               '1.4-1.4V8.6z"/>'
               '<path d="M13.4 3.6v5h5.1"/>'
               '<path d="M8.6 12.2h6.8M8.6 15.4h4.6"/>'
               '<circle cx="18.4" cy="18.4" r="3.6"/>'
               '<path d="M16.8 18.4l1.1 1.1 2.2-2.5"/>',
    "query": '<rect x="3.5" y="4.6" width="16.8" height="14.8" rx="1.4"/>'
             '<path d="M3.5 9.1h16.8"/>'
             '<circle cx="13.6" cy="14.3" r="3"/>'
             '<path d="M15.8 16.5l3.4 3.4"/>',
    "to_excel": '<rect x="3.5" y="4.6" width="11.4" height="14.8" rx="1.4"/>'
                '<path d="M3.5 9.5h11.4M3.5 14.4h11.4"/>'
                '<path d="M7.3 4.6v14.8"/>'
                '<path d="M17.2 12h4.3M19.2 9.9l2.3 2.1-2.3 2.1"/>',
    "union": '<path d="M4 6.6h7.2v5.8H17v6H4z"/>',

    "about": '<circle cx="12" cy="12" r="8.5"/>'
             '<path d="M12 11.2v5.3"/><path d="M12 7.9h.01"/>',
    "clipboard_copy": '<rect x="9.2" y="7.4" width="11.4" height="12.6" rx="1.7"/>'
                      '<path d="M12.6 4.6H6.2a1.9 1.9 0 0 0-1.9 1.9v9.4'
                      'a1.9 1.9 0 0 0 1.9 1.9h1.4"/>',
    "license": '<path d="M12 3.4l6.6 2.5v5.3c0 4-2.7 6.9-6.6 8.4'
               '-3.9-1.5-6.6-4.4-6.6-8.4V5.9z"/>'
               '<path d="M9.3 11.8l2 2 3.5-3.7"/>',
    "chip": '<rect x="7.4" y="7.4" width="9.2" height="9.2" rx="1.5"/>'
            '<path d="M10.4 3.6v3.8M13.6 3.6v3.8M10.4 16.6v3.8M13.6 16.6v3.8'
            'M3.6 10.4h3.8M3.6 13.6h3.8M16.6 10.4h3.8M16.6 13.6h3.8"/>',
    "modules": '<rect x="3.8" y="3.8" width="6.8" height="6.8" rx="1.4"/>'
               '<rect x="13.4" y="3.8" width="6.8" height="6.8" rx="1.4"/>'
               '<rect x="3.8" y="13.4" width="6.8" height="6.8" rx="1.4"/>'
               '<rect x="13.4" y="13.4" width="6.8" height="6.8" rx="1.4"/>',

    "calc": '<rect x="5" y="3.5" width="14" height="17" rx="2"/>'
            '<path d="M8 7.5h8"/>'
            '<circle cx="9" cy="12" r="1.1" fill="currentColor" stroke="none"/>'
            '<circle cx="13" cy="12" r="1.1" fill="currentColor" stroke="none"/>'
            '<circle cx="17" cy="12" r="1.1" fill="currentColor" stroke="none"/>'
            '<circle cx="9" cy="16" r="1.1" fill="currentColor" stroke="none"/>'
            '<circle cx="13" cy="16" r="1.1" fill="currentColor" stroke="none"/>'
            '<circle cx="17" cy="16" r="1.1" fill="currentColor" stroke="none"/>',
    "new_attr": '<rect x="3.5" y="5" width="15" height="14" rx="1.5"/>'
                '<path d="M3.5 9.5h15M3.5 14h15M9 9.5V19"/>'
                '<path d="M17 2.5v4.5M15 4.5h4" stroke-width="1.8"/>',
    "chevron_left": '<path d="M14 6l-6 6 6 6"/>',
    "chevron_right": '<path d="M10 6l6 6-6 6"/>',

    "point_on_surface":
        '<path d="M4.5 17.5l4.5-8.5 6 3 4-4.5v10z" '
        'fill="currentColor" stroke="none" opacity="0.16"/>'
        '<path d="M4.5 17.5l4.5-8.5 6 3 4-4.5v10z"/>'
        '<circle cx="12" cy="12.6" r="1.7" fill="currentColor" '
        'stroke="none"/>',
    "concave_hull":
        '<path d="M5 16.5l4-7 3.2 3L16 5l3.5 11z" '
        'fill="currentColor" stroke="none" opacity="0.16"/>'
        '<path d="M5 16.5l4-7 3.2 3L16 5l3.5 11z"/>'
        '<circle cx="5" cy="16.5" r="1.15" fill="currentColor" '
        'stroke="none"/>'
        '<circle cx="9" cy="9.5" r="1.15" fill="currentColor" '
        'stroke="none"/>'
        '<circle cx="16" cy="5" r="1.15" fill="currentColor" '
        'stroke="none"/>'
        '<circle cx="19.5" cy="16" r="1.15" fill="currentColor" '
        'stroke="none"/>',
    "oriented_envelope":
        '<path d="M6.5 5.2L20.6 10.3 17.5 18.8 3.4 13.7z" '
        'fill="currentColor" stroke="none" opacity="0.14"/>'
        '<path d="M6.5 5.2L20.6 10.3 17.5 18.8 3.4 13.7z"/>'
        '<circle cx="10" cy="10" r="1.15" fill="currentColor" '
        'stroke="none"/>'
        '<circle cx="14" cy="11.5" r="1.15" fill="currentColor" '
        'stroke="none"/>'
        '<circle cx="12" cy="14.5" r="1.15" fill="currentColor" '
        'stroke="none"/>',
    "minimum_bounding_circle":
        '<circle cx="12" cy="12" r="8"/>'
        '<circle cx="12" cy="4" r="1.25" fill="currentColor" '
        'stroke="none"/>'
        '<circle cx="18.9" cy="16" r="1.25" fill="currentColor" '
        'stroke="none"/>'
        '<circle cx="5.1" cy="16" r="1.25" fill="currentColor" '
        'stroke="none"/>',
    "maximum_inscribed_circle":
        '<path d="M5 18L9.5 6.5h8L19 18z" fill="currentColor" '
        'stroke="none" opacity="0.14"/>'
        '<path d="M5 18L9.5 6.5h8L19 18z"/>'
        '<circle cx="12.75" cy="12.6" r="4.6" stroke-dasharray="2.6 2.2"/>'
        '<circle cx="12.75" cy="12.6" r="1.2" fill="currentColor" '
        'stroke="none"/>',
    "boundary":
        '<path d="M4.5 17.5l4.5-8.5 6 3 4-4.5v10z" '
        'fill="currentColor" stroke="none" opacity="0.13"/>'
        '<path d="M4.5 17.5l4.5-8.5 6 3 4-4.5v10z" stroke-width="1.8"/>',
    "exterior_ring":
        '<path d="M4.5 18L8 6.5h8l3.5 11.5z"/>'
        '<path d="M9.3 15.5l1.8-4.6h2.6l1.6 4.6z" '
        'stroke-dasharray="2.2 1.8"/>',
    "extract_by_type":
        '<circle cx="5.6" cy="6.2" r="1.5" opacity="0.4"/>'
        '<path d="M4 17.5l4.5-5 4 3.5L19.5 8.5" opacity="0.4"/>'
        '<path d="M9.5 9l5.5-2.5 5 5.5-5.5 5z" '
        'fill="currentColor" stroke="none" opacity="0.2"/>'
        '<path d="M9.5 9l5.5-2.5 5 5.5-5.5 5z"/>',
    "to_multipart":
        '<circle cx="6.8" cy="8" r="2.9"/>'
        '<circle cx="17.2" cy="16" r="2.9"/>'
        '<path d="M10.4 10.6l3 3" opacity="0.55"/>'
        '<path d="M13.4 13.6l-2.3 0.5M13.4 13.6l-0.5-2.3" '
        'stroke-width="1"/>',
    "shortest_line":
        '<circle cx="5.8" cy="16.8" r="2.7"/>'
        '<rect x="13" y="4.6" width="7.6" height="7.6" rx="1"/>'
        '<path d="M8.1 14.7L15.2 8.6" stroke-width="1.7"/>',
    "remove_repeated_points":
        '<path d="M4 18l5-7 4.5 3.5L20 6.5"/>'
        '<circle cx="9" cy="11" r="2.7" stroke-dasharray="2 1.5" '
        'opacity="0.65"/>'
        '<circle cx="9" cy="11" r="1.25" fill="currentColor" '
        'stroke="none"/>',
    "snap":
        '<path d="M4 18l5-6 4 3.5 6.5-8" opacity="0.4"/>'
        '<circle cx="9" cy="12" r="1.5" fill="currentColor" '
        'stroke="none"/>'
        '<path d="M15.8 6.4L9 12" stroke-dasharray="2.2 1.8"/>'
        '<circle cx="15.8" cy="6.4" r="1.5"/>',
    "offset_curve":
        '<path d="M4.5 19.8L9.5 13.3l4 2.5L19 8.8" opacity="0.5"/>'
        '<path d="M4.5 13.2L9.5 6.7l4 2.5L19 2.2" opacity="0.5"/>'
        '<path d="M4.5 16.5L9.5 10l4 2.5L19 5.5" stroke-width="1.7"/>',
    "translate":
        '<rect x="3.5" y="6" width="8.5" height="8.5" rx="1" '
        'stroke-dasharray="2.4 2" opacity="0.55"/>'
        '<rect x="12" y="6" width="8.5" height="8.5" rx="1"/>'
        '<path d="M7.5 18.5h9" opacity="0.7"/>'
        '<path d="M13.8 17.2l2.2 1.3-2.2 1.3" stroke-width="1"/>',
    "scale":
        '<rect x="4" y="4" width="16" height="16" rx="1.2" '
        'stroke-dasharray="2.6 2.2" opacity="0.55"/>'
        '<rect x="8.5" y="8.5" width="7" height="7" rx="1"/>'
        '<path d="M12 2.2v3.3M12 18.5v3.3M2.2 12h3.3M18.5 12h3.3" '
        'stroke-width="1.1"/>',
    "rotate":
        '<rect x="7.2" y="7.2" width="9.6" height="9.6" rx="1.2" '
        'fill="currentColor" stroke="none" opacity="0.16"/>'
        '<rect x="7.2" y="7.2" width="9.6" height="9.6" rx="1.2"/>'
        '<path d="M9.5 4.5A5 5 0 0 0 4.5 9.5"/>'
        '<path d="M4.5 9.5L3.2 8M4.5 9.5L5.8 8" stroke-width="1"/>',
    "reverse":
        '<path d="M4.5 17.5L10 8l4.5 3.5L20 6.5"/>'
        '<path d="M4.5 17.5l2.9-0.5M4.5 17.5l0.5-2.9" stroke-width="1"/>'
        '<path d="M17.2 9.2l2.8-2.7-3.5-1.1" opacity="0.45"/>',
    "orient_polygons":
        '<path d="M5 17L9.5 7h8.5L19 17z" fill="currentColor" '
        'stroke="none" opacity="0.15"/>'
        '<path d="M5 17L9.5 7h8.5L19 17z"/>'
        '<path d="M15.2 13.6a2.8 2.8 0 1 1 0-2.8"/>'
        '<path d="M12.4 10.8l-1.3 0.9M12.4 10.8l0.4 1.6" '
        'stroke-width="1"/>',
    "line_merge":
        '<path d="M4 18L7.8 13.9" opacity="0.5"/>'
        '<path d="M10.2 11.1L20 6" opacity="0.5"/>'
        '<path d="M4 18L7.8 13.9L10.2 11.1L20 6" stroke-width="1.7"/>'
        '<circle cx="10.2" cy="11.1" r="1.2" fill="currentColor" '
        'stroke="none"/>',
    "build_area":
        '<path d="M5 16.5l4.5-8.5 6 3 4-4.5v11z" '
        'fill="currentColor" stroke="none" opacity="0.15"/>'
        '<path d="M5 16.5l4.5-8.5 6 3 4-4.5" stroke-width="1.7"/>'
        '<path d="M19.5 11v6.5" opacity="0.5"/>'
        '<path d="M19.5 17.5l-1.7-2.1M19.5 17.5l1.4-2" '
        'stroke-width="1"/>',
    "node":
        '<path d="M4 19L20 5.5"/>'
        '<path d="M4.5 6.5L19.5 18.5"/>'
        '<circle cx="12" cy="12.2" r="2.3" stroke-dasharray="2 1.5" '
        'opacity="0.7"/>'
        '<circle cx="12" cy="12.2" r="1.15" fill="currentColor" '
        'stroke="none"/>',
    "clip_by_rect":
        '<path d="M4 6l16 2-2 12-12-2z" opacity="0.35"/>'
        '<rect x="8" y="8" width="8" height="8" rx="0.8" '
        'fill="currentColor" stroke="none" opacity="0.2"/>'
        '<rect x="8" y="8" width="8" height="8" rx="0.8"/>',
    "area_field":
        '<path d="M4.5 17.5l4.5-8.5 6 3 4-4.5v10z" '
        'fill="currentColor" stroke="none" opacity="0.18"/>'
        '<path d="M4.5 17.5l4.5-8.5 6 3 4-4.5v10z"/>'
        '<path d="M7.5 15.2l3-3.8M10.8 15.8l3.4-4M14 16.2l3-3.6" '
        'opacity="0.45"/>',
    "length_field":
        '<path d="M4.5 12.5l6-6.5 4.5 3.5L20 5.5" stroke-width="1.6"/>'
        '<path d="M4.5 17.8h15" opacity="0.55"/>'
        '<path d="M4.5 16.4v2.8M19.5 16.4v2.8" stroke-width="1"/>',
    "perimeter_field":
        '<path d="M5 16.5l4.5-8.5 6 3 4-4.5v10z" '
        'fill="currentColor" stroke="none" opacity="0.15"/>'
        '<path d="M5 16.5l4.5-8.5 6 3 4-4.5v10z" stroke-width="1.7"/>'
        '<path d="M8 20.6h8" opacity="0.55"/>'
        '<path d="M8 19.2v2.8M16 19.2v2.8" stroke-width="1"/>',
    "num_points_field":
        '<path d="M4 18L9 11l4.5 3.5L20 6.5" opacity="0.4"/>'
        '<path d="M6.2 15.2L9 11l2.8 2.2" stroke-width="1.8"/>'
        '<circle cx="9" cy="11" r="2.4" stroke-dasharray="2 1.5"/>',
    "num_geometries_field":
        '<rect x="3" y="3.5" width="18" height="17" rx="1.5" '
        'stroke-dasharray="2.6 2.2" opacity="0.5"/>'
        '<circle cx="7.6" cy="8.2" r="3.6"/>'
        '<circle cx="16" cy="15.6" r="3.6"/>'
        '<circle cx="7.6" cy="8.2" r="1.2" fill="currentColor" '
        'stroke="none"/>'
        '<circle cx="16" cy="15.6" r="1.2" fill="currentColor" '
        'stroke="none"/>',
    "num_rings_field":
        '<path d="M4 18L7.5 6h9L20 18z"/>'
        '<path d="M9 15.5l1.8-4.5h2.4l1.8 4.5z"/>'
        '<circle cx="12" cy="10.4" r="1.35"/>',
    "minimum_clearance_field":
        '<circle cx="6.8" cy="12" r="3.6"/>'
        '<circle cx="17.2" cy="12" r="3.6"/>'
        '<path d="M10.9 12h5.6" stroke-dasharray="2.2 1.8"/>'
        '<path d="M10.9 12l1.7-1.1M10.9 12l1.7 1.1M16.5 12l-1.7-1.1'
        'M16.5 12l-1.7 1.1" stroke-width="1"/>',
    "circularity_field":
        '<circle cx="12" cy="12" r="7"/>'
        '<path d="M19 12L16.2 16.2 12 19.5 7.9 16.1 4.8 12 7.2 7.8 '
        '12 4.6 17.2 7.5z" stroke-dasharray="2.4 2" opacity="0.65"/>',
    "intersects_field":
        '<circle cx="9.5" cy="12" r="5.5"/>'
        '<rect x="12.5" y="6.5" width="8.5" height="11" rx="1"/>'
        '<circle cx="12.9" cy="12" r="1.25" fill="currentColor" '
        'stroke="none"/>',
    "overlaps_field":
        '<circle cx="9" cy="12" r="5.5"/>'
        '<circle cx="15" cy="12" r="5.5"/>'
        '<path d="M12 7.4A5.5 5.5 0 0 0 12 16.6A5.5 5.5 0 0 0 12 7.4z" '
        'fill="currentColor" stroke="none" opacity="0.3"/>',
    "crosses_field":
        '<path d="M4.5 19.5L20 4.5" stroke-width="1.6"/>'
        '<rect x="6.5" y="8" width="11" height="8.5" rx="1"/>',
    "touches_field":
        '<circle cx="8" cy="12" r="4.5"/>'
        '<rect x="12.5" y="6" width="8.5" height="12" rx="1"/>',
    "contains_field":
        '<circle cx="12" cy="12" r="8.5"/>'
        '<circle cx="12" cy="12" r="3.2" fill="currentColor" '
        'stroke="none" opacity="0.3"/>'
        '<circle cx="12" cy="12" r="3.2"/>',
    "within_field":
        '<rect x="4" y="4.5" width="16" height="15" rx="1.5"/>'
        '<circle cx="12" cy="12" r="3.6" fill="currentColor" '
        'stroke="none" opacity="0.3"/>'
        '<circle cx="12" cy="12" r="3.6"/>',
    "covers_field":
        '<circle cx="12" cy="12" r="8.5"/>'
        '<circle cx="12" cy="6.1" r="2.6"/>',
    "covered_by_field":
        '<circle cx="12" cy="12" r="8.5"/>'
        '<rect x="8.5" y="3.5" width="7" height="4" rx="0.8"/>',
    "equals_field":
        '<circle cx="10.5" cy="12" r="7"/>'
        '<circle cx="13.5" cy="12" r="7" stroke-dasharray="2.4 2" '
        'opacity="0.7"/>',
    "disjoint_field":
        '<circle cx="6.5" cy="12" r="3.8"/>'
        '<rect x="13.5" y="8.2" width="7" height="7.6" rx="1"/>',
    "dwithin_field":
        '<circle cx="8" cy="12" r="3.2"/>'
        '<circle cx="8" cy="12" r="7" stroke-dasharray="2.6 2.2" '
        'opacity="0.6"/>'
        '<circle cx="17.6" cy="12" r="2.7"/>',
    "distance_field":
        '<circle cx="6" cy="9" r="2.8"/>'
        '<rect x="13.5" y="13" width="7" height="7" rx="1"/>'
        '<path d="M7.6 10.7L15.4 15.4" stroke-dasharray="2.4 2"/>'
        '<path d="M7.6 10.7L6.23 10.64M7.6 10.7L6.91 9.52'
        'M15.4 15.4L16.77 15.46M15.4 15.4L16.09 16.1" '
        'stroke-width="1"/>',
    "union_layer":
        '<rect x="3.5" y="5" width="9" height="9" rx="1" '
        'stroke-dasharray="2.4 2" opacity="0.5"/>'
        '<rect x="8" y="9.5" width="9" height="9" rx="1" '
        'stroke-dasharray="2.4 2" opacity="0.5"/>'
        '<path d="M3.5 5h9v4.5H17v9H8V14H3.5z" '
        'fill="currentColor" stroke="none" opacity="0.18"/>'
        '<path d="M3.5 5h9v4.5H17v9H8V14H3.5z"/>',
    "collect":
        '<circle cx="5" cy="6.8" r="1.8"/>'
        '<circle cx="18.2" cy="8" r="1.8"/>'
        '<circle cx="6.2" cy="17.6" r="1.8"/>'
        '<rect x="9.6" y="9.6" width="5.4" height="5.4" rx="1" '
        'stroke-dasharray="2.2 1.8"/>'
        '<path d="M6.7 8.3l1.8 1.8M16.9 9.4l-1.7 1.6M7.8 16.4l1.6-1.5" '
        'opacity="0.6"/>',
    "extent_layer":
        '<rect x="3.5" y="4.5" width="10" height="9" rx="1" '
        'stroke-dasharray="2.4 2" opacity="0.55"/>'
        '<rect x="9.5" y="10" width="11" height="9.5" rx="1" '
        'stroke-dasharray="2.4 2" opacity="0.55"/>'
        '<rect x="3.5" y="4.5" width="17" height="15" rx="1"/>',
    "coverage_union":
        '<path d="M4 5h13v13H4z" fill="currentColor" '
        'stroke="none" opacity="0.16"/>'
        '<path d="M4 5h13v13H4z"/>'
        '<path d="M10.5 5v13M4 11.5h13" opacity="0.4"/>',
    "slope":
        '<path d="M4 19h16"/>'
        '<path d="M4 19L19 7"/>'
        '<path d="M19 7v12" stroke-dasharray="2 2"/>',
    "aspect":
        '<circle cx="12" cy="12" r="8"/>'
        '<path d="M12 4l3 8-3-2-3 2z" fill="currentColor" stroke="none"/>',
    "hillshade":
        '<path d="M3 19h18"/>'
        '<path d="M5 19l6-11 4 6 3-4 4 9"/>'
        '<path d="M11 8l4 6-4 5z" fill="currentColor" stroke="none" '
        'opacity="0.18"/>',
    "contour":
        '<path d="M12 5c4 0 7 3 7 7s-3 7-7 7-7-3-7-7 3-7 7-7z"/>'
        '<path d="M12 9c2 0 3.5 1.5 3.5 3.5S14 16 12 16s-3.5-1.5-3.5-3.5'
        'S10 9 12 9z"/>'
        '<path d="M12 12a1 1 0 100 2 1 1 0 000-2z" fill="currentColor" '
        'stroke="none"/>',
    "clip":
        '<path d="M4 16l5-8 6 4 5-6 0 12z" fill="currentColor" stroke="none" '
        'opacity="0.15"/>'
        '<path d="M4 16l5-8 6 4 5-6 0 12z"/>'
        '<rect x="4" y="4" width="16" height="16" rx="1" stroke-dasharray="2 2"/>',
    "resample":
        '<rect x="4" y="4" width="16" height="16" rx="1" stroke-dasharray="2 2"/>'
        '<circle cx="8" cy="8" r="1.2" fill="currentColor" stroke="none"/>'
        '<circle cx="16" cy="8" r="1.2" fill="currentColor" stroke="none"/>'
        '<circle cx="8" cy="16" r="1.2" fill="currentColor" stroke="none"/>'
        '<circle cx="16" cy="16" r="1.2" fill="currentColor" stroke="none"/>',
    "extract_band":
        '<rect x="4" y="6" width="16" height="4" rx="1" opacity="0.4"/>'
        '<rect x="4" y="13" width="16" height="4" rx="1" fill="currentColor" '
        'stroke="none" opacity="0.2"/>'
        '<rect x="4" y="13" width="16" height="4" rx="1"/>',
    "raster_calculator":
        '<rect x="4" y="4" width="16" height="16" rx="2"/>'
        '<path d="M12 7v10M7 12h10"/>',
    "reclassify":
        '<path d="M4 17h16"/>'
        '<path d="M5 17v-4M10 17v-7M15 17v-10M19 17v-2" opacity="0.7"/>',
    "normalize":
        '<path d="M4 19h16"/>'
        '<path d="M4 19L8 12 12 16 20 6"/>'
        '<circle cx="20" cy="6" r="1.6" fill="currentColor" stroke="none"/>',
    "raster_to_polygons":
        '<path d="M4 4h7v7H4z"/>'
        '<path d="M13 4h7v7h-7z"/>'
        '<path d="M4 13h7v7H4z"/>'
        '<path d="M13 13l7 1-1 6-6-1z" fill="currentColor" stroke="none" '
        'opacity="0.15"/>'
        '<path d="M13 13l7 1-1 6-6-1z"/>',
    "mosaic":
        '<path d="M4 5h7v14H4z" opacity="0.45"/>'
        '<path d="M13 5h7v14h-7z"/>'
        '<path d="M12 4v16" stroke-dasharray="2 2"/>',
    "stack_bands":
        '<rect x="4" y="5" width="16" height="4" rx="1" opacity="0.35"/>'
        '<rect x="4" y="10" width="16" height="4" rx="1" opacity="0.6"/>'
        '<rect x="4" y="15" width="16" height="4" rx="1"/>',
    "measure_fields":
        '<rect x="3" y="9" width="18" height="7" rx="1"/>'
        '<path d="M7 9v3M11 9v4M15 9v3M19 9v4" opacity="0.7"/>',
    "relation_fields":
        '<rect x="4" y="4" width="10" height="10" rx="1" opacity="0.55"/>'
        '<circle cx="14.5" cy="14.5" r="5.5"/>'
        '<circle cx="14.5" cy="14.5" r="1.4" fill="currentColor" '
        'stroke="none"/>',
}

ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "resources", "icons")

_INLINE_FIRST = {
    "add_vector", "add_raster", "pan", "zoom_in", "zoom_out", "zoom_full",
    "eyedropper",
    "identify", "select", "measure_length", "measure_area",
    "measure_angle", "processing", "coord_transform",
    "ins_point", "ins_line", "ins_poly",
    "plus",
    "arrange_up", "arrange_down", "distribute",
    "edit", "add_feature", "feature_new", "move_feature", "delete_feature",
    "save",
    "refresh",
    "stop",
    "finish", "cancel", "discard",
    "reset_edit",
    "vertex_edit", "split_features", "reshape", "combine_features",
    "snap_midpoint", "snap_edge",
    "fix_geometry",
    "new", "open", "project_open", "remove", "settings",
    "task",
    "link",
    "checkbox_on", "checkbox_off",
    "broom",
    "new_file", "new_shape",
    "logo",
    "basemap_main", "add_data_main",
    "cut_features", "copy_features", "paste_features",
    "paste_special",

    "crs_enabled", "crs_disabled", "new_crs", "confirm", "clear",
    "render_done",
    "crs", "crs_geo", "crs_proj",
    "merge_features", "filter", "export_raster", "input_file",
    "intersection", "query", "to_excel", "union",
    "notices",
    "log_clear",
    "intersect", "union", "difference", "sym_difference", "identity",
    "convex_hull", "bounding_box", "delete_duplicates", "densify",
    "round_coordinates",
    "about", "clipboard_copy", "license", "chip", "modules",
    "zoom_100", "view_prev", "view_next", "ruler", "guide", "margin",
    "zoom_map", "page_orient",
    "point_on_surface", "concave_hull", "oriented_envelope",
    "minimum_bounding_circle", "maximum_inscribed_circle", "boundary",
    "exterior_ring", "extract_by_type", "to_multipart", "shortest_line",
    "remove_repeated_points", "snap", "offset_curve", "translate", "scale",
    "rotate", "reverse", "orient_polygons", "line_merge", "build_area",
    "node", "clip_by_rect",
    "area_field", "length_field", "perimeter_field", "num_points_field",
    "num_geometries_field", "num_rings_field", "minimum_clearance_field",
    "circularity_field",
    "intersects_field", "contains_field", "within_field", "touches_field",
    "overlaps_field", "crosses_field", "disjoint_field", "equals_field",
    "covers_field", "covered_by_field", "dwithin_field", "distance_field",
    "union_layer", "collect", "extent_layer", "coverage_union",
    "slope", "aspect", "hillshade", "contour",
    "clip", "resample", "extract_band",
    "raster_calculator", "reclassify", "normalize", "raster_to_polygons",
    "mosaic", "stack_bands", "measure_fields", "relation_fields",
}

_FILE_MAP = {
    "add_vector":   "open_vector.svg",
    "add_raster":   "open_raster.svg",
    "open":         "folder.svg",
    "project_open": "catalog.svg",
    "browser":      "library.svg",
    "save":         "save.svg",
    "refresh":      "reset.svg",
    "info":         "about.svg",
    "overview":     "world.svg",
    "styling":      "color_table.svg",
    "export":       "to_vector.svg",
    "export_raster": "to_raster.svg",
    "rgb":          "Band_Synthesis.svg",
    "stats":        "SummaryStatistics.svg",
    "processing":   "run.svg",
    "filter":       "filter.svg",
    "logo":         "logo.svg",
    "sample":       "addData.svg",
    "layer":        "layer.svg",
    "query":        "sql.svg",
    "log":          "log.svg",
    "clear":        "clear.svg",
    "confirm":      "confirm.svg",
    "new_crs":      "newcrs.svg",
    "to_excel":     "to_excel.svg",
    "input_file":   "input_file.svg",
    "buffer":       "buffer.svg",
    "clip":         "clip.svg",
    "dissolve":     "dissolve.svg",
    "union":        "Union.svg",
    "intersection": "Intersection.svg",
}

_THEME_PAIR = frozenset({
    "point_layer", "line_layer", "polygon_layer",
    "raster_layer", "xyz_tile", "table",
})

_QGIS_MAP = {
    "pan":            "mActionPan.svg",
    "zoom_in":        "mActionZoomIn.svg",
    "zoom_out":       "mActionZoomOut.svg",
    "zoom_full":      "mActionZoomFullExtent.svg",
    "zoom_layer":     "mActionZoomToLayer.svg",
    "identify":       "mActionIdentify.svg",
    "select":         "mActionSelectRectangle.svg",
    "measure_length": "mActionMeasure.svg",
    "measure_area":   "mActionMeasureArea.svg",
    "table":          "mActionOpenTable.svg",
    "save":           "mActionFileSave.svg",
    "new":            "mActionFileNew.svg",
    "open":           "mActionFileOpen.svg",
    "project_open":   "mActionFileOpen.svg",
    "export":         "mActionFileSaveAs.svg",
    "export_raster":  "mActionFileSaveAs.svg",
    "remove":         "mActionRemoveLayer.svg",
    "refresh":        "mActionRefresh.svg",
    "info":           "mIconInfo.svg",
    "crs":            "propertyicons/CRS.svg",
    "crs_enabled":    "mIconProjectionEnabled.svg",
    "crs_disabled":   "mIconProjectionDisabled.svg",
    "settings":       "mActionOptions.svg",
    "edit":           "mActionToggleEditing.svg",
    "move_feature":   "mActionMoveFeaturePoint.svg",
    "delete_feature": "mActionDeleteSelectedFeatures.svg",
    "vertex_edit":    "mActionVertexTool.svg",
    "split_features": "mActionSplitFeatures.svg",
    "reshape":        "mActionReshape.svg",
    "merge_features": "mActionMergeFeatures.svg",
    "combine_features": "mActionMergeFeatureAttributes.svg",
    "copy_features":  "mActionEditCopy.svg",
    "cut_features":   "mActionEditCut.svg",
    "paste_features": "mActionEditPaste.svg",
    "add_feature":    "mActionCapturePoint.svg",
    "bookmark":       "mActionShowBookmarks.svg",
    "styling":        "propertyicons/symbology.svg",
    "camera":         "mActionSaveMapAsImage.svg",
    "filter":         "mIconExpressionFilter.svg",
    "query":          "mIconExpressionFilter.svg",
    "opacity":        "propertyicons/transparency.svg",
    "stretch":        "propertyicons/histogram.svg",
    "label":          "mActionLabeling.svg",
    "stats":          "mActionSum.svg",
    "browser":        "mIconFolder.svg",
}

_QGIS_CACHE = {}

_FILE_CACHE = {}

_RE_WHITE_HEX = re.compile(r"#(?:[Ff]{6}|[Ff]{3})(?![0-9A-Fa-f])")
_RE_WHITE_WORD = re.compile(r"(?<![\w#])white(?![\w])")

_LIGHT_BODY = "#3a414b"

_CACHE = {}

_DARK = True
_FG_DARK = "#d8dee9"
_FG_LIGHT = "#2d3440"


def set_theme(dark=True):
    global _DARK
    dark = bool(dark)
    if dark != _DARK:
        _CACHE.clear()
    _DARK = dark


def default_color():
    return _FG_DARK if _DARK else _FG_LIGHT


def clear_cache():
    _CACHE.clear()


_BOUND = []


def bind(target, name, size=24):
    sz = int(size)
    target.setIcon(icon(name, size=sz))
    try:
        if isinstance(target, QAbstractButton) and _default_icon_size(target):
            target.setIconSize(QSize(sz, sz))
    except Exception:
        exc_note("bind @ ggis/common/styling/icons.py:1656")
        pass
    _BOUND.append((weakref.ref(target), name, size))


def _default_icon_size(btn):
    try:
        d = btn.style().pixelMetric(
            QStyle.PixelMetric.PM_ToolBarIconSize, None, btn)
        cur = btn.iconSize()
        return int(cur.width()) == int(d) and int(cur.height()) == int(d)
    except Exception:
        exc_note("_default_icon_size @ ggis/common/styling/icons.py:1668")
        return False


def retheme_all():
    live = []
    for ref, name, size in _BOUND:
        w = ref()
        if w is None:
            continue
        live.append((ref, name, size))
        try:
            w.setIcon(icon(name, size=int(size)))
        except Exception:
            exc_note("retheme_all @ ggis/common/styling/icons.py:1682")
            pass
    _BOUND[:] = live


def is_dark():
    return _DARK


def _load_file_svg(filename):
    if filename in _FILE_CACHE:
        return _FILE_CACHE[filename]
    text = None
    try:
        path = os.path.join(ICON_DIR, filename)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
    except Exception:
        exc_note("_load_file_svg @ ggis/common/styling/icons.py:1702")
        text = None
    _FILE_CACHE[filename] = text
    return text


def _load_theme_pair_svg(name, size, dpr):
    filename = "%s/%s.svg" % ("dark" if _DARK else "light", name)
    text = _load_file_svg(filename)
    if not text:
        return None
    try:
        _s = max(1.0, float(size))
    except Exception:
        exc_note("_load_theme_pair_svg @ ggis/common/styling/icons.py:1720")
        _s = 24.0
    sw = min(1.6, max(1.2, 24.0 / _s))
    text = text.replace("__ICON_STROKE__", "%g" % sw)
    return _render_svg(text, size, dpr)


def _recolor_light(svg_text):
    svg_text = _RE_WHITE_HEX.sub(_LIGHT_BODY, svg_text)
    svg_text = _RE_WHITE_WORD.sub(_LIGHT_BODY, svg_text)
    return svg_text


def device_pixel_ratio():
    try:
        app = QGuiApplication.instance()
        if app is not None:
            scr = app.primaryScreen()
            if scr is not None:
                return max(1.0, float(scr.devicePixelRatio()) or 1.0)
    except Exception:
        exc_note("device_pixel_ratio @ ggis/common/styling/icons.py:1748")
        pass
    return 1.0


def _render_svg(svg_text, size, dpr):
    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    if not renderer.isValid():
        return None
    px = max(1, int(round(float(size) * dpr)))
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0.0, 0.0, float(px), float(px)))
    painter.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def _wrap_body(body, color, size):
    try:
        _s = max(1.0, float(size))
    except Exception:
        exc_note("_wrap_body @ ggis/common/styling/icons.py:1788")
        _s = 24.0
    sw = min(1.6, max(1.2, 24.0 / _s))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'width="{s}" height="{s}" fill="none" stroke="{c}" color="{c}" '
        'stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round">'
        '{b}</svg>'
    ).format(s=size, c=color, w=("%g" % sw), b=body)


def save_modified_icon(progress, color=None, size=24):
    if color is None:
        color = default_color()
    try:
        p = 0.0 if progress is None else max(0.0, min(1.0, float(progress)))
    except Exception:
        exc_note("save_modified_icon @ ggis/common/styling/icons.py:1814")
        p = 0.0
    s = 1.70158
    ease = 1.0 + (s + 1.0) * (p - 1.0) ** 3 + s * (p - 1.0) ** 2
    if ease < 0.0:
        ease = 0.0
    r = 3.2 * ease
    body = _BODY["save"]
    if r > 0.05:
        body += ('<circle cx="20.4" cy="20.4" r="{0:.2f}" fill="currentColor"'
                 ' fill-opacity="{1:.3f}" stroke="none"/>').format(r, p)
    pm = _render_svg(_wrap_body(body, color, size), size,
                     device_pixel_ratio())
    if pm is None:
        return icon("save_modified" if p >= 0.5 else "save", color, size)
    return QIcon(pm)


def icon(name, color=None, size=24):
    if color is None:
        color = default_color()
    dpr = device_pixel_ratio()
    key = (name, color, size, dpr)
    if key in _CACHE:
        return _CACHE[key]

    pm = None
    if (color == default_color() and name in _THEME_PAIR
            and os.path.isfile(os.path.join(
                ICON_DIR, ("dark" if _DARK else "light"), name + ".svg"))):
        pm = _load_theme_pair_svg(name, size, dpr)
        if pm is not None:
            _CACHE[key] = QIcon(pm)
            return _CACHE[key]

    if name in _INLINE_FIRST:
        body = _BODY.get(name)
        if body is not None:
            pm = _render_svg(_wrap_body(body, color, size), size, dpr)
            if pm is not None:
                _CACHE[key] = QIcon(pm)
                return _CACHE[key]

    filename = _FILE_MAP.get(name)
    if filename is not None and color == default_color():
        svg_text = _load_file_svg(filename)
        if svg_text:
            if not _DARK:
                svg_text = _recolor_light(svg_text)
            pm = _render_svg(svg_text, size, dpr)

    if pm is None:
        body = _BODY.get(name)
        if body is None:
            return QIcon()
        pm = _render_svg(_wrap_body(body, color, size), size, dpr)
        if pm is None:
            return QIcon()

    ic = QIcon(pm)
    _CACHE[key] = ic
    return ic


def filled_icon(name, size=16, color=None):
    if color is None:
        color = default_color()
    dpr = device_pixel_ratio()
    key = ("__filled__", name, color, size, dpr)
    if key in _CACHE:
        return _CACHE[key]

    S = max(1, int(round(float(size) * dpr)))
    ic = icon(name, color=color, size=size)
    pm = ic.pixmap(S, S)
    if pm.isNull() or pm.width() < 2:
        return ic
    img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32)

    minx = miny = 10 ** 9
    maxx = maxy = -1
    for y in range(img.height()):
        for x in range(img.width()):
            if (img.pixel(x, y) >> 24) & 0xFF:
                if x < minx:
                    minx = x
                if x > maxx:
                    maxx = x
                if y < miny:
                    miny = y
                if y > maxy:
                    maxy = y
    if maxx < 0:
        return ic
    bw = maxx - minx + 1
    bh = maxy - miny + 1
    if bw >= S and bh >= S:
        _CACHE[key] = ic
        return ic

    scale = float(S) / float(max(bw, bh))
    dw = max(1, int(round(bw * scale)))
    dh = max(1, int(round(bh * scale)))
    out = QImage(S, S, QImage.Format.Format_ARGB32)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    try:
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.drawImage(QRect((S - dw) // 2, (S - dh) // 2, dw, dh),
                    img.copy(minx, miny, bw, bh))
    finally:
        p.end()
    pm2 = QPixmap.fromImage(out)
    ic2 = QIcon(pm2)
    _CACHE[key] = ic2
    return ic2


def app_icon():
    svg_text = _load_file_svg("logo.svg")
    if not svg_text:
        return icon("info")
    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    pm = QPixmap(256, 256)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return QIcon(pm)


def app_logo_pixmap(size=64, dpr=None):
    try:
        svg_text = _load_file_svg("logo.svg")
    except Exception:
        exc_note("app_logo_pixmap @ ggis/common/styling/icons.py:2005")
        svg_text = ""
    if not svg_text:
        return QPixmap()
    try:
        _dpr = float(dpr) if dpr else float(device_pixel_ratio())
    except Exception:
        exc_note("app_logo_pixmap @ ggis/common/styling/icons.py:2011")
        _dpr = 1.0
    if _dpr < 1.0:
        _dpr = 1.0
    side = max(8, int(round(float(size) * _dpr)))
    pm = QPixmap(side, side)
    pm.fill(Qt.GlobalColor.transparent)
    try:
        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
        painter = QPainter(pm)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            renderer.render(painter)
        finally:
            painter.end()
    except Exception:
        exc_note("app_logo_pixmap @ ggis/common/styling/icons.py:2026")
        return QPixmap()
    pm.setDevicePixelRatio(_dpr)
    return pm


def themed_icon(name, dark=True, size=24):
    return icon(name, "#d8dee9" if dark else "#2c3038", size)


def colored_dot(color, size=16):
    dpr = device_pixel_ratio()
    px = max(1, int(round(float(size) * dpr)))
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    k = px / float(size)
    p.drawEllipse(QRectF(2.0 * k, 2.0 * k, (size - 4) * k, (size - 4) * k))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)


def colored_rect(color, size=16):
    dpr = device_pixel_ratio()
    px = max(1, int(round(float(size) * dpr)))
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    k = px / float(size)
    p.drawRect(QRectF(1.5 * k, 3.0 * k, (size - 3) * k, (size - 6) * k))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)


def colored_line(color, size=16):
    dpr = device_pixel_ratio()
    px = max(1, int(round(float(size) * dpr)))
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    k = px / float(size)
    h = 3.2
    p.drawRoundedRect(
        QRectF(1.5 * k, (size / 2.0 - h / 2.0) * k, (size - 3) * k, h * k),
        (h / 2.0) * k, (h / 2.0) * k)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)
