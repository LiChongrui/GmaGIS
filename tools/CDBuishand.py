
from core.geowin import GeoToWindow
from core.iplib import io, np, climet, env, pd, os
from core.utils import GetIcon

Title = None
Icon = None
  
def Fun(InFile, OutFile, BSMethod = 'Q', Format = 'GTiff',
        **kwargs):
    BSMethod = BSMethod.replace('-', ' ')
    def CalVe():
        ATData = io.ReadVector(InFile).AttributeTable
        
        Data = ATData.values
        
        Result = climet.Diagnosis.Buishand(Data,
                                           Axis = 0,
                                           Method = BSMethod
                                           )._asdict()
        
        Type = Result.keys()
        Result = pd.DataFrame(Result.values(), 
                              columns = [f'Col_{i}' for i in range(Data.shape[1])])
        Result.insert(0, column = 'Type', value = Type)
                                         
        Layer = io.ReadDataFrameAsLayer(Result)
        Layer.SaveAs(OutFile, Format = Format)     
    
    def CalRa(): 
        DataSet = io.ReadRaster(InFile)
        
        _, Rows, Columns = DataSet.Bands, DataSet.Rows, DataSet.Columns
        NoData = DataSet.NoData
        
        DataType = DataSet.DataType
        if DataType != 'Float64':
            dt = np.float32
        else:
            dt = np.float64  
        
        ResultLOC = np.zeros((Rows, Columns), dtype = dt)
        ResultSta = np.zeros((Rows, Columns), dtype = dt)
    
        Block = int(np.ceil(env.MaxPT / Columns / 100))
        Slice = list(range(0, Rows, Block))
        Times = len(Slice)
        
        for i, st in enumerate(Slice):
            Data = DataSet.ToArray(TopRow = st, RowSize = Block)
            Sta, Loc = climet.Diagnosis.Buishand(Data,
                                                 Axis = 0,
                                                 Method = BSMethod
                                                 )
            if NoData:
                Loc[Data[0] == NoData] = NoData
                Sta[Data[0] == NoData] = NoData
                
            ResultSta[st:st+Block, :] = Sta
            ResultLOC[st:st+Block, :] = Loc
            if env.CallBack:
                env.CallBack((i + 1) / Times)
                
        env.CallBack = None
        
        BName, EXT = os.path.splitext(OutFile)
        OutFileSta = BName + f'_sta({BSMethod})' + EXT
        
        for n, D in [[OutFile, ResultLOC], 
                     [OutFileSta, ResultSta]]:
            io.SaveArrayAsRaster(D, n,
                                 Projection = DataSet.Projection,
                                 Transform = DataSet.GeoTransform,
                                 NoData = DataSet.NoData,
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