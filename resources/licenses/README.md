# 第三方许可证全文

此外**必须**手工放入以下整篇文本（LGPL §4 要求随分发提供
许可证全文；这些全文不在任何 wheel 里）：

- `LGPL-3.0.txt`  —— Qt6 / PySide6 / shiboken6
- `GPL-3.0.txt`   —— LGPL-3.0 的姊妹文本（LGPL-3.0 以 GPL-3.0 为基）
- `LGPL-2.1.txt`  —— GEOS（shapely / rasterio / pyogrio 捆绑）、libiconv
- `MPL-2.0.txt`   —— certifi / pathspec
- `MPL-1.1.txt`   —— FreeXL / SpatiaLite 的三许可择一中的 MPL 支
- `HDF5.txt`      —— HDF5（rasterio 捆绑）

FreeXL 与 SpatiaLite 上游为 `MPL-1.1 OR GPL-2.0-or-later OR LGPL-2.1-or-later`，
三选一即可；本目录同时收录 MPL-1.1/LGPL-2.1/GPL 全文，覆盖任一支。

宽松许可（BSD/MIT/Apache 等）保留声明即可：随包分发的 dist-info
LICENSE 已满足义务；scipy 与 matplotlib（2026-11-17 合入）的全文
另收录在本目录 `scipy/LICENSE.txt` 与 `matplotlib/LICENSE`
（后者含捆绑 Qhull 与 FreeType 的许可文本）。

获取地址：https://www.gnu.org/licenses/ 、
https://www.mozilla.org/MPL/ 、https://spdx.org/licenses/HDF5.json
