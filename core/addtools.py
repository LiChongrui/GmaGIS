# -*- coding: utf-8 -*-

from .iplib import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, Qt, QWidgetAction,
                    QGridLayout, QTabWidget, QMenu, QToolButton, QSize, partial,
                    QFrame)
from .utils import stl, GetIcon, ReadJson
import importlib

class CreateTabWidgets:
    '''创建选项卡工具栏'''

    def __init__(self, ToolCFG, parent = None):
        
        self.ToolCFG = ToolCFG
        self.parent = parent
        
        ### 选项卡水平分布
        self.TabLayout = QHBoxLayout()
 
        ### 这是一个选项卡控件
        self.TabWidget = QTabWidget()
        self.TabWidget.setStyleSheet(stl.TabStyle)
        # self.TabWidget.setFixedHeight(150)
        self.TabWidget.setFixedHeight(160)
        
        self.TabLayout.addWidget(self.TabWidget)
        
        self._create_tab_()
        
    def _create_tab_(self):
        '''创建选项卡'''
        def _new_tab_(TabName):
            # 添加选项卡
            Tab = QWidget()
            TabLayout = QHBoxLayout()  
            TabLayout.setContentsMargins(10, 4, 10, 4) 

            Tab.setLayout(TabLayout)
            self.TabWidget.addTab(Tab, TabName)

            return TabLayout

        for TabName, TabCfg in self.ToolCFG.items():
            TabLayout = _new_tab_(TabName)
            
            self._create_group_(TabLayout, TabCfg)
            
            ## 添加一个空白弹性空间填充空白区域
            TabLayout.addStretch(1)
    
    def _create_group_(self, TabLayout, TabCfg):
        '''0.创建每个选项卡中功能分组'''
        def _new_group_(GroupName):
            
            ### 0. 垂直布局
            GroupLayout = QVBoxLayout()
            TabLayout.addLayout(GroupLayout)
            
            GroupLayout.setContentsMargins(0, 0, 0, 0)
            
            #### 0.1 添加 功能组布局
            GroupItemLayout = QGridLayout()  
            GroupItemLayout.setHorizontalSpacing(0)  # 设置水平间距
            GroupItemLayout.setVerticalSpacing(0)    # 设置垂直间距
            
            # 设置布局的外部边距 (left, top, right, bottom)
            GroupItemLayout.setContentsMargins(0, 0, 0, 0)            
            
            GroupLayout.addLayout(GroupItemLayout)

            # 0.1.1 添加一个弹性空间
            GroupLayout.addStretch(1)  
            
            ### 0.2 添加一个QLabel作为底部标题
            GroupNameLabel = QLabel(GroupName)
            GroupNameLabel.setAlignment(Qt.AlignCenter) 
            GroupLayout.addWidget(GroupNameLabel, alignment = Qt.AlignCenter)
            
            # GroupLayout.addStretch(1)  
            ###########################
            return GroupItemLayout
        
        ## 读取此选项卡的配置文件
        TabGroupsData = ReadJson(TabCfg.get('path', ''))

        for GroupName, GroupData in TabGroupsData.items():
            
            GroupItemLayout = _new_group_(GroupName) 
            self._create_tool_(GroupItemLayout, GroupData)
            #### 添加一条垂直分割线
            vLine = QFrame()
            vLine.setFrameShape(QFrame.VLine)
            vLine.setStyleSheet("color: lightgray;")
            TabLayout.addWidget(vLine)
            
    def _create_tool_(self, GroupItemLayout, GroupData):
        '''1.创建选项卡内功能或功能组的分组'''

        ToolItems = GroupData.get('Item', {})
        for c, (ToolName, ToolData) in enumerate(ToolItems.items()):
            
            ToolButton = self._create_button_(ToolName, ToolData)

            GroupItemLayout.addWidget(ToolButton, 0, c)

    def _create_button_(self, ToolName, ToolData):
        '''2.为功能或功能组添加按钮 '''
        ToolButton = QToolButton()
        ToolButton.setStyleSheet(stl.ButtonStyle)
        ToolButton.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        ToolButton.setPopupMode(QToolButton.InstantPopup) 
        
        ToolButton.setMinimumWidth(60)
        ToolButton.setMinimumHeight(60)

        Icon = GetIcon(ToolData.get('Icon'))
        ToolButton.setIconSize(QSize(40, 40)) 
        ToolButton.setIcon(Icon)

        ### 添加按钮
        PYName = ToolData.get('PY', None)
        if PYName: ###### 如果是功能
            ToolButton.clicked.connect(partial(self.OpenNewWindow,
                                                ToolName, PYName, Icon))    
        else: ######## 如果功能组
            ToolItems = ToolData.get('Item', {})
            if ToolItems:
                Menu = self._create_menu_(ToolItems)     
                ToolButton.setMenu(Menu)   

        ### 添加名称 
        if ' ' in ToolName:
            ToolName = ToolName.replace(' ', '\n')
        elif '\n' in ToolName:
            pass
        else:
            ToolName = ToolName + '\n'
        ToolButton.setText(ToolName)
        
        ### 添加提示
        Tip = ToolData.get('Tip', '')
        ToolButton.setToolTip(Tip)

        return ToolButton
    
    def _create_menu_(self, ToolData):
        '''3.为功能组添加菜单'''
        menu = QMenu()
        # 添加菜单项到菜单
        for ToolName, ToolConfig in ToolData.items():
            if isinstance(ToolConfig, dict) is False:
                continue
            action = QWidgetAction(self.parent)
            action_widget = self._create_menu_item_(ToolName, ToolConfig)
            action.setDefaultWidget(action_widget)
            menu.addAction(action)
        
        return menu
    
    def _create_menu_item_(self, ToolName, ToolConfig):
        
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)  

        ### 图标标签
        ToolButton = QToolButton()
        ToolButton.setMinimumWidth(60)
        ToolButton.setMinimumHeight(50)
        ToolButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        ToolButton.setStyleSheet(stl.ButtonStyle)

        Icon = GetIcon(ToolConfig.get('Icon'))
        ToolButton.setIcon(Icon)
        ToolButton.setIconSize(QSize(32, 32))
        if ToolName:
            ToolButton.setText(' ' + str(ToolName).ljust(7, "　"))     
 
        ### 提示
        Tip = ToolConfig.get('Tip', '')
        ToolButton.setToolTip(Tip)
        
        layout.addWidget(ToolButton)
        widget.setLayout(layout)
        
        layout.addStretch(1)  
        
        #### 为 按钮添加点击事件
        PYName = ToolConfig.get('PY', '')

        ToolButton.clicked.connect(partial(self.OpenNewWindow,
                                           ToolName, PYName, Icon))
        
        return widget
    
    def OpenNewWindow(self, n, PYName, Icon = None):
        # 打开一个新窗口
        ModuleName = f"tools.{PYName.replace('/', '.')}"
        try:
            Module = importlib.import_module(ModuleName)
        except Exception as E:
            self.parent.MSGBox(3, MSG = f'【{n}】模块异常：{str(E)}！')  
            return
        
        Module.Title = n.replace(' ', '')
        Module.Icon = Icon
   
        NoWindow = getattr(Module, 'NoWindow', False)
        if NoWindow: 
            SubWindow = Module.ToolWindow(self.parent)
        else:
            SubWindow = Module.ToolWindow()
            def emit(obj):
                self.parent.completed.emit(obj)
                
            SubWindow.completed.connect(emit)
            self.parent.SubWindows.append(SubWindow)
            SubWindow.show()

        
