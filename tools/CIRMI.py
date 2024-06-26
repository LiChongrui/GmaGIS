# -*- coding: utf-8 -*-

from core.geowin import GeoToWindow
from core.iplib import io, np, climet, env, pd
from core.utils import GetIcon

Title = None
Icon = None
  
def Fun(InFilePRE, InFilePET, OutFile, TimeScale = 1, Format = 'GTiff', 
        **kwargs):
    
    def CalVe():
        ATPre = io.ReadVector(InFilePRE).AttributeTable
        ATPet = io.ReadVector(InFilePET).AttributeTable
        
        PRE = ATPre.values
        PET = ATPet.values
        
        Result = climet.Index.RMI(PRE, PET, 
                                  Axis = 0,
                                  Scale = TimeScale
                                  )
        
        Result = pd.DataFrame(Result, 
                              columns = [f'Col_{i}' for i in range(PRE.shape[1])])  
                                         
        Layer = io.ReadDataFrameAsLayer(Result)
        env.CallBack = None
        Layer.SaveAs(OutFile, Format = Format) 
        
    def CalRa():
        PRESet = io.ReadRaster(InFilePRE)
        PETSet = io.ReadRaster(InFilePET)
        
        Bands, Rows, Columns = PRESet.Bands, PRESet.Rows, PRESet.Columns
        NoData = PRESet.NoData
        
        DataType = PRESet.DataType
        if DataType != 'Float64':
            dt = np.float32
        else:
            dt = np.float64  
        Result = np.zeros((Bands, Rows, Columns), dtype = dt)
    
        Block = int(np.ceil(env.MaxPT / Columns / 100))
        Slice = list(range(0, Rows, Block))
        Times = len(Slice)
        for i, st in enumerate(Slice):
            PRE = PRESet.ToArray(TopRow = st, RowSize = Block)
            PET = PETSet.ToArray(TopRow = st, RowSize = Block)
            Index = climet.Index.RMI(PRE, PET, 
                                     Axis = 0,
                                     Scale = TimeScale
                                     )
            
            if NoData:
                Index[PRE == NoData] = NoData
            
            Result[:, st:st+Block, :] = Index
            if env.CallBack:
                env.CallBack((i + 1) / Times)
                
        env.CallBack = None
        io.SaveArrayAsRaster(Result,
                             OutFile,
                             Projection = PRESet.Projection,
                             Transform = PRESet.GeoTransform,
                             NoData = PRESet.NoData,
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
        self._sel_in_file_type()
        self.initUI()

        self.AddButtonConnect()
        
        self.Title = Title
        self.setWindowTitle(self.Title)
        self.setWindowIcon(GetIcon(Icon))        

        self.setMinimumWidth(self.SubWinCFG['WindowsSize'][0])
        self.adjustSize() 
        self.Center()
        
        
        