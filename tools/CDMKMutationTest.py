
from core.geowin import GeoToWindow
from core.iplib import io, np, climet, env, pd, os
from core.utils import GetIcon

Title = None
Icon = None
  
def Fun(InFile, OutFile, Format = 'GTiff', **kwargs):
    
    def CalVe():
        ATData = io.ReadVector(InFile).AttributeTable
        
        Data = ATData.values
        
        Result = climet.Diagnosis.MKMutationTest(Data, Axis = 0)._asdict()

        env.CallBack = None
        for k, v in Result.items():

            Result = pd.DataFrame(v, 
                                  columns = [f'Col_{i}' for i in range(Data.shape[1])])
            BName, EXT = os.path.splitext(OutFile)
            OutFileU = BName + f'_{k}' + EXT
            Layer = io.ReadDataFrameAsLayer(Result)

            Layer.SaveAs(OutFileU, Format = Format) 
    
    def CalRa():
        DataSet = io.ReadRaster(InFile)
        
        Bands, Rows, Columns = DataSet.Bands, DataSet.Rows, DataSet.Columns
        NoData = DataSet.NoData
        
        DataType = DataSet.DataType
        if DataType != 'Float64':
            dt = np.float32
        else:
            dt = np.float64    
        ResultUFk = np.zeros((Bands, Rows, Columns), dtype = dt)
        ResultUBk = np.zeros((Bands, Rows, Columns), dtype = dt)
    
        Block = int(np.ceil(env.MaxPT / Columns / 100))
        Slice = list(range(0, Rows, Block))
        Times = len(Slice)
        for i, st in enumerate(Slice):
            Data = DataSet.ToArray(TopRow = st, RowSize = Block)
            
            Index = climet.Diagnosis.MKMutationTest(Data, Axis = 0)
            UFk, UBk = Index.UFk, Index.UBk
            
            if NoData:
                UFk[Data == NoData] = NoData
                UBk[Data == NoData] = NoData
                
            ResultUFk[:, st:st+Block, :] = UFk
            ResultUBk[:, st:st+Block, :] = UBk
            if env.CallBack:
                env.CallBack((i + 1) / Times)
                
        env.CallBack = None
        
        BName, EXT = os.path.splitext(OutFile)
        OutFileUFk = BName + '_UFk' + EXT
        OutFileUBk = BName + '_UBk' + EXT
    
        for n, D in [[OutFileUFk, ResultUFk], 
                     [OutFileUBk, ResultUBk]]:
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