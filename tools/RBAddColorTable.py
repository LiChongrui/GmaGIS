
# -*- coding: utf-8 -*-

from core.ratowin import *
from core.iplib import QColor
from core.utils import GetIcon


# 模块标题、图标、函数
Title = None
Icon = None
Fun = rasp.Basic.AddColorTable
    
class ToolWindow(RaToWindow):

    def __init__(self, parent = None):
    
        super().__init__(Fun, parent)
        
        ######## 标记是否需要？、进度条
        self.NeedFileIO = True
        self.NeedParLayout = True
        ########
        
        self.Title = Title
        self.setWindowTitle(self.Title)
        self.setWindowIcon(GetIcon(Icon))  
        
        ## 监控输入文件或模版文件
        self.initUI(NeedBar = False)
        self.AddButtonConnect()
        self.SigFile()
        ## 

        self.setMinimumWidth(self.SubWinCFG['WindowsSize'][0])
        self.adjustSize() 
        self.Center()

        self.CTVRange = dict(zip(['Byte', 'Int16', 'UInt16'], [[0, 255], [-256, 255], [0, 65535]]))
        
    def SigFile(self):
        '''重建输入文件或模版文件监控'''
        
        ITextEdit = self.AddPars.loc[self.AddPars['Name'] == "InFile", 'TextEdit']
        TTextEdit = self.AddPars.loc[self.AddPars['Name'] == "TemplateFile", 'TextEdit']
        
        self.InCT = pd.DataFrame(columns = ['值', 'R', 'G', 'B', 'A', '颜色'])
        self.OutCT = self.InCT.copy()
        
        self.TablePar = {}
        X = self.AddPars.index[self.AddPars['Name'] == "ColorTable"][0]
        self.AddPars.at[X, 'Value'] = self.TablePar

        ITextEdit.iat[0][0].textChanged.connect(partial(self.AddInCT, ITextEdit.index[0]))
        TTextEdit.iat[0][0].textChanged.connect(partial(self.AddTeCT, TTextEdit.index[0]))  
        
        self.TableGF = self.AddPars.query('Name == "ColorTable"')["GBWig"].iat[0]
        self.TableGF.Table(self.InCT)
        
        self.QTable = self.TableGF.LayoutInfo['TableWT'][0]
        self.QTable.itemChanged.connect(self.itemChangedFun)  
        # self.QTable.verticalHeader().setVisible(False)

            
    def _CTToDF(self, CT, DataFrame):
        DataFrame[['R', 'G', 'B', 'A']] = pd.DataFrame(CT.values()).values
        DataFrame['值'] = CT.keys()     
        DataFrame['颜色'] = ''
        return DataFrame  
        
    def AddInCT(self, i, Text):
        '''输入文件 ColorTable '''
        
        if Text == "":
            return
        
        DataSet = self.ReadRaster(i, Text)
        
        Format = DataSet.Driver
        DataType = DataSet.DataType
        VT = gft.GetRasterFormat(Format)
        CTDT = VT.ColorTableDataTypes
        
        if DataType in CTDT and DataType in self.CTVRange:
            pass
        else:
            self.MSGBox(3, MSG = f"输入数据格式【{Format}】的数据类型【{DataType}】不支持色彩映射表！")
            return
        
        D = self.AddPars.loc[i]
        CT = DataSet.GetColorTable()
        
        if CT == {}:
            self.InCT['值'] = range(*self.CTVRange[DataType])
            self.InCT[['R', 'G', 'B']] = 0
            self.InCT[['A']] = 255
            self.InCT['颜色'] = ''
        else:
            self.InCT = self._CTToDF(CT, self.InCT)  
        
        if self.OutCT.empty:
            pass
        else:
            InLen = len(self.InCT)
            OutLen = len(self.OutCT)
            
            if InLen < OutLen:
                return
            else:
                self.InCT.loc[:len(self.OutCT)] = self.OutCT.values
        
        self.TableGF.Table(self.InCT)

    def AddTeCT(self, i, Text):
        '''模版文件 ColorTable '''
        
        if Text == "":
            return

        DataSet = self.ReadRaster(i, Text)
        D = self.AddPars.loc[i]
        CT = DataSet.GetColorTable()
    
        if CT == {}:
            return
        else:
            self.OutCT = self._CTToDF(CT, self.OutCT)   
            
            InLen = len(self.InCT)
            OutLen = len(self.OutCT)   
            if InLen > OutLen:
                self.OutCT = pd.concat([self.OutCT, self.InCT[OutLen:]])
            else:
                self.OutCT = self.OutCT[:InLen]

            self.TableGF.Table(self.OutCT)
        
    def itemChangedFun(self, item):
        '''表发生变化的处理'''
        r = item.row()
        c = item.column()
        RGBA = []
        for i in range(1, 5):
            try: 
                C = int(self.QTable.item(r, i).text())
            except:
                C = 0
            C = 255 if C > 255 else (0 if C < 0 else C)
                
            RGBA.append(C)

        try:
            Color = QColor(*RGBA)
            self.QTable.item(r, 5).setBackground(Color)
        except:
            pass
        try:
            Value = int(self.QTable.item(r, 0).text())
        except:
            Value = 0

        self.TablePar[Value] = tuple(RGBA)

            
