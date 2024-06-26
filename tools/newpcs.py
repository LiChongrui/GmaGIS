# -*- coding: utf-8 -*-

from core.crswin import CreatePCS
from core.utils import GetIcon

Title = ""
Icon = None

class ToolWindow(CreatePCS):
    
    def __init__(self, parent = None):
        
        super().__init__(parent)
        
        self.setWindowIcon(GetIcon(Icon))
        
        self.setWindowTitle(str(Title))
        self.initUI()
        
        self.ButtonOK.setEnabled(False)
        self.show()

 