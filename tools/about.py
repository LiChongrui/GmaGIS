# -*- coding: utf-8 -*-

from core.aboutwin import AboutWindow
from core.utils import GetIcon

Title = ""
Icon = None

class ToolWindow(AboutWindow):
    
    def __init__(self, parent = None):
        
        super().__init__(parent)
        
        self.setWindowIcon(GetIcon(Icon))
        
        self.setWindowTitle(str(Title))
        
        self.Version()
        self.Image()
        self.AboutInfo()

 