# -*- coding: utf-8 -*-

from core.vetowin import *
from core.utils import GetIcon

Title = None
Icon = None
  
def Fun(InFile, OutFile, GeometryAttribute = False, Format = 'XLSX'):
    Layer = io.ReadVector(InFile)
    if GeometryAttribute:
        Layer = Layer.CalculateGeometry()
    env.CallBack = None
    Layer.SaveAs(OutFile, Format)
    
class ToolWindow(VeToWindow):

    def __init__(self, parent = None):
    
        super().__init__(Fun, parent)
        
        self.NeedBar = True
        self.NeedFileIO = True
        self.NeedParLayout = True
        
        self.initUI()
        self._rebuild_()

        self.AddButtonConnect()
        
        self.Title = Title
        self.setWindowTitle(self.Title)
        self.setWindowIcon(GetIcon(Icon))        

        self.setMinimumWidth(self.SubWinCFG['WindowsSize'][0])
        self.adjustSize() 
        self.Center()
        
    def _rebuild_(self):
        
        ### 重建指令
        OutD = self.AddPars.query('TypeCode == 10').iloc[0]
        Buttons = OutD['Button']
        SInfo = 'XLSX 文件 (*.xlsx)'
        i = OutD.name
        Buttons[0].clicked.disconnect()
        Buttons[0].clicked.connect(partial(self.SaveFDialog, i, SInfo, Def = 'XLSX'))

