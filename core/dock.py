# -*- coding: utf-8 -*-

from .base import *


class LayerDock(QDockWidget):
    
    
    def __init__(self, Name = '图层', parent = None):

        super().__init__(Name, parent)
        
        # 1.1 左侧停靠窗口
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.setStyleSheet(stl.DockStyle)

        # self.setMinimumWidth(200)
        # self.setMaximumWidth(300)
        self.setFixedWidth(300)
        
        self.setMinimumHeight(600)
        
    def AddTopLeveItem(self, Name, i = 0):
        new_item = QTreeWidgetItem([Name])
        self.insertTopLevelItem(i, new_item)
            
    def AddQTree(self): 
        # 创建QTreeWidget并添加到DockWidget中
        self.tree = TopTreeItem()
        self.setWidget(self.tree)
        
        return self.tree
        
class TopTreeItem(QTreeWidget):
    
    def __init__(self):
        
        super().__init__()
        self.setHeaderHidden(True)
        self.setIndentation(15) 
        
    def AddQTreeItem(self, Name, Checked = True, i = 0):
        # 创建树的顶层节点
        SubQTItem = SubTreeItem(Name, Checked, i, self)
 
        return SubQTItem
    
    def AddTopLeveItem(self, Name, Checked = True, i = 0):
        SubQTItem = SubTreeItem(Name, Checked, i)
        
        self.addTopLevelItem(SubQTItem)
        
        return SubQTItem
        

class SubTreeItem(QTreeWidgetItem):
    
    def __init__(self, Name, Checked = True, i = 0, QTree = None):
        super().__init__(QTree)
        self.setText(i, Name) 
        if Checked:
            self.setCheckState(i, Qt.Checked)
        self.setSizeHint(0, QSize(0, 25))

    def AddTopLeveItem(self, Name, Checked = True, i = 0):
        
        SubQTItem = SubTreeItem(Name, Checked, i)
        
        self.insertChild(i, SubQTItem)
        
        return SubQTItem
    
    def AddQTreeItem(self, Name, Checked = True, i = 0):
        
        SubQTItem = SubTreeItem(Name, Checked, i)

        self.addChild(SubQTItem)
        
        return SubQTItem
        

    
    
    


    
    
    
    