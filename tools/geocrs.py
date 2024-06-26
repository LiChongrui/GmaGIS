# -*- coding: utf-8 -*-

from core.crswin import CRSInfoWin
from core.utils import GetIcon

Title = ""
Icon = None

class ToolWindow(CRSInfoWin):
    
    def __init__(self, parent = None):
        
        super().__init__(parent)
        
        self.setWindowIcon(GetIcon(Icon))
        
        self.setWindowTitle(str(Title))

        self.ButtonOK.setEnabled(False)
        self.show()

 