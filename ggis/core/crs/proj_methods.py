# -*- coding: utf-8 -*-

__all__ = ["PARAM_SETS", "PROJ_METHODS", "COMMON", "method_info",
           "method_defaults", "method_label"]

_TM = (("lat_0", 0.0), ("lon_0", 117.0), ("k", 1.0),
       ("x_0", 500000.0), ("y_0", 0.0))
_UTM = (("zone", 50.0), ("x_0", 500000.0), ("y_0", 0.0))
_CYL = (("lat_ts", 0.0), ("lon_0", 0.0), ("x_0", 0.0), ("y_0", 0.0))
_MERC = (("lat_0", 0.0), ("lon_0", 0.0), ("k", 1.0),
         ("x_0", 0.0), ("y_0", 0.0))
_PSEUDO = (("lon_0", 0.0), ("x_0", 0.0), ("y_0", 0.0))
_AZ = (("lat_0", 0.0), ("lon_0", 105.0), ("x_0", 0.0), ("y_0", 0.0))
_CONE2 = (("lat_1", 25.0), ("lat_2", 47.0), ("lat_0", 0.0), ("lon_0", 105.0),
          ("x_0", 0.0), ("y_0", 0.0))
_CONE1 = (("lat_1", 25.0), ("lat_0", 0.0), ("lon_0", 105.0), ("k", 1.0),
          ("x_0", 0.0), ("y_0", 0.0))
_STERE = (("lat_0", 90.0), ("lon_0", 0.0), ("k", 0.994),
          ("x_0", 0.0), ("y_0", 0.0))
_TCEA = (("lat_0", 0.0), ("lat_ts", 30.0), ("lon_0", 105.0),
         ("x_0", 0.0), ("y_0", 0.0))
_OMERC = (("lat_0", 0.0), ("lonc", 105.0), ("alpha", 45.0), ("gamma", 45.0),
          ("k", 1.0), ("x_0", 0.0), ("y_0", 0.0))
_GEOS = (("lat_0", 0.0), ("lon_0", 105.0), ("h", 35785831.0),
         ("x_0", 0.0), ("y_0", 0.0))
_NSPER = (("lat_0", 40.0), ("lon_0", 105.0), ("h", 35785831.0),
          ("tilt", 0.0), ("azi", 0.0), ("x_0", 0.0), ("y_0", 0.0))
_GN_SINU = (("m", 2.0), ("n", 1.0), ("lon_0", 0.0), ("x_0", 0.0),
            ("y_0", 0.0))
_URM5 = (("n", 0.5), ("q", 1.0), ("alpha", 45.0), ("lon_0", 0.0),
         ("x_0", 0.0), ("y_0", 0.0))
_MISRSOM = (("lat_0", 30.0), ("lon_0", 31.0), ("path", 1.0), ("k", 1.0),
            ("x_0", 0.0), ("y_0", 0.0))
_TPEQD = (("lat_1", 45.0), ("lon_1", 105.0), ("lat_2", -45.0), ("lon_2", -75.0),
          ("x_0", 0.0), ("y_0", 0.0))
_KROVAK = (("lat_0", 49.5), ("lon_0", 24.8333333333333),
           ("alpha", 30.2881397527778), ("k", 0.9999),
           ("x_0", 0.0), ("y_0", 0.0))
_SOMERC = (("lat_0", 46.95240555555556), ("lon_0", 7.439583333333333),
           ("k", 1.0), ("x_0", 0.0), ("y_0", 0.0))
_URMFPS = (("n", 0.5), ("lon_0", 0.0), ("x_0", 0.0), ("y_0", 0.0))
_BONNE = (("lat_1", 45.0), ("lon_0", 105.0), ("x_0", 0.0), ("y_0", 0.0))

_LABRD = (("lat_0", -18.5), ("lon_0", 46.5), ("azi", 18.9), ("k", 0.9995),
          ("x_0", 400000.0), ("y_0", 800000.0))

PARAM_SETS = {
    "tm": _TM, "utm": _UTM, "cyl": _CYL, "merc": _MERC, "pseudo": _PSEUDO,
    "az": _AZ, "cone2": _CONE2, "cone1": _CONE1, "stere": _STERE,
    "tcea": _TCEA, "omerc": _OMERC, "geos": _GEOS, "nsper": _NSPER,
    "tpeqd": _TPEQD, "krovak": _KROVAK, "somerc": _SOMERC,
    "urmfps": _URMFPS, "bonne": _BONNE, "labrd": _LABRD,
    "misrsom": _MISRSOM, "gn_sinu": _GN_SINU, "urm5": _URM5,
    "none": _AZ,
}

PROJ_METHODS = (
    ("tmerc", "横轴墨卡托 / 高斯-克吕格", "tm"),
    ("utm", "通用横轴墨卡托（UTM）", "utm"),
    ("etmerc", "扩展横轴墨卡托（EtMerc）", "tm"),
    ("lcc", "兰勃特等角圆锥（2 标准纬线）", "cone2"),
    ("aea", "阿尔伯斯等积圆锥", "cone2"),
    ("eqdc", "等距圆锥", "cone2"),
    ("merc", "墨卡托（1SP）", "merc"),
    ("webmerc", "Web 墨卡托（Pseudo-Mercator）", "none"),
    ("cea", "等积圆柱（Lambert）", "cyl"),
    ("eqc", "等距圆柱（Plate Carrée）", "cyl"),
    ("mill", "米勒圆柱", "pseudo"),
    ("laea", "兰勃特方位等积", "az"),
    ("aeqd", "方位等距", "az"),
    ("stere", "立体投影（极球面）", "stere"),
    ("sterea", "斜轴立体（Oblique Stereographic）", "stere"),
    ("somerc", "瑞士斜轴墨卡托", "somerc"),
    ("krovak", "捷克 Krovak", "krovak"),
    ("omerc", "斜轴墨卡托（Hotine）", "omerc"),
    ("tcea", "横轴等积圆柱", "tcea"),
    ("moll", "摩尔威德", "pseudo"),
    ("robin", "罗宾逊", "pseudo"),
    ("sinu", "正弦曲线（Sinusoidal）", "pseudo"),
    ("natearth", "自然地球", "pseudo"),
    ("goode", "古德等积（Homolosine）", "pseudo"),
    ("eck4", "埃克特 IV", "pseudo"),
    ("vandg", "范德格林滕 I", "pseudo"),
    ("ortho", "正射投影（Orthographic）", "az"),
    ("gnom", "球心投影（Gnomonic）", "az"),
    ("geos", "地球同步卫星视图", "geos"),
    ("nsper", "近侧透视（Vertical Perspective）", "nsper"),
    ("airy", "Airy 最小误差方位", "az"),
    ("aitoff", "艾托夫", "pseudo"),
    ("alsk", "阿拉斯加圆锥（Modified Stereo）", "az"),
    ("apian", "Apian 球面", "az"),
    ("august", "August 极射", "az"),
    ("bacon", "Bacon 球面", "pseudo"),
    ("bipc", "双极圆锥（Bipolar Conic）", "cone2"),
    ("boggs", "Boggs 等积", "pseudo"),
    ("bonne", "Bonne 等积圆锥", "bonne"),
    ("cart", "Cartesian（笛卡儿）", "none"),
    ("cass", "卡西尼（Cassini-Soldner）", "tm"),
    ("cc", "中央圆柱（Central Cylindrical）", "pseudo"),
    ("collg", "Collignon 等积", "pseudo"),
    ("comill", "紧凑米勒（Compact Miller）", "pseudo"),
    ("crast", "Craster 抛物线", "pseudo"),
    ("denoy", "Denoyer 半立方", "pseudo"),
    ("eck1", "埃克特 I", "pseudo"),
    ("eck2", "埃克特 II", "pseudo"),
    ("eck3", "埃克特 III", "pseudo"),
    ("eck5", "埃克特 V", "pseudo"),
    ("eck6", "埃克特 VI", "pseudo"),
    ("eqearth", "等积地球（Equal Earth）", "pseudo"),
    ("fahey", "法赫伊", "pseudo"),
    ("fouc", "富科", "pseudo"),
    ("gall", "Gall 立体", "pseudo"),
    ("geocent", "地心直角坐标（Geocentric）", "none"),
    ("gins8", "金斯堡 VIII", "pseudo"),
    ("gn_sinu", "通用正弦（General Sinusoidal）", "gn_sinu"),
    ("gstmerc", "高斯-施赖伯横轴墨卡托", "tm"),
    ("hammer", "Hammer 等积", "pseudo"),
    ("hatano", "Hatano 非对称等积", "pseudo"),
    ("healpix", "HEALPix", "none"),
    ("rhealpix", "rHEALPix", "none"),
    ("igh", "国际椭球专用（Interrupted Goode）", "pseudo"),
    ("isea", "ISEA 离散全球网格", "none"),
    ("lagrng", "拉格朗日", "none"),
    ("larr", "拉里维", "pseudo"),
    ("lask", "Laskowski 三角", "pseudo"),
    ("latlon", "经纬度（Lat/Lon）", "none"),
    ("longlat", "经纬度（Long/Lat）", "none"),
    ("lonlat", "经纬度（Lon/Lat）", "none"),
    ("loxim", "洛希等距", "pseudo"),
    ("mill", "米勒圆柱", "pseudo"),
    ("natearth2", "自然地球 II", "pseudo"),
    ("nell", "Nell 准等积", "pseudo"),
    ("nicol", "Nicolosi 全球", "pseudo"),
    ("ocea", "斜轴等积圆柱", "cyl"),
    ("ortel", "奥特柳斯", "pseudo"),
    ("patterson", "Patterson 圆柱", "pseudo"),
    ("poly", "多圆锥（Polyconic）", "az"),
    ("qsc", "四边球面立方（Quadrilateralized）", "none"),
    ("rouss", "Roussilhe 斜轴立体", "stere"),
    ("rpoly", "矩形多圆锥", "az"),
    ("stere", "立体投影", "stere"),
    ("tcc", "倾斜中央圆柱", "pseudo"),
    ("tpers", "倾斜透视（Tilted Perspective）", "nsper"),
    ("tpeqd", "两等距点（Two Point Equidistant）", "tpeqd"),
    ("ups", "通用极球面（UPS）", "stere"),
    ("urm5", "乌尔马耶夫 V", "urm5"),
    ("urmfps", "Urmaev 平极正弦", "urmfps"),
    ("vandg2", "范德格林滕 II", "pseudo"),
    ("vandg3", "范德格林滕 III", "pseudo"),
    ("vandg4", "范德格林滕 IV", "pseudo"),
    ("wag1", "瓦格纳 I", "pseudo"),
    ("wag2", "瓦格纳 II", "pseudo"),
    ("wag3", "瓦格纳 III", "pseudo"),
    ("wag4", "瓦格纳 IV", "pseudo"),
    ("wag5", "瓦格纳 V", "pseudo"),
    ("wag6", "瓦格纳 VI", "pseudo"),
    ("wag7", "瓦格纳 VII", "pseudo"),
    ("wink1", "温克尔 I", "pseudo"),
    ("wink2", "温克尔 II", "pseudo"),
    ("wintri", "Winkel 三角", "pseudo"),
    ("labrd", "Laborde 斜轴墨卡托", "labrd"),
    ("misrsom", "埃及斜轴墨卡托（MisrSOM）", "misrsom"),
)

COMMON = (
    "tmerc", "utm", "etmerc", "lcc", "aea", "eqdc", "merc", "webmerc",
    "cea", "eqc", "mill", "laea", "aeqd", "stere", "sterea", "somerc",
    "krovak", "omerc", "tcea", "moll", "robin", "sinu", "natearth", "goode",
    "eck4", "vandg", "ortho", "gnom", "geos", "nsper",
)

_BY_KEY = {k: (label, pset) for k, label, pset in PROJ_METHODS}


def method_info(key):
    return _BY_KEY.get(str(key or ""))


def method_defaults(key):
    got = _BY_KEY.get(str(key or ""))
    pset = PARAM_SETS["tm"] if got is None else PARAM_SETS.get(got[1], ())
    return tuple(pset)


def method_label(key):
    got = _BY_KEY.get(str(key or ""))
    return got[0] if got else str(key or "")
