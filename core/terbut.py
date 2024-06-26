# -*- coding: utf-8 -*-

from .logwin import LogWin
from .utils import icon, GetCurrentTime
from .iplib import QFrame, pd
from .base import LayoutWidget, WorkerThread

class AddParTools:
    
    def __init__(self):
        self.Title = ''
        self.HaveBar = False

    def AddButton(self, parent = None):
        '''添加按钮'''
        
        ButtonInfo = {"Run": ['运行',  icon.RUN], 
                      "Reset": ['重置', icon.RESET], 
                      "Log": ['日志', icon.LOG]}
        
        GroupFrame = QFrame()
        
        LW = LayoutWidget(BoxLayout = 'H')

        for k, (Name, Icon) in  ButtonInfo.items():
            exec(f'self.Button{k} = LW.Button(Name, Icon)')
            
        GroupFrame.setLayout(LW.MainLayout)
        self.MainLayout.addWidget(GroupFrame)
        
        ####创建日志窗口
        self.LogWin = LogWin(parent)
        
    def Reset(self):
        '''重置'''
        for i, D in self.AddPars.iterrows():
            TextEdits = D['TextEdit']
            Default = None if pd.isna(D['Default']) else str(D['Default'])
            for LE in TextEdits:
                LE.clear()
                LE.setText(Default)
            TableWT = D['TableWT']
            for TWT in TableWT:
                TWT.setRowCount(0)
            ListWT = D['ListWT']  
            for LWT in ListWT:
                LWT.clear()
                
            ComboWT = D['ComboBox']  
            for CWT in ComboWT:
                if Default == None:
                    CWT.setCurrentIndex(0)
                else:
                    CWT.setCurrentText(Default)
        if self.HaveBar:
            self.PBar.setValue(0)
        self.LogWin.LogTextEdit.clear()

    def initPARValues(self):
        ### 初始化运行参数
        NeedButNone = (self.AddPars['Must'] == True)&(pd.isna(self.AddPars['Value']))

        if NeedButNone.any():
            self.MSGBox(3, MSG = f"参数【{'，'.join(self.AddPars.loc[NeedButNone, 'WinName'])}】不能为空！")
            PAR = {}
        else:    
            PAR = dict(self.AddPars.loc[:, ['Name', 'Value']].values)
            
            Format = self.Format.to_dict()
            PAR.update(**Format)
        return PAR
      
    def Run(self):
        '''运行程序'''
        PAR = self.initPARValues()

        self.PBar.setValue(0)
        def Finished(Value):
            if Value == 'Finish':
                LTInfo = f'【{GetCurrentTime()}】 || 处理完成！\n' 
                self.completed.emit(PAR)
            else:
                LTInfo = f'{" " * 4}错误：\n{" " * 8}{Value}\n【{GetCurrentTime()}】 || 任务终止！\n'
                self.MSGBox(3, MSG = Value)
                
            self.LogWin.LogTextEdit.append(LTInfo) 
            self.ButtonRun.setEnabled(True)
            self.ButtonReset.setEnabled(True)
      
        def initPAR():
            StrPARs = []
            PAR = dict(self.AddPars.loc[:, ['WinName', 'Value']].values)
            for k, v in PAR.items():
                StrPARs.append(f"{' ' * 8}{k} = " +  (f'"{v}"' if isinstance(v, str) else f'{v}'))
            PARInfo =  ',\n'.join(StrPARs) 
            return PARInfo
  
        if PAR:
            self.ButtonRun.setEnabled(False)
            self.ButtonReset.setEnabled(False)
            
            self.LogWin.LogTextEdit.append(f'【{GetCurrentTime()}】 || 开始处理...\n{" " * 4}执行参数：')
            self.LogWin.LogTextEdit.append(initPAR())
            
            self.WorkerThread = WorkerThread(self.Fun, **PAR)
            self.WorkerThread.WTSignal.connect(self.PBSetValue)
            self.WorkerThread.WTFinSig.connect(Finished) 
            self.WorkerThread.start()

    def Log(self):
        '''日志'''
        try:
            if self.LogWin.QWidget.isVisible() == True:
                self.LogWin.hide()
                self.LogWin.TaskExecuting = False
                return
        except:
            pass
        self.LogWin.TaskExecuting = True

        self.LogWin.setWindowIcon(icon.LOG)
        self.SubWindows.append(self.LogWin) 
        self.LogWin.setWindowTitle(f'日志 【{self.Title}】')    
        
        ## 窗口大小
        FGeom = self.frameGeometry()
        X, Y, Width = FGeom.x(), FGeom.y(), FGeom.width() 
        Height = self.geometry().height()
        self.LogWin.move(X + Width, Y)
        self.LogWin.resize(Width, Height)
            
        self.LogWin.show()
        
    def AddButtonConnect(self):
        '''为按钮添加指令'''

        ### 运行按钮
        self.ButtonRun.clicked.connect(self.Run)
        
        ### 重置按钮
        self.ButtonReset.clicked.connect(self.Reset)    
        
        ### 日志按钮
        self.ButtonLog.clicked.connect(self.Log)    