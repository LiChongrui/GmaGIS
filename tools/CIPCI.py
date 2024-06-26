
from core.geowin import GeoToWindow
from core.iplib import io, np, climet, env, pd
from core.utils import GetIcon

Title = None
Icon = None
  
def Fun(InFilePRE, OutFile, TimeScale = 1, Periodicity = 12, Format = 'GTiff', 
        **kwargs):
    
    def CalVe():
        ATPre = io.ReadVector(InFilePRE).AttributeTable
        
        PRE = ATPre.values
        
        Result = climet.Index.PCI(PRE,
                                 Axis = 0,
                                 Scale = TimeScale,
                                 Periodicity = Periodicity,
                                 )
        
        Result = pd.DataFrame(Result, 
                              columns = [f'Col_{i}' for i in range(PRE.shape[1])])
                                         
        Layer = io.ReadDataFrameAsLayer(Result)
        Layer.SaveAs(OutFile, Format = Format) 
    
    
    def CalRa(): 
        PRESet = io.ReadRaster(InFilePRE)
        
        Bands, Rows, Columns = PRESet.Bands, PRESet.Rows, PRESet.Columns
        NoData = PRESet.NoData
        
        Block = int(np.ceil(env.MaxPT / Columns / 100))
        Slice = list(range(0, Rows, Block))
        
        Times = len(Slice)
        
        Result = np.zeros((int(np.ceil(Bands / Periodicity)), Rows, Columns))
        
        for i, st in enumerate(Slice):
            PRE = PRESet.ToArray(TopRow = st, RowSize = Block)
            Index = climet.Index.PCI(PRE,
                                     Axis = 0,
                                     Scale = TimeScale,
                                     Periodicity = Periodicity,
                                     )
            if NoData:
                Index[:, PRE[0] == NoData] = NoData
    
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