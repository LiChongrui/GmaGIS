# -*- coding: utf-8 -*-

from core.vetowin import *
from core.utils import GetIcon

Title = None
Icon = None
  
def Fun(InFile, OutFile, MethodFile, Format = 'ESRI Shapefile'):
    Layer = io.ReadVector(InFile)
    MLayer = io.ReadVector(MethodFile)
    Result = Layer.Clip(MLayer)
    
    env.CallBack = None

    Result.SaveAs(OutFile, Format)
    
class ToolWindow(VeToWindow):

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

