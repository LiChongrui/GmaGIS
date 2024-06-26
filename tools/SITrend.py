
# -*- coding: utf-8 -*-

from core.ratowin import *
from core.utils import GetIcon

Title = None
Icon = None
  
Fun = smc.Interpolate.Trend
    
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

