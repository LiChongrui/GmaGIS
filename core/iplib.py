# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from gma.algos.core.iplib import *
from gma.map.base import *
np.seterr(all = 'ignore')
np.set_printoptions(suppress = True)

from gma import io, rasp, vesp, math, climet, rsvi, gft, crs, env, osf
from gma.map import plot, inres, cltbase

import os, sys, subprocess
import datetime as dt
import inspect

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas  
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.axes as ax

env.VectorReadMode = 0

cltbase.SetExtent = lambda x: None
