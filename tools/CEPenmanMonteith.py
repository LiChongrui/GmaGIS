# -*- coding: utf-8 -*-

from core.ratowin import *
from core.iplib import (io, np, climet, env, pd, dt as datetime)
from core.utils import GetIcon

Title = None
Icon = None
  
def Fun(InFilePRS, InFileWIN, InFileTMax, InFileTMin, InFileRHU, InFileSSH, 
        InFileELE, OutFile, StartDate = [1992, 1, 1], Format = 'GTiff'):
    
    PRSSet = io.ReadRaster(InFilePRS)
    WINSet = io.ReadRaster(InFileWIN)    
    TMaxSet = io.ReadRaster(InFileTMax)
    TMinSet = io.ReadRaster(InFileTMin)    
    
    RHUSet = io.ReadRaster(InFileRHU)
    SSHSet = io.ReadRaster(InFileSSH)
    ELESet = io.ReadRaster(InFileELE)

    Bands, Rows, Columns = TMaxSet.Bands, TMaxSet.Rows, TMaxSet.Columns

    StDate = datetime.datetime(*StartDate)
    EnDate = StDate + datetime.timedelta(Bands - 1)

    Day = pd.date_range(StDate, EnDate).dayofyear.values[:, None, None]

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
        
        PRS = PRSSet.ToArray(TopRow = st, RowSize = Block)
        WIN = WINSet.ToArray(TopRow = st, RowSize = Block)
        TMax = TMaxSet.ToArray(TopRow = st, RowSize = Block)
        TMin = TMinSet.ToArray(TopRow = st, RowSize = Block)  
        RHU = RHUSet.ToArray(TopRow = st, RowSize = Block)
        SSH = SSHSet.ToArray(TopRow = st, RowSize = Block)
        
        ELE = ELESet.ToArray(TopRow = st, RowSize = Block)

        LAT = LATSet.ToArray(TopRow = st, RowSize = Block, BandList = 2)
   
        if PRSSet.Bands != 1:
            LAT = LAT[None, :]

        Index = climet.ET0.PenmanMonteith(PRS, WIN, TMax, TMin, 
                                          RHU, SSH, LAT, Day, ELE)
        
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

