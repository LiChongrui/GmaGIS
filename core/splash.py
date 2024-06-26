# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt
    
class SplashScreen(QSplashScreen):
    
    def __init__(self, pixmap = None):
        self.app = QApplication([]) 
        
        if pixmap is None:
            pixmap = self._rad_image_()
        
        super().__init__(pixmap)
        self.message = ""
        self.font = QFont("Microsoft YaHei", 9)
        # self.font.setBold(True)
        
    def _rad_image_(self):
        '''随机背景'''
        # import random, glob
        # Inputs = glob.glob(r'./icon/splash/*.jpg')
        
        # if Inputs:
            # file = random.choice(Inputs)
            
        file = r'./icon/logo.svg' 
        
        QImage = QPixmap(file).scaled(300, 300,
                                      Qt.KeepAspectRatio, 
                                      Qt.SmoothTransformation)
        return QImage 

    def setMessage(self, message, color = Qt.black, font=None):
        self.message = message
        self.text_color = color
        if font:
            self.font = font
        self.showMessage(self.message, 
                         Qt.AlignBottom | Qt.AlignCenter, 
                         self.text_color)

    def drawContents(self, painter):
        painter.setPen(self.text_color)
        painter.setFont(self.font)
        # 自定义文本绘制位置
        rect = self.rect()
        text_rect = painter.boundingRect(rect, 
                                         Qt.AlignBottom | Qt.AlignCenter, 
                                         self.message)
        x = (rect.width() - text_rect.width()) // 2
        y = int((rect.height() - text_rect.height()) // 6 * 3.8)
        painter.drawText(x, y, self.message)

    
    
    
    
    
    
    
    

