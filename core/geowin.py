# -*- coding: utf-8 -*-

# from .subwin import *
from .iplib import partial
from .ratowin import RaToWindow

class GeoToWindow(RaToWindow):

    def __init__(self, Fun = None, parent = None):

        super().__init__(Fun, parent)
        self.FileType = 'Raster'

    def _sel_in_file_type(self):
        
        from .base import LayoutWidget
        self.Fun = partial(self.Fun, FileType = self.FileType)
        
        LW = LayoutWidget('H')
        self.RadioGroup = LW.RadioButton(Name = '【选择计算数据类型】', 
                                         Radias = ['基于时间序列栅格', 
                                                   '基于矢量属性表或表'])
        
        LW.MainLayout.setContentsMargins(0, 0, 0, 10)
        
        self.RadioGroup.buttonClicked[int].connect(self._reset_con_)  
        
        self.MainLayout.addLayout(LW.MainLayout)
        
    def _reset_con_(self, idx):
        if idx == 1:
            self.FileType = 'Vector'
            ## 改为矢量
            con = {'ReadText': self.ReadVector,
                   'Open': self.OpenVeDialog,
                   'SaveText':self.SaveFileOrDir,
                   'Save':self.SaveVeDialog}
        else:
            ### 改为栅格
            self.FileType = 'Raster'
            con = {'ReadText': self.ReadRaster,
                   'Open': self.OpenRaDialog,
                   'SaveText':self.SaveFileOrDir,
                   'Save':self.SaveRaDialog}
            
        self._reset_infile_(con)
        self.Fun = partial(self.Fun, FileType = self.FileType)
            
    def _reset_infile_(self, con):
        '''重置为矢量'''

        for i, D in self.AddPars.iterrows():
            TC = D['TypeCode']
            TextEdits = D['TextEdit']
            Buttons = D['Button']
            
            if TC in [0, 4]: # 输入
                if TextEdits:
                    TextEdits[0].clear()
                    TextEdits[0].textChanged.disconnect()
                    TextEdits[0].textChanged.connect(partial(con['ReadText'], i))
                    
                if Buttons:  
                    Buttons[0].clicked.disconnect()
                    Buttons[0].clicked.connect(partial(con['Open'], i, D))
            
            elif TC in [10, 12]: # 输出
                if TextEdits:
                    TextEdits[0].clear()
                    TextEdits[0].textChanged.disconnect()
                    TextEdits[0].textChanged.connect(partial(con['SaveText'], i))
                    
                if Buttons:  
                    Buttons[0].clicked.disconnect()
                    Buttons[0].clicked.connect(partial(con['Save'], i))
