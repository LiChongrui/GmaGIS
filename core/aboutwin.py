# -*- coding: utf-8 -*-

from .base import UtilWindow
from .iplib import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPixmap, Qt, QGroupBox, 
                    QGridLayout, QFont)
from .utils import icon, MainWinCFG

class AboutWindow(UtilWindow):

    def __init__(self, parent = None):
        
        super().__init__(parent)
        
        ###### 窗口主控件
        self.QWidget = QWidget()
        self.setCentralWidget(self.QWidget)
        self.MainLayout = QVBoxLayout()  

        ########## 生成主体布局
        self.QWidget.setLayout(self.MainLayout) ## 将主布局插入控件中
        
        # self.adjustSize() 
        self.setWindowIcon(icon.GMALOGO)
        self.setWindowTitle('关于')
        self.resize(480, 400)
        
        self.Center()
        # self.show() 
        
    def Version(self):
        VersionLayout = QVBoxLayout() 
        
        ## 添加 logo
        label1 = QLabel() 
        pixmap1 = QPixmap('./icon/logo.svg')
        label1.setPixmap(pixmap1.scaled(160, 160, 
                                        Qt.KeepAspectRatio, 
                                        Qt.SmoothTransformation)) 
        label1.setAlignment(Qt.AlignCenter) 
        VersionLayout.addWidget(label1)  
        
        ## 添加版本
        label2 = QLabel() 
        label2.setText(MainWinCFG["Version"])
        label2.setAlignment(Qt.AlignCenter) 
        
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        label2.setFont(font)
        
        VersionLayout.addWidget(label2) 
        
        ## 添加版本
        label3 = QLabel() 
        label3.setText('地理与气象数据快速处理分析工具软件')
        label3.setAlignment(Qt.AlignCenter) 

        VersionLayout.addWidget(label3) 
        
        self.MainLayout.addLayout(VersionLayout)    

    def Image(self):
        
        GroupFrame = QGroupBox()

        PixFiles = ['./icon/scipy.svg',
                    './icon/pandas.svg',
                    './icon/numpy.svg',
                    './icon/osgeo.svg',
                    './icon/matplotlib.svg']
        
        GroupLayout = QGridLayout()
        for i, f in enumerate(PixFiles):
            label1 = QLabel()  
            pixmap1 = QPixmap(f)  
            label1.setPixmap(pixmap1.scaled(30, 30, 
                                            Qt.KeepAspectRatio, 
                                            Qt.SmoothTransformation))  
            label1.setAlignment(Qt.AlignCenter) 
            label1.setStyleSheet("QLabel {background-color: transparent;}")
            GroupLayout.addWidget(label1, 0, i)

        GroupFrame.setLayout(GroupLayout) 
        
        self.MainLayout.addWidget(GroupFrame)

    def AboutInfo(self):
        
        PipLayout = QHBoxLayout() 
        
        PixFiles = ['./icon/gongzhonghao.jpg',
                    './icon/zanzhu.jpg']
        
        for f in PixFiles:

            label1 = QLabel()  
            pixmap1 = QPixmap(f)  

            label1.setPixmap(pixmap1.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            label1.setAlignment(Qt.AlignCenter) 
            PipLayout.addWidget(label1)  
        
        self.MainLayout.addLayout(PipLayout)       

        PipLayout2 = QHBoxLayout() 
        
        ## 添加版本
        label11 = QLabel() 
        label11.setText('关注公众号')
        label11.setAlignment(Qt.AlignCenter) 
        PipLayout2.addWidget(label11) 
        
        ## 添加版本
        label21 = QLabel() 
        label21.setText('赞助作者（微信）')
        label21.setAlignment(Qt.AlignCenter)
        
        PipLayout2.addWidget(label21)         
        
        self.MainLayout.addLayout(PipLayout2) 
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        