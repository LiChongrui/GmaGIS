
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor

from ggis.common.util.exc_report import exc_note

from .viewport import GgsMapSettings
from ..core.crs import crs_key

__all__ = ["RenderTask"]


class RenderTask:

    __slots__ = ("extent", "cov", "w", "h", "cw", "ch",
                 "dpr", "dpi", "color", "aa",
                 "crs_obj", "crs", "lod_ref_width", "labels_enabled")

    def __init__(self, *, extent, cov, w, h, cw, ch, dpr, dpi, color,
                 aa, crs_obj, crs, lod_ref_width=0, labels_enabled=True):
        self.extent = extent
        self.cov = cov
        self.w = w
        self.h = h
        self.cw = cw
        self.ch = ch
        self.dpr = dpr
        self.dpi = dpi
        self.color = color
        self.aa = bool(aa)
        self.crs_obj = crs_obj
        self.crs = crs
        self.lod_ref_width = lod_ref_width
        self.labels_enabled = bool(labels_enabled)

    @classmethod
    def from_canvas(cls, canvas):
        w = max(1, canvas.width())
        h = max(1, canvas.height())
        dpr = canvas._eff_dpr()
        dpi = 96.0
        try:
            scr = canvas.screen()
            if scr is not None:
                dpi = float(scr.logicalDotsPerInch())
        except Exception:
            exc_note("RenderTask.from_canvas @ ggis/render/render_task.py")
            pass
        cov = canvas._cov_for(canvas._extent)
        cw, ch = canvas._cov_size_for(w, h)
        crs_obj = canvas.effectiveCrs()
        return cls(
            extent=canvas._extent, cov=cov, w=w, h=h, cw=cw, ch=ch,
            dpr=dpr, dpi=dpi, color=QColor(canvas._color),
            aa=bool(canvas._anti_alias), crs_obj=crs_obj,
            crs=crs_key(crs_obj),
            lod_ref_width=0,
            labels_enabled=bool(canvas._labels_enabled),
        )

    def proc_dict(self, seq):
        cov4 = (float(self.cov.xmin), float(self.cov.ymin),
                float(self.cov.xmax), float(self.cov.ymax))
        return {
            "seq": int(seq),
            "extent": cov4,
            "size": (self.cw, self.ch),
            "dpr": self.dpr,
            "color": (self.color.red(), self.color.green(),
                      self.color.blue()),
            "aa": self.aa,
            "crs": self.crs,
            "dpi": self.dpi,
            "lod_ref_width": self.lod_ref_width,
            "labels": True,
            "labels_enabled": self.labels_enabled,
            "selection": False,
            "overlay": False,
            "raster_budget_ms": None,
        }

    def snapshot_dict(self):
        s = GgsMapSettings()
        try:
            s.set_extent(self.cov)
            s.set_output_size(QSize(self.cw, self.ch))
            s.set_lod_reference_width(self.lod_ref_width)
            s.set_destination_crs(self.crs_obj)
            s.set_dpi(self.dpi)
        except Exception:
            exc_note("RenderTask.snapshot_dict @ ggis/render/render_task.py")
            pass
        return {"size": (self.cw, self.ch), "dpr": self.dpr,
                "color": self.color,
                "aa": self.aa, "settings": s}
