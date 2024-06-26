# -*- coding: utf-8 -*-

from .base import UtilWindow, ProgressBar, GroupBox
from .monitor import TextChange
from .utils import GetFunPar, GetParInfo, SubWinCFG
from .terbut import AddParTools
from .iplib import QWidget, QVBoxLayout, QHBoxLayout, pd

class NewWindow(UtilWindow, ProgressBar, TextChange, AddParTools):

    def __init__(self, Fun = None, parent = None):

        super().__init__(parent)

        self.NeedFileIO = True
        self.NeedParLayout = True
        
        self.Fun = Fun
        self.AddPars = self.GetParInfo()
        self.SubWinCFG = SubWinCFG

        ###### 窗口主控件
        self.QWidget = QWidget()  
        self.setCentralWidget(self.QWidget)
        
        ########## 生成主体布局
        self.MainLayout = QVBoxLayout() ## 主布局
        self.QWidget.setLayout(self.MainLayout) ## 将主布局插入控件中

        ########## 初始化 UI
        self.HaveBar = False

    def initUI(self, AddPars = True, AddBut = True, NeedBar = True):
        '''初始化 UI '''
        if AddPars:
            ## 生成控件
            self.GenWidget()
            ## 分配控件样式
            self.WinStyle1()
        
        if AddBut:
            ## 添加点击按钮
            self.AddButton(self)
        
        ## 插入进度条
        if NeedBar:
            self.MainLayout.addSpacing(5)
            self.MainLayout.addLayout(self.BarLayout)
            self.MainLayout.addSpacing(5)
            self.HaveBar = True
        else:
            self.HaveBar = False

        ## 添加文本框监控
        self.AddTextConnect()

    def WinStyle1(self):
        '''按照样式排列控件'''
        ## 输入/输出文件、下拉筛选 控件
        if self.NeedFileIO:
            Query0 = 'TypeCode < 20'
            for i, D in self.AddPars.query(Query0).iterrows():
                GBWig = D['GBWig']
                if GBWig:
                    self.MainLayout.addWidget(GBWig.GroupFrame)
                    self.MainLayout.setSpacing(0)
                
        if self.NeedParLayout:
            Query1 = 'TypeCode < 100 and TypeCode >= 20'
            for i, D in self.AddPars.query(Query1).iterrows():
                GBWig = D['GBWig']
                if GBWig:
                    self.MainLayout.addWidget(GBWig.GroupFrame)
                    self.MainLayout.setSpacing(0)

            ## 其他文本框 控件    
            AddPars = self.AddPars.query('TypeCode >= 100 or TypeCode.isna()')
            i = 0
            SWNum = self.SubWinCFG['StyleParNum']
            
            while i < len(AddPars):
                ParLayout = QHBoxLayout()  # 参数区域的总体布局/水平
                self.MainLayout.addLayout(ParLayout) 
                
                APs = AddPars.iloc[i: i + SWNum]
                if len(APs) < SWNum:
                    for n in range(len(APs), SWNum):
                        APs.loc[f'Temp{n}'] = ''
                i += SWNum
                
                for k, D in APs.iterrows():
                    # 添加 2 级布局
                    ParSub2 = QHBoxLayout()
                    if D['Type'] == '':
                        GBWig = GroupBox(D)
                        GBWig.TextWidget()
                        ParSub2.addWidget(GBWig.GroupFrame)
                    else:
                        GBWig = D['GBWig']
                        if GBWig:
                            ParSub2.addWidget(GBWig.GroupFrame)
                    ParLayout.addLayout(ParSub2)
                
    def GetParInfo(self):
        '''读取函数参数信息'''
        FunPar = GetFunPar(self.Fun)

        ## 记录格式信息
        FormatInfo = FunPar.query('Name in ("OutFormat", "Format")')
        self.Format = pd.Series(dict(zip(FormatInfo['Name'], 
                                         FormatInfo['Default'])))

        FunPar = FunPar.query('Name not in ("self", "OutFormat", "Format")')
        ParInfo = GetParInfo()

        AddPars = pd.merge(FunPar, ParInfo, how = 'left', on = 'Name')
        AddPars = AddPars.sort_values('TypeCode', ignore_index = True)
        
        ## 是否当做默认参数写入窗口标记
        AddPars['SetText'] = ~AddPars['Default'].isna()
        
        ## 控件.布局名称标记
        AddPars['WinName'] = AddPars['CHN']
        NoneLoc = AddPars['WinName'].isna()
        AddPars.loc[NoneLoc, 'WinName'] = AddPars.loc[NoneLoc, 'Name']
        MustLoc = AddPars['Must'] == True
        AddPars.loc[MustLoc, 'WinName'] = "*" + AddPars.loc[MustLoc, 'WinName']
        
        ## 添加其他参数
        Widget = pd.DataFrame(columns = ['GBWig', 'Button', 'TextEdit', 
                                         'ComboBox', 'TableWT', 'ListWT'])  
        
        AddPars = pd.concat([AddPars, Widget], axis = 1).astype('O')
        AddPars['Value'] = AddPars['Default'].astype('O')
        
        return AddPars
        
    def GenWidget(self):
        '''生成控件'''
        for i, D in self.AddPars.iterrows():
            GBWig = GroupBox(D)
            TCode = D['TypeCode']
            if TCode in [0, 4, 10, 12]: # 输入输出控件（单文件）
                GBWig.FileWidget()
            elif TCode == 1: # 多文件输入
                GBWig.FilesWidget()
            elif TCode == 11: # 文件夹
                GBWig.FileWidget()
            elif TCode == 20: # 参数选择型控件
                GBWig.SelectWidget()
                self.AddPars.loc[i, 'Value'] = D['Value']
            elif TCode == 80: # 多窗口参数
                GBWig.MultiTextWidget()
            elif TCode == 40: # 表格窗口
                GBWig.Table()
            elif TCode == 60: # 坐标系窗口
                GBWig.ProjWidget()
            else:
                GBWig.TextWidget()
            
            self.AddPars.loc[i, 'GBWig'] = GBWig
            self.AddPars.loc[i, GBWig.LayoutInfo.keys()] = GBWig.LayoutInfo.values()
    