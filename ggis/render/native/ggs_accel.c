/*
 * ggs_accel.c —— GmaGIS 方案2（流式瓦片渲染）的原生加速层。
 *
 * 设计约束（很重要，别改）
 * -----------------------
 * 1. **裸 C ABI + ctypes 调用**，不用 pybind11、不用 CPython 扩展 API。
 *    原因：本项目自带的 Python 3.14.7 发行包里没有 Include/ 与 libs/
 *    （缺开发文件），装 pybind11 也编译不了；而裸 DLL 只要一个 C 编译器
 *    + Windows SDK 就能出，本机（VS 18 Community，MSVC 14.51）已具备。
 *    附带好处：numpy 数组按指针直传，**零拷贝**，也不需要 numpy C API。
 * 2. **只用 C89/C99 的 <stddef.h> / <stdlib.h> / <string.h>**，不链接
 *    CRT 以外的任何东西（/MT 也不必要，这几个函数没有跨模块的堆对象）。
 * 3. 所有函数都返回 0 表示成功、非 0 表示参数非法 —— Python 侧据此
 *    回退到纯 Python 实现，绝不因为原生层炸掉而功能不可用。
 *
 * 三个算子都是"随顶点数线性增长"的纯数值热区，也是方案2 里
 * 每次换级 / 每块取候选部件都要跑的东西：
 *
 *   ggs_part_bbox     每部件 bbox（替 numpy reduceat 那一族）
 *   ggs_bucketize     部件 → 瓦片分桶，输出 CSR（替 argsort + unique）
 *   ggs_bbox_select   一块瓦片的候选部件筛选（每块一次，最热）
 */

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* 这份源码**同时能按 C 和 C++ 编译**（`build.py --cxx` 会用 /TP 走 C++
   前端）。C++ 会对函数名做 name mangling，ctypes 就找不到符号了，所以
   导出符号一律套 `extern "C"`。这样"要不要上 C++"是构建开关，不是重写。 */
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
 * 1) 每部件 bbox
 *
 * 输入 xs / ys 是**分开的**连续 float64 数组（不是交错的 (npts,2)）。
 * 这样 C 与 numpy 两份实现吃的是同一份输入，微基准才公平；调用方
 * 本来就只需要拆一次列（O(n)，之后按图层缓存）。
 *
 * starts/ends 是每部件在 xs/ys 中的半开区间 [s, e)。输出 out 是
 * (nparts, 4) = {x0, y0, x1, y1}。
 *
 * 空区间（e - s < 1）写出"空框"（x0 = +1, x1 = -1），调用方用
 * x1 >= x0 判有效 —— 与 numpy 版行为一字不差。
 * ------------------------------------------------------------------ */
GGS_API int ggs_part_bbox(const double *xs, const double *ys,
                          ptrdiff_t npts,
                          const int64_t *starts, const int64_t *ends,
                          ptrdiff_t nparts, double *out)
{
    ptrdiff_t i;
    if (xs == NULL || ys == NULL || starts == NULL || ends == NULL
        || out == NULL) {
        return GGS_ERR_ARGS;
    }
    if (nparts < 0 || npts < 0) {
        return GGS_ERR_ARGS;
    }
    for (i = 0; i < nparts; ++i) {
        int64_t s = starts[i];
        int64_t e = ends[i];
        double x0 = 0.0, y0 = 0.0, x1 = 0.0, y1 = 0.0;
        int64_t j;
        int has = 0;
        if (s < 0) s = 0;
        if (e > npts) e = npts;
        for (j = s; j < e; ++j) {
            double x = xs[j];
            double y = ys[j];
            if (!has) {
                x0 = x1 = x; y0 = y1 = y; has = 1;
            } else {
                if (x < x0) x0 = x;
                if (x > x1) x1 = x;
                if (y < y0) y0 = y;
                if (y > y1) y1 = y;
            }
        }
        out[i * 4 + 0] = has ? x0 : 1.0;
        out[i * 4 + 1] = has ? y0 : 1.0;
        out[i * 4 + 2] = has ? x1 : -1.0;
        out[i * 4 + 3] = has ? y1 : -1.0;
    }
    return GGS_OK;
}

/* ------------------------------------------------------------------ *
 * 2) 部件 → 桶（瓦片）分桶，计数排序输出 CSR
 *
 * 归属规则与方案1 的 `_chunk_index` **逐字一致**：按部件 bbox 的
 * **最小角** (x0, y0) 归属，每个部件只归一决 —— 这一点是硬要求，
 * 重复归属会让半透明填充叠加（颜色偏深）、描边重复（线变粗）。
 *
 * 桶号 = bx * nc + by（bx 沿 x，by 沿 y，by 向上增长）。
 * 输出：
 *   out_bucket[i]  部件 i 的桶号（原始，未钳制；调用方自己看）
 *   order[k]       第 k 个位置放的是哪个部件
 *   indptr[b]      桶 b 在 order 里的区间 [indptr[b], indptr[b+1])
 * indptr 长度 = nc*nc + 1。
 * ------------------------------------------------------------------ */
GGS_API int ggs_bucketize(const int64_t *bucket_in, ptrdiff_t nparts,
                          int nc,
                          int64_t *bucket_out,
                          int64_t *order,
                          int64_t *indptr)
{
    ptrdiff_t i;
    int64_t nb;
    int64_t *count = NULL;
    if (bucket_in == NULL || bucket_out == NULL
        || order == NULL || indptr == NULL) {
        return GGS_ERR_ARGS;
    }
    if (nc <= 0 || nparts < 0) {
        return GGS_ERR_ARGS;
    }
    nb = (int64_t)nc * (int64_t)nc;
    count = (int64_t *)calloc((size_t)nb, sizeof(int64_t));
    if (count == NULL) {
        return GGS_ERR_ALLOC;
    }

    for (i = 0; i < nparts; ++i) {
        int64_t b = bucket_in[i];
        bucket_out[i] = b;
        if (b < 0) b = 0;
        if (b >= nb) b = nb - 1;
        count[b] += 1;
    }

    indptr[0] = 0;
    for (i = 0; i < nb; ++i) {
        indptr[i + 1] = indptr[i] + count[i];
    }
    /* 计数排序：order[indptr[b]] = 部件下标 */
    memcpy(count, indptr, (size_t)nb * sizeof(int64_t));
    for (i = 0; i < nparts; ++i) {
        int64_t b = bucket_in[i];
        if (b < 0) b = 0;
        if (b >= nb) b = nb - 1;
        order[count[b]] = (int64_t)i;
        count[b] += 1;
    }
    free(count);
    return GGS_OK;
}

/* ------------------------------------------------------------------ *
 * 3) 部件 → 瓦片归属（单趟）+ 粗桶号
 *
 * 归属规则与方案1 的 `_chunk_index` **逐字一致**：按部件 bbox 的
 * **最小角** (x0, y0) 归属，每个部件只归一决 —— 硬要求，重复归属会让
 * 半透明填充叠加（颜色偏深）、描边重复（线变粗）。
 *
 * 一次遍历同时算出两样东西（省掉 numpy 那串 clip/floor/multiply 的
 * 中间数组）：
 *   assign[i] = cx * n_axis + cy      同级瓦片 id
 *   cid[i]    = (cx/factor) * nc + (cy/factor)   粗桶 id（nc = n_axis/factor）
 * 粗桶只当 **候选预筛**：请求同级瓦片 (tx,ty) 时先取它所属粗桶那一段
 * CSR 切片，再按 assign 精确过滤 —— 每次只扫 1/factor² 的部件。
 * ------------------------------------------------------------------ */
GGS_API int ggs_tile_assign(const double *x0, const double *y0,
                            ptrdiff_t n,
                            double gx0, double gy0,
                            double tw, double th,
                            int64_t n_axis, int factor,
                            int64_t *assign_out, int64_t *cid_out)
{
    ptrdiff_t i;
    int64_t nc;
    if (x0 == NULL || y0 == NULL || assign_out == NULL || cid_out == NULL) {
        return GGS_ERR_ARGS;
    }
    if (n_axis <= 0 || factor <= 0 || n_axis % factor != 0) {
        return GGS_ERR_ARGS;
    }
    if (tw <= 0.0 || th <= 0.0) {
        return GGS_ERR_ARGS;
    }
    nc = n_axis / factor;
    for (i = 0; i < n; ++i) {
        int64_t cx = (int64_t)((x0[i] - gx0) / tw);
        int64_t cy = (int64_t)((y0[i] - gy0) / th);
        if (cx < 0) cx = 0;
        if (cx > n_axis - 1) cx = n_axis - 1;
        if (cy < 0) cy = 0;
        if (cy > n_axis - 1) cy = n_axis - 1;
        assign_out[i] = cx * n_axis + cy;
        cid_out[i] = (cx / factor) * nc + (cy / factor);
    }
    return GGS_OK;
}

/* ------------------------------------------------------------------ *
 * 4) 版本号（Python 侧用来确认 DLL 与包装层对得上）
 * ------------------------------------------------------------------ */
GGS_API int ggs_accel_version(void)
{
    return 6;   /* 1=bbox 2=+bucketize 3=+bbox_select 4=+winding
                   5=bbox 改吃分开的 xs/ys
                   6=删掉多余的 bbox_select / winding，改为 tile_assign */
}
