# -*- coding: utf-8 -*-

from .base import *
from .dock import LayerDock

class MainWindow(UtilWindow):
  
    def __init__(self):
        
        super().__init__()
        
        self.MainWinCFG = MainWinCFG
        
        self.BaseUI()  ## 创建基础布局
        
        # self.adjustSize() # 自适应窗口大小
        self.Center() # 将窗口居中
        
        self.show()
    
    def BaseUI(self):
        '''基础 UI 布局'''

        self.setWindowTitle(self.MainWinCFG["Version"])
        # 配置图标
        self.setWindowIcon(QIcon(self.MainWinCFG['WindowIcon']))
        self.setStyleSheet(self.MainWinCFG['StyleSheet'])  # 设置窗口背景为白色

        # 创建布局
        CentralWidget = QWidget()
        self.setCentralWidget(CentralWidget)
        self.BaseLayout = QVBoxLayout(CentralWidget)
        self.BaseLayout.setContentsMargins(10, 4, 10, 0) 
        
        # 0. 添加选项卡布局
        self._tab_layout_()
        
        # 1. 绘图区域布局
        self._plot_layout_()
        
        # 2.底部信息栏
        self._status_bar_()
        
        self.resize(*self.MainWinCFG["WindowsSize"])
        # self.resize(1400, 820)
        
    def _tab_layout_(self):
        '''选项卡布局'''

        from .addtools import CreateTabWidgets
        
        TabWidget = CreateTabWidgets(ToolCFG, self)
        
        self.BaseLayout.addLayout(TabWidget.TabLayout)
            
        # 为选项卡添加项目
        
    def _plot_layout_(self):    
        '''绘图区域布局'''

        self.PlotLayout = QHBoxLayout()
        self.BaseLayout.addLayout(self.PlotLayout)

        #################################################
        # 1 左侧停靠窗口
        self.LayerDock = LayerDock("内容")
        self.PlotLayout.addWidget(self.LayerDock)
        
        ## 1.1 目录树
        self.Tree = self.LayerDock.AddQTree()
        ### 1.1.2 添加一个一级节点
        self.MapTree = self.Tree.AddQTreeItem("地图", Checked = False)
        self.Tree.expandAll()
        
        #################################################
        # 2 绘图区域布局
        TabWidget = QTabWidget()
        TabWidget.setStyleSheet(stl.TabStyle + """
                                QTabBar::tab {
                                    padding: 4px 12px 4px 12px;
                                    }""")

        self.PlotLayout.addWidget(TabWidget)
        
        # 2.0 添加绘图选项卡布局
        PreVW = QWidget()
        TabWidget.addTab(PreVW, "预览")
        PreViewLayout = QVBoxLayout()
        PreVW.setLayout(PreViewLayout)
        
        ## 2.1 创建绘图部件
        from .figure import MatplotlibWidget
        self.MPLWidget = MatplotlibWidget()
        PreViewLayout.addWidget(self.MPLWidget)
        
        ## 2.2 添加 控制部件
        # PreViewLayout.addStretch(1)
        # self.toolbar = NavigationToolbar(self.MPLWidget, self)
        # PreViewLayout.addWidget(self.toolbar)
        
        ## 2.3 其他操作
        xmin, ymin, xmax, ymax = self.MPLWidget.MapF.FrameFeature.Boundary
        self.MPLWidget.Axes.set_xlim(xmin, xmax)
        self.MPLWidget.Axes.set_ylim(ymin, ymax)
        
        ###################### 添加指令
        def plotbase(x):
            
            for ot in ['OutFile', 'OutVector']:
                OutFile = x.get(ot, None)
                if OutFile is not None:
                    break
            if OutFile is None:
                return
            
            if os.path.exists(OutFile):
                try:
                    DataSet = io.ReadRaster(OutFile)
                    GmaPlotItem = self.MPLWidget.AddDataSetDiscrete(DataSet) 
                    Name = DataSet.Name
                except:
                    try:
                        Layer = io.ReadVector(OutFile)
                        GmaPlotItem = self.MPLWidget.AddLayer(Layer, 
                                                              LineWidth = 1,
                                                              FaceColor = None)
                        Name = Layer.Name
                    except:
                        return
                self.MapTree.AddTopLeveItem(Name)    

        self.completed.connect(plotbase)
        self.Tree.itemChanged.connect(self.MPLWidget.handleItemChanged)

    def _status_bar_(self):
        # 创建一个标签用于显示状态栏信息 
        SBar = self.statusBar()
        PLabel = QLabel()
        font = QFont()  
        font.setItalic(True) 
        font.setPointSize(8)
        PLabel.setFont(font) 

        SBar.addPermanentWidget(PLabel)
         
        def update_info():
            cpu_percent = psutil.cpu_percent()
            cpu_cores = psutil.cpu_count(logical=False)
            logical_cores = psutil.cpu_count(logical=True)
    
            # 获取内存信息
            virtual_memory = psutil.virtual_memory()
            total_memory = virtual_memory.total / (1024 ** 3) # 转换为 GB
            used_memory = virtual_memory.used / (1024 ** 3)  # 转换为 GB
            memory_percent = virtual_memory.percent
    
            # 更新标签文本
            PLabel.setText(
                f"CPU：{cpu_percent}% ({cpu_cores}核{logical_cores}线程)  |  "
                f"内存：{memory_percent}% ({used_memory:.2f}/{total_memory:.2f}GB)"
            )                                                   

        import psutil
        update_info()
        
        # 创建一个定时器，每隔一秒更新一次信息
        self.timer = QTimer(self)
        self.timer.timeout.connect(update_info)
        self.timer.start(1000)  # 每隔1000毫秒（1秒）更新一次
        
        

def main():
    
    APP = QApplication(sys.argv)
    Font = QFont(*MainWinCFG['Font']) # 创建一个微软雅黑字体
    APP.setFont(Font) # 将默认字体设置为微软雅黑
    APP.setStyle(MainWinCFG['Style'])
    
    # 创建翻译器实例
    translator = QTranslator()
    # 获取Qt库的安装路径中的翻译文件
    qt_translations_path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    translator.load("qt_" + QLocale.system().name(), qt_translations_path)
    APP.installTranslator(translator)
    
    Window = MainWindow()
    
    sys.exit(APP.exec_())
  
if __name__ == '__main__':

    main()