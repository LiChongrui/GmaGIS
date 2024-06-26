# -*- coding: utf-8 -*-

from core.base import UtilWindow
from core.utils import GetIcon

Title = ""
Icon = None
NoWindow = True

class ToolWindow:
    
    def __init__(self, parent = None):
        
        InFile = parent.OpenVectorDialog()
        
        parent.completed.emit({'OutFile':InFile})
        


 