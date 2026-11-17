# -*- coding: utf-8 -*-
from __future__ import annotations

from ggis.common.util.exc_report import exc_note
__all__ = ["run_analysis_job"]


def run_analysis_job(params, jobs=None, to_file=False, path="",
                     creation_options=None, result_name="",
                     progress=None, cancel=None):
    from ..core import analysis as A

    _CALC_SPAN = 0.95

    def _scaled(frac, text):
        if progress is None:
            return
        try:
            f = max(0.0, min(1.0, float(frac)))
        except Exception:
            exc_note("_scaled @ ggis/exec/jobs.py:57")
            return
        try:
            progress(f * _CALC_SPAN, text)
        except Exception:
            exc_note("_scaled @ ggis/exec/jobs.py:61")
            pass

    jobs = list(jobs or [])
    if jobs:
        br = A.run_batch(jobs, progress=_scaled, cancel=cancel)
        if not br.results:
            return None, br
        first = jobs[0]
        crs = None
        try:
            lyr = first.input_layer
            crs = lyr.crs() if lyr is not None else None
        except Exception:
            exc_note("run_analysis_job @ ggis/exec/jobs.py:74")
            crs = None
        result = br.merged(result_name or "", crs=crs)
        result.ms = br.ms
    else:
        result = A.run_analysis(params, progress=_scaled, cancel=cancel)
        br = None

    if to_file and path and result is not None:
        if progress is not None:
            try:
                progress(0.97, "写入结果文件…")
            except Exception:
                exc_note("run_analysis_job @ ggis/exec/jobs.py:86")
                pass
        A.write_result(
            result, path,
            driver=(params.output_driver if params is not None else ""),
            creation_options=creation_options)
    if progress is not None:
        try:
            progress(1.0, "完成")
        except Exception:
            exc_note("run_analysis_job @ ggis/exec/jobs.py:96")
            pass
    return result, br
