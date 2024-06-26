# -*- coding: utf-8 -*-

from core.base import *
from core.utils import GetIcon
from core.terbut import *
from core.utils import GetIcon
import importlib

class BatchWindow(UtilWindow, ProgressBar, AddPars):
  
    def __init__(self):
        
        super().__init__()
        self.SubWinCFG = SubWinCFG
        self.BaseUI()  ## 创建基础布局

        self.SelTools()

        self.adjustSize() # 自适应窗口大小
        self.Center() # 将窗口居中
        
    def BaseUI(self):
        '''基础 UI 布局'''
        self.setStyleSheet(self.SubWinCFG['StyleSheet'])
        self.setWindowTitle('批处理工具')
        # 配置图标
        self.setWindowIcon(icon.GMALogo)
        
        # 创建布局
        CentralWidget = QWidget()
        self.setCentralWidget(CentralWidget)
        self.MainLayout = QVBoxLayout(CentralWidget)
            
    def Input(self, D):
        # 文件输入输出
        InGBFrame = GroupBox(D)
        InGBFrame.FilesWidget()
        self.MainLayout.addWidget(InGBFrame.GroupFrame)
        
    def Output(self, D):
        
        OutGBFrame = GroupBox(D)
        OutGBFrame.FileWidget()
        self.MainLayout.addWidget(OutGBFrame.GroupFrame)        
        
    def SelTools(self):
        # 选择批处理工具
        self.GroupFrame = QGroupBox('【选择工具】')
        self.GroupFrame.setFixedHeight(80)
        
        self.Module0 = '栅格处理'
        self.Class0 = '基础处理'
        
        self.ToolCFG = ToolCFG.loc[ToolCFG['Batch'] == 1]

        self.Tools = {}
        for d, Dm in self.ToolCFG.groupby('Tool'):
            Cla = {}
            for c, Dc in Dm.groupby('Model'):
                Cla[c] = Dc['CHN'].to_list()
            self.Tools[d] = Cla

        ### 先创建 3 个控件
        ModSelLayout = QHBoxLayout()
        Labels = ['模块', '类别', '模型']
        self.ComB = []
        for i, t in enumerate(Labels):
            SelLayout = QHBoxLayout()
            Label = QLabel(t + ':')            
            ComboBox = QComboBox()
            ComboBox.setStyleSheet(stl.QComboBoxBarStyle)
            if i == 0:
                Items = self.Tools.keys()
            elif i == 1:
                Items = self.Tools[self.Module0].keys()
            else:
                Items = self.Tools[self.Module0][self.Class0]
                self.ForType = 'Ve' if self.Module0 == '矢量处理' else 'Ra'
                self.Tool0 = Items[0]
            ComboBox.addItems(Items)
            ComboBox.setMinimumWidth(160)
            SelLayout.addWidget(Label)
            SelLayout.addWidget(ComboBox)
            self.ComB.append(ComboBox)
            ModSelLayout.addLayout(SelLayout)

        self.GroupFrame.setLayout(ModSelLayout)
        self.MainLayout.addWidget(self.GroupFrame)
        
        self.OtherPAR()

        ################### 参数设置框
        ParGroupFrame = QGroupBox('【模型参数】') 
        self.ParLayout = QVBoxLayout()
        ParGroupFrame.setLayout(self.ParLayout)
        self.MainLayout.addWidget(ParGroupFrame)
        ################### 参数设置框
        
        ########### 初始化默认工具
        self.QWT = None
        self.SetTool(self.Tool0)
        #############
        ### 为三个布局添加监控    
        self.ComB[0].currentTextChanged.connect(self.ModChangeToCla)
        self.ComB[1].currentTextChanged.connect(self.ClaChangeToTool)
        self.ComB[2].currentTextChanged.connect(self.SetTool)
        
        self.AddButton()
        
    def OtherPAR(self):
        ### 其他配置
        OtherGroupFrame = QGroupBox('【通用配置】') 
        self.MainLayout.addWidget(OtherGroupFrame)
        
        OtherLayout = QVBoxLayout()
        OtherGroupFrame.setLayout(OtherLayout)

        # 2.输出文件过滤器
        InF = QGroupBox('输出文件设置')
        OtherLayout.addWidget(InF)
        ### 2.1 创建一个水平布局，开始添加元素
        GLLayout = QHBoxLayout()
        InF.setLayout(GLLayout)   
        
        Label = QLabel('输出格式:') 
        self.ComboBox = QComboBox()
        self.ComboBox.setStyleSheet(stl.QComboBoxBarStyle)
        # self.ComboBox.setMaxVisibleItems(15)
        self.ComboBox.currentTextChanged.connect(self.ForamtChage) 
        
        self.ComboBox.setMinimumWidth(160)
        GLLayout.addWidget(Label)
        GLLayout.addWidget(self.ComboBox)    

        Label = QLabel('标识字符:') 
        self.AddText = QLineEdit()
        self.AddText.setText('_Batch')
        GLLayout.addWidget(Label)
        GLLayout.addWidget(self.AddText)

    def SetTool(self, Value):
        ## 配置工具
        if Value == '':
            return
        SelLoc = (self.ToolCFG['CHN'] == Value)&(self.ToolCFG['Model'] == self.Class0)&(self.ToolCFG['Tool'] == self.Module0)
        ToolPy = self.ToolCFG.loc[SelLoc, 'PY'].iat[0]
        
        ModuleName = f'tools.{ToolPy}'
        Module = importlib.import_module(ModuleName)
        Module.Icon = "GMALogo"
        
        
        self.Fun = Module.Fun
        self.SubWindow = Module.ToolWindow()
        self.Format = self.SubWindow.Format
        
        
        
        ### 更新通用配置
        self.ForType = 'Ve' if self.Module0 == '矢量处理' else 'Ra'
        if self.ForType == 'Ra':
            SelFormats = gft.RasterSummary()._RAConfig
            Deft = 'GTiff'
        else:
            SelFormats = gft.VectorSummary()._VEConfig
            Deft = 'ESRI Shapefile'
        Items = SelFormats.loc[SelFormats['Creation'] == 'Yes'].index
        
        self.ComboBox.clear()
        self.ComboBox.addItems(Items)
        self.ComboBox.setCurrentText(Deft)

        ######################## 修改 TypeCode 信息
        self.AddPars = self.SubWindow.AddPars
        # 移除 InFile 和 OutFile 参数，在外部生成
        self.AddPars.loc[self.AddPars['Name'] == 'InFile', 
                         ['WinName', 'TypeCode']] = ['*输入文件列表', 1]

        self.AddPars.loc[self.AddPars['Name'] == 'OutFile',
                         ['WinName', 'TypeCode']] = ['*输出路径', 11]

        self.SubWindow.DelectAll()
        self.SubWindow.initUI(AddBut = False, NeedBar = False)
        
        ### 删除输入输出控件
        QWT = self.SubWindow.QWidget
        if self.QWT:
            self.ParLayout.replaceWidget(self.QWT, QWT)
            self.QWT.setParent(None)
            self.QWT.deleteLater()
        else:
            self.ParLayout.addWidget(QWT)  
        self.QWT = QWT
        
        self.resize(self.SubWindow.width(), self.SubWindow.height())
        self.adjustSize()
        
    def ForamtChage(self, Text):
        
        
        if self.Format.empty is False:
            self.Format.iat[0] = Text
            self.ComboBox.setEnabled(True)
            self.AddText.setEnabled(True)
        else:
            self.ComboBox.setEnabled(False)
            self.AddText.setEnabled(False)
            self.Format = pd.Series({})
        
        # self.Format.iat[0] = Text
  
    def ModChangeToCla(self, Value):
        ## 模块改变
        self.Module0 = Value
        Classes = list(self.Tools[self.Module0])
        # self.Class0 = Classes[0]
        self.ComB[1].clear()
        self.ComB[1].addItems(Classes)
        
    def ClaChangeToTool(self, Value):
        ## 类别改变
        if Value:
            self.Class0 = Value
            BasTools = self.Tools[self.Module0][self.Class0]
            self.ComB[2].clear()
            self.ComB[2].addItems(BasTools)     
    
    def AddButton(self):
        '''添加按钮'''
        
        ButtonInfo = {"Run": ['运行',  icon.Run], 
                      "Reset": ['重置'
from core.utils import GetIcon.Reset], 
                      "Log": ['日志'
from core.utils import GetIcon.Log]}
        
        GroupFrame = QFrame()
        
        LW = LayoutWidget(BoxLayout = 'H')

        for k, (Name, Icon) in  ButtonInfo.items():
            exec(f'self.Button{k} = LW.Button(Name, Icon)')
            
        GroupFrame.setLayout(LW.MainLayout)
        self.MainLayout.addWidget(GroupFrame)
        
        ####创建日志窗口
        self.LogWin = LogWin()
        
        ### 重置按钮
        self.ButtonReset.clicked.connect(self.Reset)     
        
        ### 运行按钮
        self.ButtonRun.clicked.connect(self.Run)
        
        ### 日志按钮
        self.ButtonLog.clicked.connect(self.Log)
        self.Title = '批处理工具'
        self.HaveBar = True
        self.MainLayout.addLayout(self.BarLayout)
 
    def Run(self):
        '''运行程序'''
        PAR = self.initPARValues()
        
        if PAR == {}:
            return 

        InFiles = PAR['InFile']
        OutPath = PAR['OutFile']

        FileNum = len(InFiles)

        if self.ForType == 'Ra':
            Format = gft.GetRasterFormat(self.Format.iat[0])
        else:
            Format = gft.GetVectorFormat(self.Format.iat[0])
        
        PAR.update(self.Format.to_dict())
        EXT = Format.Extension
        MarkText = self.AddText.text()
        
        def Finished(Value):
            if Value == 'Finish':
                LTInfo = f'\n' 
            else:
                LTInfo = f'{" " *
from core.utils import GetIcon 4}错误：\n{" " *
from core.utils import GetIcon 8}{Value}\n【{GetCurrentTime()}】\n'
                self.MSGBox(3, MSG = Value)
                
            self.LogWin.LogTextEdit.append(LTInfo)
            
            self.PBar.setValue(int((i + 1) / FileNum) *
from core.utils import GetIcon 100)
            
            if i + 1 == FileNum:
                self.ButtonRun.setEnabled(True)
                
        def initPAR():
            ComPAR = dict(zip(self.AddPars.loc[:, 'WinName'], PAR.values()))
            ComPAR.pop('*输入文件列表')
            ComPAR.pop('*输出路径')
            StrPARs = []
            for k, v in ComPAR.items():
                StrPARs.append(f"{' ' *
from core.utils import GetIcon 8}{k} = " +  (f'"{v}"' if isinstance(v, str) else f'{v}'))
            PARInfo =  ',\n'.join(StrPARs) 
            return PARInfo   
        
        def Close(self):  
            self.WorkerThread.quit()
            self.WorkerThread = None  

        self.LogWin.LogTextEdit.append(f'【{GetCurrentTime()}】 || 开始处理...\n{" " *
from core.utils import GetIcon 4}公共参数：')
        self.LogWin.LogTextEdit.append(initPAR())
        self.PBar.setValue(0)
        self.ButtonRun.setEnabled(False)
        
        for i, f in enumerate(InFiles):
            PAR['InFile'] = f
            fName = os.path.basename(f)
            PAR['OutFile'] = f'{OutPath}/{fName[:-(len(fName.split(".")[-1]) + 1)]}{MarkText}{EXT}'
            self.LogWin.LogTextEdit.append(f"{' ' *
from core.utils import GetIcon 4}正在执行({i + 1}/{FileNum})：{f}...")
            self.WorkerThread = WorkerThread(self.Fun, *
from core.utils import GetIcon*PAR)
            # # self.WorkerThread.WTSignal.connect(self.PBSetValue)
            self.WorkerThread.start()
            self.WorkerThread.wait()
            self.WorkerThread.WTFinSig.connect(Close)
            
            self.PBar.setValue(int((i + 1) / FileNum *
from core.utils import GetIcon 100))

        self.LogWin.LogTextEdit.append(f'【{GetCurrentTime()}】 || 任务结束！\n' )
        self.ButtonRun.setEnabled(True)