# -*- coding: utf-8 -*-

from .base import UtilWindow, LayoutWidget, QWidget
# from .utils import SubWinCFG

class LogWin(UtilWindow, LayoutWidget):
    
    def __init__(self, parent = None):
        
        super().__init__(parent)
        
        ###### 窗口主控件
        self.QWidget = QWidget()
        self.setCentralWidget(self.QWidget)
        
        ########## 生成主体布局
        self.QWidget.setLayout(self.MainLayout) ## 将主布局插入控件中

        self.initUI()
        
    def initUI(self):
        '''初始化UI'''
        
        self.LogTextEdit = self.TextEdit()
        self.LogTextEdit.setReadOnly(True)
        # self.setStyleSheet(SubWinCFG['StyleSheet'])
        self.MainLayout.addWidget(self.LogTextEdit)
        
        # self.setMinimumHeight(SubWinCFG['WindowsSize'][1])
        