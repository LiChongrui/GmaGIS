# -*- coding: utf-8 -*-

from core.geowin import GeoToWindow
from core.iplib import (io, np, climet, env, pd, dt as datetime)
from core.utils import GetIcon

Title = None
Icon = None
  
def Fun(InFileTmean, OutFile, StartMonth = [1992, 1], Format = 'GTiff', #LAT = 34.6,
        **kwargs):
    
    StartYear = int(StartMonth[0])
    Date = datetime.datetime(*StartMonth, 1)
    StartMonth = int(Date.strftime('%m'))
    
    def CalVe():
        ATTMean = io.ReadVector(InFileTmean).AttributeTable
        
        TMean = ATTMean.values
        
        Result = climet.ET0.Thornthwaite(TMean, 
                                         #LAT = LAT, 
                                         Axis = 0, 
                                         StartYear = StartYear, 
                                         StartMonth  = StartMonth 
                                         )
        
        Result = pd.DataFrame(Result, 
                              columns = [f'Col_{i}' for i in range(TMean.shape[1])])  
                                         
        Layer = io.ReadDataFrameAsLayer(Result)
        Layer.SaveAs(OutFile, Format = Format) 
        
    def CalRa():
        TMeanSet = io.ReadRaster(InFileTmean)
        
        Bands, Rows, Columns = TMeanSet.Bands, TMeanSet.Rows, TMeanSet.Columns

        NoData = TMeanSet.NoData
        
        LATSet = TMeanSet.GenLonLat()
        
        DataType = TMeanSet.DataType
        if DataType != 'Float64':
            dt = np.float32
        else:
            dt = np.float64
        Result = np.zeros((Bands, Rows, Columns), dtype = dt)
    
        Block = int(np.ceil(env.MaxPT / Columns / 100))
        Slice = list(range(0, Rows, Block))
        Times = len(Slice)
        for i, st in enumerate(Slice):
            
            TMean = TMeanSet.ToArray(TopRow = st, RowSize = Block)
    
            LAT = LATSet.ToArray(TopRow = st, RowSize = Block, BandList = 2)
            
            Index = climet.ET0.Thornthwaite(TMean, 
                                            LAT = LAT, 
                                            Axis = 0, 
                                            StartYear = StartYear, 
                                            StartMonth  = StartMonth 
                                            )
            
            if NoData:
                Index[TMean == NoData] = NoData
            
            Result[:, st:st+Block, :] = Index
            if env.CallBack:
                env.CallBack((i + 1) / Times)
                
        env.CallBack = None
        io.SaveArrayAsRaster(Result,
                             OutFile,
                             Projection = TMeanSet.Projection,
                             Transform = TMeanSet.GeoTransform,
                             NoData = TMeanSet.NoData,
                             Format = Format)  
        
    if 'FileType' in kwargs:
        if kwargs['FileType'] == 'Vector':
            CalVe()
            return
    CalRa()
    
class ToolWindow(GeoToWindow):

    def __init__(self, parent = None):
    
        super().__init__(Fun, parent)
        
        ## 添加一个选择按钮
        self.NeedBar = True
        self.NeedFileIO = True
        self.NeedParLayout = True
        # self._sel_in_file_type()
        self.initUI()

        self.AddButtonConnect()
        
        self.Title = Title
        self.setWindowTitle(self.Title)
        self.setWindowIcon(GetIcon(Icon))        

        self.setMinimumWidth(self.SubWinCFG['WindowsSize'][0])
        self.adjustSize() 
        self.Center()
        
