# SBOM（软件物料清单）

生成时间：2026-09-11 01:26:34  ·  Python 3.14.7
2026-11-17 手工补入：scipy 1.18.1 / matplotlib 3.11.2 及其间接依赖
（contourpy / cycler / fonttools / kiwisolver / python-dateutil /
tzdata，均宽松许可）⇒ OK 60→68。

## 汇总

| 状态 | 数量 | 含义 |
|---|---|---|
| OK | 68 | 宽松许可，保留声明即可 |
| NOTICE | 200 | 弱 copyleft，动态链接 + 保留声明即可分发 |
| REVIEW | 0 | 表里没收录，需人工确认 |
| **FAIL** | 0 | **GPL/AGPL 等强 copyleft，不符合分发要求** |

## Python 包 · 随产品分发

| 组件 | 版本 | 许可证 | 状态 | 角色 |
|---|---|---|---|---|
| **matplotlib | 3.11.2 | Matplotlib（BSD-3 兼容） | OK | 运行时 · 绘图 |
| **numpy | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | OK | 运行时 · 数值 |
| **pillow | 12.3.0 | MIT-CMU | OK | 运行时 · 图像 |
| **pyogrio | 0.13.0 | MIT | OK | 运行时 · 矢量 IO |
| **pyproj | 3.8.0 | MIT | OK | 运行时 · 坐标变换 |
| **rasterio | 1.5.1 | BSD-3-Clause | OK | 运行时 · 栅格 IO |
| **scipy | 1.18.1 | BSD-3-Clause | OK | 运行时 · 数值 |
| **shapely | 2.1.2 | BSD-3-Clause | OK | 运行时 · 几何运算 |
| **shiboken6 | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · PySide6 绑定（随 PySide6 引入） |
| affine | 3.0.1 | BSD-3-Clause | OK | 间接依赖 |
| attrs | 26.1.0 | MIT | OK | 间接依赖 |
| certifi | 2026.7.22 | MPL-2.0 | NOTICE | 间接依赖 |
| click | 8.5.0 | BSD-3-Clause | OK | 间接依赖 |
| colorama | 0.4.6 | BSD-3-Clause | OK | 间接依赖 |
| contourpy | 1.4.0 | BSD-3-Clause | OK | 间接依赖（matplotlib） |
| cycler | 0.12.1 | BSD-3-Clause | OK | 间接依赖（matplotlib） |
| fonttools | 4.68.0 | MIT | OK | 间接依赖（matplotlib） |
| iniconfig | 2.3.0 | MIT | OK | 间接依赖 |
| kiwisolver | 1.5.1 | MIT | OK | 间接依赖（matplotlib） |
| mypy_extensions | 1.1.0 | MIT | OK | 间接依赖 |
| ninja | 1.13.2 | Apache-2.0 | OK | 间接依赖 |
| packaging | 26.3 | Apache-2.0 | OK | 间接依赖 |
| pathspec | 1.1.1 | MPL-2.0 | NOTICE | 间接依赖 |
| pip | 26.2.1 | MIT | OK | 间接依赖 |
| pluggy | 1.6.0 | MIT | OK | 间接依赖 |
| prettytable | 3.18.0 | BSD-3-Clause | OK | 间接依赖 |
| psutil | 7.2.2 | BSD-3-Clause | OK | 间接依赖 |
| Pygments | 2.21.0 | BSD-2-Clause | OK | 间接依赖 |
| pyparsing | 3.3.2 | MIT | OK | 间接依赖 |
| python-dateutil | 4.0.0 | BSD-3-Clause | OK | 间接依赖（matplotlib） |
| PySide6_Essentials | 6.11.2 | LGPL-3.0-only | NOTICE | 间接依赖 |
| rtree | 1.4.1 | MIT | OK | 间接依赖 |
| sip | 6.16.1 | BSD-2-Clause | OK | 间接依赖 |
| tomli | 2.4.1 | MIT | OK | 间接依赖 |
| typing_extensions | 4.16.0 | PSF-2.0 | OK | 间接依赖 |
| tzdata | 2026.6 | Apache-2.0 | OK | 间接依赖（matplotlib） |
| wcwidth | 0.8.3 | MIT | OK | 间接依赖 |

## Python 包 · 仅开发用，不随产品分发

| 组件 | 版本 | 许可证 | 状态 | 角色 |
|---|---|---|---|---|
| mypy | 1.18.2 | MIT | OK | 间接依赖 |
| pip-licenses | 5.0.0 | MIT | OK | 间接依赖 |
| pytest | 9.1.1 | MIT | OK | 间接依赖 |
| pytest-qt | 4.4.0 | MIT | OK | 间接依赖 |
| ruff | 0.14.4 | MIT | OK | 间接依赖 |

## wheel 内捆绑的原生库

| 组件 | 版本 | 许可证 | 状态 | 角色 |
|---|---|---|---|---|
| Expat | - | MIT | OK | wheel 内捆绑原生库 |
| FreeXL | - | MPL-1.1 OR GPL-2.0-or-later OR LGPL-2.1-or-later | NOTICE | wheel 内捆绑原生库 |
| GDAL/OGR | - | MIT | OK | wheel 内捆绑原生库 |
| **GEOS | - | LGPL-2.1-or-later | NOTICE | wheel 内捆绑原生库 |
| **GEOS C API | - | LGPL-2.1-or-later | NOTICE | wheel 内捆绑原生库 |
| giflib | - | MIT | OK | wheel 内捆绑原生库 |
| HDF5 | - | HDF5 | NOTICE | wheel 内捆绑原生库 |
| HDF5 High-Level | - | HDF5 | NOTICE | wheel 内捆绑原生库 |
| json-c | - | MIT | OK | wheel 内捆绑原生库 |
| LERC | - | Apache-2.0 | OK | wheel 内捆绑原生库 |
| libcurl | - | curl | OK | wheel 内捆绑原生库 |
| libgeotiff | - | MIT | OK | wheel 内捆绑原生库 |
| **libiconv | - | LGPL-2.1-or-later | NOTICE | wheel 内捆绑原生库 |
| libjpeg-turbo | - | BSD-3-Clause | OK | wheel 内捆绑原生库 |
| libpng | - | libpng-2.0 | OK | wheel 内捆绑原生库 |
| libpq (PostgreSQL) | - | PostgreSQL | OK | wheel 内捆绑原生库 |
| libsharpyuv (WebP) | - | BSD-3-Clause | OK | wheel 内捆绑原生库 |
| libtiff | - | libtiff | OK | wheel 内捆绑原生库 |
| libwebp | - | BSD-3-Clause | OK | wheel 内捆绑原生库 |
| libxml2 | - | MIT | OK | wheel 内捆绑原生库 |
| Mesa 软件 OpenGL (opengl32sw.dll) | 6.11.2 | MIT | OK | 运行时 · 软件 OpenGL 回退（PySide6 携带） |
| minizip | - | Zlib | OK | wheel 内捆绑原生库 |
| MSVC C++ 运行库 | - | LicenseRef-MSVC-Runtime | NOTICE | wheel 内捆绑原生库 |
| netCDF | - | BSD-3-Clause | OK | wheel 内捆绑原生库 |
| OpenBLAS (SciPy 构建) | - | BSD-3-Clause | OK | wheel 内捆绑原生库 |
| OpenJPEG | - | BSD-2-Clause | OK | wheel 内捆绑原生库 |
| OpenSSL libcrypto | - | Apache-2.0 | OK | wheel 内捆绑原生库 |
| OpenSSL libssl | - | Apache-2.0 | OK | wheel 内捆绑原生库 |
| PCRE2 | - | BSD-3-Clause | OK | wheel 内捆绑原生库 |
| PROJ 9 | - | MIT | OK | wheel 内捆绑原生库 |
| **PySide6 绑定模块 (pyside6.abi3.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Python 绑定（PySide6 携带） |
| **PySide6 绑定模块 (pyside6qml.abi3.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Python 绑定（PySide6 携带） |
| Qhull | - | Qhull | OK | wheel 内捆绑原生库 |
| **Qt6 (Qt6Concurrent.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6Core.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6DBus.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6Designer.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6DesignerComponents.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6Gui.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6Help.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6LabsAnimation.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6LabsFolderListModel.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6LabsPlatform.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6LabsQmlModels.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6LabsSettings.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6LabsSharedImage.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6LabsStyleKit.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6LabsStyleKitImpl.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6LabsSynchronizer.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6LabsWavefrontMesh.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6Lottie.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6LottieVectorImageGenerator.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6LottieVectorImageHelpers.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6Network.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6OpenGL.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6OpenGLWidgets.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6PrintSupport.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6Qml.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QmlCompiler.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QmlCore.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QmlLocalStorage.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QmlMeta.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QmlModels.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QmlNetwork.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QmlWorkerScript.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QmlXmlListModel.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6Quick.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickControls2.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickControls2Basic.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickControls2BasicStyleImpl.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickControls2FluentWinUI3StyleImpl.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickControls2Fusion.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickControls2FusionStyleImpl.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickControls2Imagine.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickControls2ImagineStyleImpl.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickControls2Impl.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickControls2Material.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickControls2MaterialStyleImpl.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickControls2Universal.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickControls2UniversalStyleImpl.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickControls2WindowsStyleImpl.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickDialogs2.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickDialogs2QuickImpl.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickDialogs2Utils.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickEffects.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickLayouts.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickParticles.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickShapes.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickShapesDesignHelpers.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickTemplates2.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickTest.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickTimeline.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickTimelineBlendTrees.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickVectorImage.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickVectorImageGenerator.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickVectorImageHelpers.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6QuickWidgets.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6Sql.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6Svg.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6SvgWidgets.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6Test.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6UiTools.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6Widgets.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 (Qt6Xml.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 原生库（PySide6 携带） |
| **Qt6 QML 模块 (effectsplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (labsanimationplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (labsmodelsplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (labsplatformplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (labsstylekitimplplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (labsstylekitplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (labssynchronizerplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (modelsplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (particlesplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (pdfquickplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qmlfolderlistmodelplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qmllocalstorageplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qmlnetworkplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qmlplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qmlsettingsplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qmlshapesplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qmlwavefrontmeshplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qmlxmllistmodelplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qquicklayoutsplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qquickvectorimagehelpersplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qquickvectorimageplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtqmlcoreplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtqmlstatemachineplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquick2plugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2basicstyleimplplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2basicstyleplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2fluentwinui3styleimplplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2fluentwinui3styleplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2fusionstyleimplplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2fusionstyleplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2imaginestyleimplplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2imaginestyleplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2implplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2materialstyleimplplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2materialstyleplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2nativestyleplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2plugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2universalstyleimplplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2universalstyleplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2windowsstyleimplplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickcontrols2windowsstyleplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickdialogs2quickimplplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickdialogsplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickscene2dplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickscene3dplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquickshapesdesignhelpersplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquicktemplates2plugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquicktimelineblendtreesplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtquicktimelineplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtvkbbuiltinstylesplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtvkbcomponentsplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtvkbhangulplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtvkblayoutsplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtvkbopenwnnplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtvkbpinyinplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtvkbplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtvkbpluginsplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtvkbsettingsplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtvkbstylesplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtvkbtcimeplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (qtvkbthaiplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (quicktestplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (quicktoolingplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (quickwindowplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (sharedimageplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (virtualkeyboardplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 QML 模块 (workerscriptplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 QML 模块（PySide6 携带） |
| **Qt6 插件 (PySidePlugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qaxwidget.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qcertonlybackend.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qdirect2d.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qdslintplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qgif.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qicns.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qico.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qjpeg.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qlottievectorimage.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qminimal.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qmldbg_debugger.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qmldbg_inspector.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qmldbg_local.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qmldbg_messages.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qmldbg_native.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qmldbg_nativedebugger.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qmldbg_preview.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qmldbg_profiler.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qmldbg_quick3dprofiler.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qmldbg_quickeventreplay.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qmldbg_quickprofiler.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qmldbg_server.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qmldbg_tcp.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qmodernwindowsstyle.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qnetworklistmanager.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qoffscreen.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qopensslbackend.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qpdf.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qquickwidget.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qschannelbackend.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qsqlibase.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qsqlite.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qsqlmimer.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qsqloci.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qsqlodbc.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qsqlpsql.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qsvg.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qsvgicon.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qtga.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qtiff.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qtuiotouchplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qtvirtualkeyboardplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (quicklintplugin.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qwbmp.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qwebengineview.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qwebp.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| **Qt6 插件 (qwindows.dll) | 6.11.2 | LGPL-3.0-only | NOTICE | 运行时 · Qt6 插件（PySide6 携带） |
| SpatiaLite | - | MPL-1.1 OR GPL-2.0-or-later OR LGPL-2.1-or-later | NOTICE | wheel 内捆绑原生库 |
| SQLite | - | Public-Domain | OK | wheel 内捆绑原生库 |
| SZIP (HDF5 随附) | - | SZIP | OK | wheel 内捆绑原生库 |
| tinyxml2 | - | Zlib | OK | wheel 内捆绑原生库 |
| XZ Utils (liblzma) | - | 0BSD | OK | wheel 内捆绑原生库 |
| zlib | - | Zlib | OK | wheel 内捆绑原生库 |
| Zstandard | - | BSD-3-Clause | OK | wheel 内捆绑原生库 |
