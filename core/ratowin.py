# -*- coding: utf-8 -*-

from .iplib import partial, rasp, pd, gft
from .subwin import NewWindow
from .utils import icon

class RaToWindow(NewWindow):

    def __init__(self, Fun = None, parent = None):

        super().__init__(Fun, parent)
     
    def AddTextConnect(self):
        
        '''为参数添加指令'''
        for i, D in self.AddPars.iterrows():
            
            TC = D['TypeCode']
            TextEdits = D['TextEdit']
            ComboBoxs = D['ComboBox']
            Buttons = D['Button']
            
            if TC == 0: # 输入栅格
                if TextEdits:
                    TextEdits[0].textChanged.connect(partial(self.ReadRaster, i))
                if Buttons:  
                    Buttons[0].clicked.connect(partial(self.OpenRaDialog, i, D))
            elif TC == 10: # 输出栅格
                if TextEdits:   
                    TextEdits[0].textChanged.connect(partial(self.SaveFileOrDir, i))
                if Buttons:  
                    Buttons[0].clicked.connect(partial(self.SaveRaDialog, i))
            elif TC == 1: # 输出栅格列表
                if Buttons:  
                    Button = Buttons[0]
                    MemuWidget = Button.menu()
                    SelectFileAction = MemuWidget.actions()[0]
                    SelectFileAction.triggered.connect(partial(self.OpenRaFsDialog, i, D))
                    
                    SelectDirAction = MemuWidget.actions()[1]
                    SelectDirAction.triggered.connect(partial(self.OpenRaFsFromDirDialog, i, D))
                
            elif TC == 4: # 输入矢量
                if TextEdits:   
                    TextEdits[0].textChanged.connect(partial(self.ReadVector, i))
                if Buttons:  
                    Buttons[0].clicked.connect(partial(self.OpenVeDialog, i, D))  
            elif TC == 12: # 输出矢量
                if TextEdits:   
                    TextEdits[0].textChanged.connect(partial(self.SaveFileOrDir, i))
                if Buttons:  
                    Buttons[0].clicked.connect(partial(self.SaveVeDialog, i))
            elif TC == 11: # 文件夹路径
                if TextEdits:   
                    TextEdits[0].textChanged.connect(partial(self.SaveFileOrDir, i))
                if Buttons:  
                    Buttons[0].clicked.connect(partial(self.OpenDir, i))
            elif TC == 60: # 坐标系
                if TextEdits:   
                    TextEdits[0].textChanged.connect(partial(self.PYText, i))
                if Buttons:
                    Buttons[0].clicked.connect(partial(self.OpenProjWin, D))
            else:
                if TextEdits:
                    for TE in TextEdits:
                        TE.textChanged.connect(partial(self.PYText, i))
                if ComboBoxs:
                    for CB in ComboBoxs:
                        # CB.currentIndexChanged.connect(partial(self.PYComb, i))    
                        CB.currentTextChanged.connect(partial(self.PYComb, i))  
