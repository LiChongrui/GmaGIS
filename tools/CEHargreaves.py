# -*- coding: utf-8 -*-

from core.ratowin import *
from core.iplib import (io, np, climet, env, dt as datetime)
from core.utils import GetIcon

Title = None
Icon = None
  
def Fun(InFileTMax, InFileTMin, OutFile, InFileTmean = None, 
        StartDate = [1992, 1, 1], Format = 'GTiff'):
    
    TMaxSet = io.ReadRaster(InFileTMax)
    TMinSet = io.ReadRaster(InFileTMin)

    if InFileTmean:
        TMeanSet = io.ReadRaster(InFileTmean)
    else:
        TMeanSet = None

    Bands, Rows, Columns = TMaxSet.Bands, TMaxSet.Rows, TMaxSet.Columns
    StartYear = int(StartDate[0])
    Date = datetime.datetime(*StartDate)
    StartDayOfYear = int(Date.strftime('%j'))
    NoData = TMaxSet.NoData
    
    LATSet = TMaxSet.GenLonLat()
    
    DataType = TMaxSet.DataType
    if DataType != 'Float64':
        dt = np.float32
    else:
        dt = np.float64
    Result = np.zeros((Bands, Rows, Columns), dtype = dt)

    Block = int(np.ceil(env.MaxPT / Columns / 100))
    Slice = list(range(0, Rows, Block))
    Times = len(Slice)
    for i, st in enumerate(Slice):
        TMax = TMaxSet.ToArray(TopRow = st, RowSize = Block)
        TMin = TMinSet.ToArray(TopRow = st, RowSize = Block)
        if TMeanSet:
            TMean = TMeanSet.ToArray(TopRow = st, RowSize = Block)
        else:
            TMean = None
        LAT = LATSet.ToArray(TopRow = st, RowSize = Block, BandList = 2)
        
        Index = climet.ET0.Hargreaves(TMax, TMin, 
                                      LAT = LAT, 
                                      TMean = TMean, 
                                      Axis = 0, 
                                      StartYear = StartYear, 
                                      StartDayOfYear = StartDayOfYear
                                      )
        
        if NoData:
            Index[TMax == NoData] = NoData
        
        Result[:, st:st+Block, :] = Index
        if env.CallBack:
            env.CallBack((i + 1) / Times)
            
    env.CallBack = None
    io.SaveArrayAsRaster(Result,
                         OutFile,
                         Projection = TMaxSet.Projection,
                         Transform = TMaxSet.GeoTransform,
                         NoData = TMaxSet.NoData,
                         Format = Format)  
    
class ToolWindow(RaToWindow):

    def __init__(self, parent = None):
    
        super().__init__(Fun, parent)
        
        self.NeedBar = True
        self.NeedFileIO = True
        self.NeedParLayout = True
        
        self.initUI()

        self.AddButtonConnect()
        
        self.Title = Title
        self.setWindowTitle(self.Title)
        self.setWindowIcon(GetIcon(Icon))        

        self.setMinimumWidth(self.SubWinCFG['WindowsSize'][0])
        self.adjustSize() 
        self.Center()

