# 第三方许可声明（THIRD PARTY NOTICES）

生成时间：2026-09-11 01:26:34  ·  Python 3.14.7  ·  组件总数 260

## 一、需要履行义务的组件（弱 copyleft，200 项）

以下组件的许可证要求**随分发提供许可证全文并保留版权声明**。本产品对它们全部**动态链接、未作修改**，因此符合分发要求。

| 组件 | 版本 | 许可证 | 本产品的链接方式 |
|---|---|---|---|
| Qt6（含 PySide6 / shiboken6 绑定、Qt6 插件与 QML 模块） | 6.11.2 | `LGPL-3.0-only` | 动态链接 · 未修改 |
| GEOS；GEOS C API；libiconv | 多个 | `LGPL-2.1-or-later` | 动态链接 · 未修改 |
| HDF5；HDF5 High-Level | 多个 | `HDF5` | 动态链接 · 未修改 |
| FreeXL；SpatiaLite | 多个 | `MPL-1.1 OR GPL-2.0-or-later OR LGPL-2.1-or-later` | 动态链接 · 未修改 |
| certifi；pathspec | 多个 | `MPL-2.0` | 动态链接 · 未修改 |
| MSVC C/C++ 运行库（concrt140 / msvcp140 / vcruntime140 …） | 多个 | `LicenseRef-MSVC-Runtime` | 动态链接 · 未修改 |

- **PySide6 / Qt6 / shiboken6** 为 `LGPL-3.0-only`。本产品动态链接 Qt6 动态库，用户可自行替换这些 DLL（详见 `resources/licenses/LGPL-3.0.txt` 与 `GPL-3.0.txt`）。
- **GEOS**（经 `shapely` / `rasterio` / `pyogrio` 捆绑）为 `LGPL-2.1-or-later`，同样是动态链接。
- 我方未对上述任一库的二进制做改名、重签名、裁剪或静态链接（由 `tests/test_gates.py::test_no_qt_binary_renamed_or_modified` 自动核验）。

## 二、宽松许可组件（仅需保留声明，68 项）

| 组件 | 许可证 |
|---|---|
| Expat；GDAL/OGR；Mesa 软件 OpenGL (opengl32sw.dll)；PROJ 9；attrs；giflib（另 18 个同类） | `MIT` |
| OpenBLAS (SciPy 构建)；PCRE2；Zstandard；affine；click；colorama（另 8 个同类） | `BSD-3-Clause` |
| LERC；OpenSSL libcrypto；OpenSSL libssl；ninja；packaging | `Apache-2.0` |
| OpenJPEG；Pygments；sip | `BSD-2-Clause` |
| minizip；tinyxml2；zlib | `Zlib` |
| XZ Utils (liblzma) | `0BSD` |
| numpy | `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0` |
| scipy | `BSD-3-Clause` |
| matplotlib（wheel 内捆绑 Qhull，FreeType 静态链接；许可全文均已含于其随包 LICENSE） | `Matplotlib`（BSD-3 兼容） |
| contourpy | `BSD-3-Clause` |
| cycler | `BSD-3-Clause` |
| fonttools | `MIT` |
| kiwisolver | `MIT` |
| python-dateutil | `BSD-3-Clause` |
| tzdata | `Apache-2.0` |
| pillow | `MIT-CMU` |
| typing_extensions | `PSF-2.0` |
| libpq (PostgreSQL) | `PostgreSQL` |
| SQLite | `Public-Domain` |
| Qhull | `Qhull` |
| SZIP (HDF5 随附) | `SZIP` |
| libcurl | `curl` |
| libpng | `libpng-2.0` |
| libtiff | `libtiff` |

## 三、许可证全文位置

各组件自带的许可证随包收集在 `resources/licenses/`：

- 顶层整篇文本（LGPL/GPL/MPL 等由人工放入的官方全文）：

  - `GPL-3.0.txt`（35149 字节）
  - `HDF5.txt`（5118 字节）
  - `LGPL-2.1.txt`（26419 字节）
  - `LGPL-3.0.txt`（7652 字节）
  - `MPL-1.1.txt`（26224 字节）
  - `MPL-2.0.txt`（16726 字节）
- `<包名>/…`：各组件的 `LICENSE` / `COPYING` 原样抄录，共 31 个包/目录。
  - `scipy/`：scipy 1.18.1 的 `LICENSE.txt`（2026-11-17 补）
  - `matplotlib/`：matplotlib 3.11.2 的 `LICENSE`（含捆绑 Qhull 与
    FreeType 的许可文本，2026-11-17 补）

## 四、Qt6 特别声明

> 本产品使用 Qt6，依据 GNU Lesser General Public License v3 授权。
> Qt 及其商标归 The Qt Company Ltd. 所有。
> 本产品与 The Qt Company 无隶属关系，亦未获其背书。

Qt6 以动态链接方式使用，用户可以获取、修改并替换本产品使用的
Qt6 动态库以行使 LGPL-3.0 赋予的权利。
