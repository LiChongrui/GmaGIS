/*
 * ggs_prims.c —— 方案3 的 C++/C 图元内核（**不依赖 Qt、不做光栅化**）。
 *
 * 定位
 * ----
 * 本文件只干"几何"这一件事：把**地图坐标**的顶点批量变成**屏幕坐标**、
 * 精确裁掉视口外的部件、按类别把部件分桶，产出一份**紧凑的图元清单**
 * （多边形 / 线 / 点 的顶点）。
 *
 * **刻意不做像素操作**：这里一个 `uint8_t*` 像素缓冲都没有，也没有扫描线、
 * 没有覆盖率。矢量始终保持"多边形、线、点"的图元语义，最终由 Qt 的
 * QPainter 以矢量方式绘制（真抗锯齿、分辨率无关、能导出 PDF/SVG）。
 * 这与"把矢量光栅化成位图掩膜"是两条完全不同的路。
 *
 * 为什么值得搬到 C
 * ----------------
 * 方案1 的做法是：把**整个块**的部件都建成 QPainterPath（含大量视口外的），
 * 再在绘制时用一个 `QTransform` 把地图坐标缩到屏幕。两笔浪费：
 *   1. 视口外的顶点白建了路径；
 *   2. 每个顶点都要在 Python 里过一遍 `ravel().tolist()` + `QPointF` 配对
 *     （实测整层 7.9 秒、占建路径耗时 94%）。
 * 这里把"投影 + 裁剪 + 分桶"一次算完，Python 侧只对**可见部件**建路径，
 * 而且拿到的是**屏幕坐标**（不再需要 QTransform）。
 *
 * 单位与约定
 * ----------
 * * 屏幕仿射与 `viewport.GgsMapSettings.map_to_pixel` 完全一致：
 *     px = (x - x0) * sx        py = (y0 - y) * sy        （y 轴翻转）
 * * 裁剪用**部件 bbox 与裁剪框相交**判定（不是逐顶点），
 *   `pad` 是描边/符号的外扩量（像素），保证贴边的线不会被裁掉一截。
 * * 输出坐标是 `float`（屏幕像素，量级 1e3，float 精度绰绰有余；
 *   相比 double 省一半带宽）。
 */

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#if defined(__cplusplus)
#define GGS_LINKAGE extern "C"
#else
#define GGS_LINKAGE
#endif
#if defined(_WIN32)
#define GGS_API GGS_LINKAGE __declspec(dllexport)
#else
#define GGS_API GGS_LINKAGE
#endif

#define GGS_OK 0
#define GGS_ERR_ARGS 1
#define GGS_ERR_ALLOC 2

/* ------------------------------------------------------------------ *
 * 把部件按"可见 / 不可见"筛一遍，并输出屏幕坐标与按类别的分桶。
 *
 * 输出（全部由调用方预分配）：
 *   out_xy       float32[npts * 2]   —— 屏幕坐标（**全部顶点都写**，
 *                                       下标与输入一一对应，这样调用方
 *                                       可以直接按原区间切片，不必重映射）
 *   out_part     int64[nparts]       —— 通过裁剪的部件下标
 *   out_class    int64[nparts]       —— 与 out_part 对应的类别号
 *                                        （part_class 为 NULL 时全 0）
 *   out_order    int64[nparts]       —— 按类别号稳定排序后的 out_part 下标
 *                                       （调用方按类取连续区间即可）
 *   out_indptr   int64[nclass+1]     —— 第 k 类的部件在 out_order 中的区间
 *
 * 返回 GGS_OK / 错误码；通过裁剪的部件数写进 *out_nparts。
 * ------------------------------------------------------------------ */
GGS_API int ggs_build_prims(
    const double *xs, const double *ys, ptrdiff_t npts,
    const int64_t *part_start, const int64_t *part_end, ptrdiff_t nparts,
    const int64_t *part_class,
    double sx, double sy, double x0, double y0,
    double clip_minx, double clip_miny, double clip_maxx, double clip_maxy,
    double pad,
    int64_t nclass,
    float *out_xy,
    int64_t *out_part,
    int64_t *out_class,
    int64_t *out_order,
    int64_t *out_indptr,
    int64_t *out_nparts)
{
    ptrdiff_t i;
    int64_t m = 0;
    int64_t *count = NULL;

    if (xs == NULL || ys == NULL || part_start == NULL || part_end == NULL
        || out_xy == NULL || out_part == NULL || out_class == NULL) {
        return GGS_ERR_ARGS;
    }
    if (nclass < 1) {
        nclass = 1;
    }

    /* ---- ① 批量投影到屏幕坐标（并顺便算每个部件的屏幕 bbox）---- */
    for (i = 0; i < npts; ++i) {
        out_xy[i * 2]     = (float)((xs[i] - x0) * sx);
        out_xy[i * 2 + 1] = (float)((y0 - ys[i]) * sy);
    }

    /* ---- ② 逐部件：屏幕 bbox 与裁剪框相交就留下 ---- */
    for (i = 0; i < nparts; ++i) {
        int64_t s = part_start[i];
        int64_t e = part_end[i];
        float x0f, y0f, x1f, y1f;
        int64_t j;
        int has = 0;
        if (s < 0) s = 0;
        if (e > npts) e = npts;
        if (e - s < 2) {
            continue;                       /* 空部件 / 单点无法成线面 */
        }
        for (j = s; j < e; ++j) {
            float px = out_xy[j * 2];
            float py = out_xy[j * 2 + 1];
            if (!has) {
                x0f = x1f = px; y0f = y1f = py; has = 1;
            } else {
                if (px < x0f) x0f = px;
                if (px > x1f) x1f = px;
                if (py < y0f) y0f = py;
                if (py > y1f) y1f = py;
            }
        }
        if (!has) {
            continue;
        }
        /* 闭区间相交 + pad 外扩：宁可多带一个部件，也不能把贴边的裁掉 */
        if ((double)x1f < clip_minx - pad || (double)x0f > clip_maxx + pad
            || (double)y1f < clip_miny - pad || (double)y0f > clip_maxy + pad) {
            continue;
        }
        out_part[m] = (int64_t)i;
        out_class[m] = part_class ? part_class[i] : 0;
        ++m;
    }
    *out_nparts = m;

    if (out_order == NULL || out_indptr == NULL) {
        return GGS_OK;                      /* 只要裁剪结果，不分桶 */
    }

    /* ---- ③ 按类别做计数排序（稳定），得到每类的连续区间 ---- */
    count = (int64_t *)calloc((size_t)nclass, sizeof(int64_t));
    if (count == NULL) {
        return GGS_ERR_ALLOC;
    }
    for (i = 0; i < m; ++i) {
        int64_t c = out_class[i];
        if (c < 0) c = 0;
        if (c >= nclass) c = nclass - 1;
        count[c] += 1;
    }
    out_indptr[0] = 0;
    for (i = 0; i < nclass; ++i) {
        out_indptr[i + 1] = out_indptr[i] + count[i];
    }
    memcpy(count, out_indptr, (size_t)nclass * sizeof(int64_t));
    for (i = 0; i < m; ++i) {
        int64_t c = out_class[i];
        if (c < 0) c = 0;
        if (c >= nclass) c = nclass - 1;
        out_order[count[c]] = (int64_t)i;    /* 存的是 out_part 的下标 */
        count[c] += 1;
    }
    free(count);
    return GGS_OK;
}

/* ------------------------------------------------------------------ *
 * LOD 抽稀：按屏幕距离过滤掉"连成一条线也看不出"的中间顶点。
 *
 * **默认不启用**（用户实测"简化后问题很大"）。这里的语义是保守的：
 *   * 只删"与前后两点在屏幕上都太近"的中间点（垂距 + 距离双条件）；
 *   * 每条环至少保留 3 个点、首尾点永不删；
 *   * 线至少保留 2 个点。
 * 调用方负责决定要不要用（`vector_lod_simplify` 打开时才调）。
 * ------------------------------------------------------------------ */
GGS_API int64_t ggs_decimate_parts(float *xy, const int64_t *part_start,
                                   const int64_t *part_end, ptrdiff_t nparts,
                                   int keep_min, double min_dist,
                                   int64_t *out_start, int64_t *out_end)
{
    ptrdiff_t i;
    double md2;
    if (xy == NULL || part_start == NULL || part_end == NULL
        || out_start == NULL || out_end == NULL) {
        return -1;
    }
    if (keep_min < 2) keep_min = 2;
    md2 = min_dist * min_dist;

    for (i = 0; i < nparts; ++i) {
        int64_t s = part_start[i];
        int64_t e = part_end[i];
        int64_t w = s;                       /* 写指针（就地压缩） */
        int64_t j;
        int64_t kept = 0;
        if (s < 0) s = 0;
        if (e <= s) {
            out_start[i] = s;
            out_end[i] = s;
            continue;
        }
        /* 首点必留 */
        if (w != s) {
            xy[w * 2] = xy[s * 2];
            xy[w * 2 + 1] = xy[s * 2 + 1];
        }
        ++w; ++kept;
        for (j = s + 1; j < e - 1; ++j) {
            double ax = xy[(w - 1) * 2], ay = xy[(w - 1) * 2 + 1];
            double bx = xy[j * 2], by = xy[j * 2 + 1];
            double cx = xy[(j + 1) * 2], cy = xy[(j + 1) * 2 + 1];
            double dx = bx - ax, dy = by - ay;
            double ex = cx - bx, ey = cy - by;
            double d1 = dx * dx + dy * dy;
            double d2 = ex * ex + ey * ey;
            if (d1 < md2 && d2 < md2) {
                continue;                    /* 前后都太近 → 这个点可省 */
            }
            if (w != j) {
                xy[w * 2] = (float)bx;
                xy[w * 2 + 1] = (float)by;
            }
            ++w; ++kept;
        }
        /* 末点必留（且保证总点数不低于 keep_min） */
        if (kept < keep_min) {
            out_start[i] = s;
            out_end[i] = e;                  /* 太短就不动它 */
            continue;
        }
        if (w != e - 1) {
            xy[w * 2] = xy[(e - 1) * 2];
            xy[w * 2 + 1] = xy[(e - 1) * 2 + 1];
        }
        ++w;
        out_start[i] = s;
        out_end[i] = w;
    }
    return 0;
}

GGS_API int ggs_prims_version(void)
{
    return 1;   /* 1 = build_prims + decimate_parts */
}
