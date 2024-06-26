# -*- coding: utf-8 -*-

from .base import (UtilWindow, LayoutWidget, SearchWidget)
from .figure import MatplotlibWidget
                  
from .iplib import (crs, QWidget, QLineEdit, QHBoxLayout, QGroupBox, QPushButton, 
                    QAction, QMenu, QVBoxLayout, QFont, inres, QFrame,QLabel, 
                    QComboBox, QDoubleValidator)
from .utils import stl, icon, GetFunPar


class CRSUtil(UtilWindow, LayoutWidget):
    
    def __init__(self, parent = None, BoxLayout = 'H'):
        
        UtilWindow.__init__(self, parent)
        LayoutWidget.__init__(self, BoxLayout = BoxLayout)

        ###### 窗口主控件
        self.QWidget = QWidget()
        self.setCentralWidget(self.QWidget)
        
        ########## 生成主体布局
        self.QWidget.setLayout(self.MainLayout) ## 将主布局插入控件中
        
        self.Spat = None
        
    def save(self):
        
        self._create_cs_()
        
        SInfo = ';;'.join(['GIS 通用投影文件 (*.prj)',
                           'GMA 投影文件 (*.gsr)',
                           'Proj4 投影文件 (*.p4)'])
        OutFile, SelFormat = self.SaveFileDialog(SInfo, 'GIS 通用投影文件 (*.prj)')
        if OutFile == '':
            return
        try:
            Format = SelFormat.split()[0]
            if Format == 'Proj4':
                Proj = self.Spat.Export('Proj4')
            elif Format == 'GMA':
                Proj = str({'WKT':self.Spat.Export(), 
                            'Metadata': self.Spat._metadata})
            else:
                Proj = self.Spat.Export()  
            with open(OutFile, 'w') as f:
                f.write(Proj)
            self.MSGBox(MSG = '文件已保存。')   
        except Exception as E:
            self.MSGBox(3, MSG = f'错误：{str(E)}\n无法保存文件！')  
            
    def _create_cs_(self):
        pass
            
    def confirmEvent(self, event):
        '''确定事件'''
        try:
            self._create_cs_()
        except Exception as E:
            self.MSGBox(3, MSG = f'错误：{str(E)}\n无法创建坐标系！')  
            return
        
        self.confirmed.emit()
        self.closeEvent(event)
        
    def _button_frame_(self):
        '''添加控制按钮'''

        LW = LayoutWidget(BoxLayout = 'H')

        self.ButtonOK = LW.Button('确定', icon.CONFIRM)
        self.ButtonSave = LW.Button('保存', icon.SAVE)
            
        GroupFrame = QFrame()    
        GroupFrame.setLayout(LW.MainLayout)

        self.MainLayout.addWidget(GroupFrame)

        self.ButtonOK.clicked.connect(self.confirmEvent)

        self.ButtonSave.clicked.connect(self.save) 
        
        return GroupFrame
    
    def _add_button_(self):
        
        BuFrame = self._button_frame_()
        self.MainLayout.addWidget(BuFrame)
    
    def _create_tip_label_(self):
        
        TipLabel = QLabel()
        font = QFont()  
        font.setItalic(True) 
        font.setPointSize(7)
        TipLabel.setFont(font) 
        
        return TipLabel
    
    def _create_geogcs_(self):
        '''新建地理坐标系'''
        GCSWin = CreateGCS()
        self.SubWindows.append(GCSWin)
        GCSWin.initUI()
        
        def SetSpat():
            if GCSWin.Spat is None:
                return
            self._reset_info_(GCSWin.Spat)
            
        GCSWin.confirmed.connect(SetSpat)

    def _create_projcs_(self):
        '''新建投影坐标系'''
        PCSWin = CreatePCS()
        self.SubWindows.append(PCSWin)
        PCSWin.initUI()
        
        def SetSpat():
            if PCSWin.Spat is None:
                return
            self._reset_info_(PCSWin.Spat)
            
        PCSWin.confirmed.connect(SetSpat)
        
class CRSInfoWin(CRSUtil):
    
    def __init__(self, parent = None, BoxLayout = 'H'):
        
        super().__init__(parent, BoxLayout)

        self.initUI()

        # self.adjustSize() # 自适应窗口大小
        self.Center() # 将窗口居中
        
        # self.show()
        
    def initUI(self):
        '''初始化UI'''
        self.setWindowIcon(icon.WORLD)
        self.setWindowTitle('坐标系')

        self.setFixedSize(900, 720)
        
        #### 1.添加坐标系必要控件
        self.SpatLayout = QVBoxLayout() 
        self.MainLayout.addLayout(self.SpatLayout)
        
        #### 1.1 左上方坐标名和坐标创建按钮  
        self.NameLayout = QHBoxLayout()
        self.SpatLayout.addLayout(self.NameLayout)
        self._name_()
        self._create_()
        
        #### 1.2 坐标系信息
        self.InfoLayer = QHBoxLayout()
        self.SpatLayout.addLayout(self.InfoLayer)
        self._spat_info_()
        
        #### 1.3 范围绘图
        self.AreaLayer = QHBoxLayout()
        self.SpatLayout.addLayout(self.AreaLayer)
        self._plot_area_of_use_()
        
        #### 1.4 添加控制按钮
        self.CONLayer = QHBoxLayout()
        self.SpatLayout.addLayout(self.CONLayer)
        BuFrame = self._button_frame_()
        self.CONLayer.addWidget(BuFrame)
        
        #### 2.预定义坐标筛选
        self.DauSpatLayout = QVBoxLayout() 
        self.MainLayout.addLayout(self.DauSpatLayout)
        self._dau_spat_()

    def _dau_spat_(self):
        '''预定义坐标系'''
        with open('./core/crs.gd') as f:

            self.SearchFrame = SearchWidget('选择预定义坐标系', f)
            
            self.SearchFrame.searchLineEdit.setMinimumWidth(300)
            
            self.DauSpatLayout.addWidget(self.SearchFrame.GroupFrame)
            
            self.SearchFrame.listWidget.currentItemChanged.connect(self._change_info_)
    
    def _change_info_(self):
        Item = self.SearchFrame.listWidget.currentItem().text().split()[0]
        
        try:
            Spat = crs.SpatRef(Item.split(':')[1])
        except:
            Spat = crs.SpatRef(Item)

        self._reset_info_(Spat)
        
    def _reset_info_(self, Spat):
        
        ## 0.修改名称
        self.NameEdit.clear()
        self.NameEdit.setText(Spat.Name)

        ## 1.修改属性
        PM = Spat.ProjMethod
        PM = '' if PM is None else PM
        Type = Spat.Type
        if 'geographic' in Type.lower():
            Unit = Spat.AngularUnits
        else:
            Unit = Spat.LinearUnits
            
        WKID = Spat.WKID
        if WKID[0] == WKID[1] == '':
            WKID = ('0000', 'GMA')

        Items = ["注册ID：%s %s" % tuple(WKID),
                f"类　型：{Type}",
                "单　位：%s %s" % tuple(Unit),
                f"投　影：{PM}",
                f"基准面：{Spat.DatumName}",
                f"椭球体：{Spat.SpheroidName}",
                "范　围：%.6s°(西)  %.5s°(南)  %.6s°(东)  %.5s°(北)" % tuple(Spat.AeraOfUse),
                ]
        for i, n in enumerate(Items):  
            LineE = self.SpatPAR[i]
            LineE.clear()
            LineE.setText(n)
            
        ## 2.修改图
        Colls = self.MPLWidget.Axes.collections
        if len(Colls) > 1:
            Colls[1].remove()
        try:
            self.MPLWidget.MapF.AddFeature(Spat.GetUseFeatureInWGS84(),
                                           FaceColor = [1, 0.84, 0, 0.4],
                                           LineColor = 'red', LineWidth = 0.7)

            self.MPLWidget.Axes.set_xlim(-181, 181)
            self.MPLWidget.Axes.set_ylim(-91, 91)
        except:
            pass

        self.MPLWidget.draw_idle() 

        self.Spat = Spat

    def _plot_area_of_use_(self):
        '''添加绘制区域'''

        self.MPLWidget = MatplotlibWidget()

        self.AreaLayer.addWidget(self.MPLWidget)
        
        BMap = inres.WorldLayer.Land.Simplify(0.2)
        self.MPLWidget.AddLayer(BMap, FaceColor = '#E6E6FA', 
                                AutoSimplify = False,
                                LineColor = 'lightgray', 
                                LineWidth = 0.1)

        self.MPLWidget.Axes.set_xlim(-181, 181)
        self.MPLWidget.Axes.set_ylim(-91, 91)

        self.MPLWidget.draw_idle() 

    def _spat_info_(self):
        '''坐标系信息'''
        Items = ["注册ID：", "类　型：", "单　位：", "投　影：",
                 "基准面：", "椭球体：", "范　围: "]
  
        self.SpatPAR = []   
        
        GroupFrame = QGroupBox('基础属性')
        ItemLayer = QVBoxLayout() 
        for n in Items:  

            NameEdit = QLineEdit()
            NameEdit.setText(n)
            
            NameEdit.setReadOnly(True)
            NameEdit.setStyleSheet('background-color:transparent;border:none;')  

            ItemLayer.addWidget(NameEdit)
            
            self.SpatPAR.append(NameEdit)
            
        GroupFrame.setLayout(ItemLayer)
        
        self.InfoLayer.addWidget(GroupFrame)
        
    def _name_(self):
        '''坐标系名称'''

        GroupFrame = QGroupBox('当前坐标系')
        NameLayout = QHBoxLayout()  # 输入输出布局/水平
        
        self.NameEdit = QLineEdit()
        NameLayout.addWidget(self.NameEdit)
        
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.NameEdit.setFont(font)
        
        GroupFrame.setLayout(NameLayout)
        self.NameEdit.setReadOnly(True)
        self.NameEdit.setStyleSheet('''background-color:transparent;border:none;''')  
        self.NameEdit.setMinimumHeight(25)
        self.NameEdit.setMinimumWidth(350)

        self.NameLayout.addWidget(GroupFrame)
   
    def _create_(self):
        '''创建坐标系''' 
        GroupFrame = QGroupBox('创建坐标系')
        NewProjLayout = QVBoxLayout()  # 输入输出布局/水平
        
        ### 导入
        InputButton = QPushButton('导入.. ')
        InputButton.setStyleSheet(stl.ButtonStyle)
        InputButton.setIcon(icon.INPUT)
        
        NewProjLayout.addWidget(InputButton)

        ### 创建
        Button = QPushButton("新建.. ")
        Button.setStyleSheet(stl.ButtonStyle)
        Button.setIcon(icon.NEWCRS)
        
        Menu = QMenu()
        self.GeogAction = QAction('新建地理坐标系', Button)
        self.ProjAction = QAction('新建投影坐标系', Button)
        Menu.addAction(self.GeogAction) 
        Menu.addAction(self.ProjAction)
        Button.setMenu(Menu)  
        
        NewProjLayout.addWidget(Button)

        #################
        GroupFrame.setLayout(NewProjLayout)
 
        self.NameLayout.addWidget(GroupFrame)
        
        InputButton.clicked.connect(self._read_file_)
        
        self.GeogAction.triggered.connect(self._create_geogcs_)

        self.ProjAction.triggered.connect(self._create_projcs_)
        
    def _read_file_(self):
        
        SInfo = ';;'.join(['投影文件 (*.prj *.gsr *.p4)'])
        InFile = self.OpenFileDialog(SInfo)

        if InFile == '':
            return
        try:
            with open(InFile, 'r') as f:
                ProjData = f.read()
                if InFile.lower().endswith('.gsr'):
                    ProjData, Metadata = eval(ProjData).values()
                    Spat = crs.SpatRef(ProjData)
                    Spat._metadata = Metadata
                else:
                    Spat = crs.SpatRef(ProjData)
                self._reset_info_(Spat)
        except:
            self.MSGBox(3, MSG = f'无法读取投影文件 {InFile} ！')  
    
class CreatePCS(CRSUtil):
    
    def __init__(self, parent = None, BoxLayout = 'V'):
        
        super().__init__(parent, BoxLayout)
        self.ProjMDict = {'CentralMeridian': ['中央子午线：'],
                          'StandardParallels1': [' 标准纬线 1：'],
                          'StandardParallels2': [' 标准纬线 2：'],
                          'CentralLongitude': ['　中央经线：'],
                          'CentralLatitude': ['　中央纬线：'],
                          'FalseEasting': ['　东偏移量：'],
                          'FalseNorthing': ['　北偏移量：'],
                          'ScaleFactor': ['　比例因子：'],
                          'OriginLatitude': ['　起始纬度：'],
                          }
        self.GCS = 'WGS84'

    def initUI(self):
        '''初始化UI'''
        
        self.setWindowIcon(icon.PROJCS)
        self.setWindowTitle('新建投影坐标系')
        self.setMinimumWidth(500)
        
        self._pcs_name_()
        self._pcs_lunit_() 
        self._pcs_projm_()
        self._geogcs_()
        self._area_of_use_()
        
        self._add_button_()
        
        self.adjustSize() 
        self.Center() # 将窗口居中
        
        self.show()
        
    def _area_of_use_(self):
        #### 4.使用范围
        NameFrame = QGroupBox('使用范围')
        NameFrame.setStyleSheet(stl.QGroupBoxStyle) 

        LW = LayoutWidget()

        AreaOfUse = self.ProjMethod().AeraOfUse
        
        LW.Label('西:')
        self.AreaWEdit = LW.LineEdit()
        self.AreaWEdit.setText(str(AreaOfUse[0]))
        self.AreaWEdit.setValidator(QDoubleValidator())
        LW.Label('南:')
        self.AreaSEdit = LW.LineEdit()
        self.AreaSEdit.setText(str(AreaOfUse[1]))
        self.AreaSEdit.setValidator(QDoubleValidator())
        LW.Label('东:')
        self.AreaEEdit = LW.LineEdit()
        self.AreaEEdit.setText(str(AreaOfUse[2]))
        self.AreaEEdit.setValidator(QDoubleValidator())
        LW.Label('北:')
        self.AreaNEdit = LW.LineEdit()
        self.AreaNEdit.setText(str(AreaOfUse[3]))
        self.AreaNEdit.setValidator(QDoubleValidator())
        
        NameFrame.setLayout(LW.MainLayout)
        
        self.MainLayout.addWidget(NameFrame)

    def _create_cs_(self):
        
        if self.Spat is not None:
            return

        Name = self.NameEdit.text()
        LUnit = self.LUnitComboBox.currentText()
        
        #############
        Fun = getattr(crs.ProjMethod, self.ProjMComboBox.currentText())
        FunPars = GetFunPar(Fun)
        ParNames = FunPars['Name'].to_list()
        
        Pars = {n: float(self.ProjMDict[n][2].text()) for n in ParNames}
        ProjM = Fun(**Pars)
        #############
    
        GCS = self.GCS

        AOF = [float(self.AreaWEdit.text()), 
               float(self.AreaSEdit.text()),
               float(self.AreaEEdit.text()), 
               float(self.AreaNEdit.text())]

        PCS = crs.ProjCS(Name, LUnit, ProjM, GCS, AOF)
        self.Spat = PCS


    def _geogcs_(self):
        #### 3.地理坐标系
        GCSFrame = QGroupBox('地理坐标系')
        GCSFrame.setStyleSheet(stl.QGroupBoxStyle) 
        
        
        GCSLayout = QVBoxLayout()
        GCSFrame.setLayout(GCSLayout)
        ##################
        
        LW = LayoutWidget()
        self.GCSEdit = LW.LineEdit(True)
         
        self.GCSButton = LW.Button('...', icon.GEOGCS, FixSize = False)
        
        GCSLayout.addLayout(LW.MainLayout)
        
        self.MainLayout.addWidget(GCSFrame)
        
        self.GCSButton.clicked.connect(self._create_geogcs_)

        ########### 值提示标签
        TipLabel = self._create_tip_label_()
        GCSLayout.addWidget(TipLabel)
        self.MainLayout.addLayout(GCSLayout)
        
        ###########
        def currentChanged(Text):
            GCS = crs.SpatRef(self.GCSEdit.text())
            TipLabel.setText(f"角度单位  {GCS.AngularUnits[0]}    "
                             f"本初子午线  {GCS.Primem[0]}    "
                             f"长半轴  {GCS.SemiMajor}    "
                             f"反扁率  {GCS.InvFlattening}"
                             )
            
        self.GCSEdit.textChanged.connect(currentChanged)      
        
        self.GCSEdit.setText('WGS84') 

    def _create_geogcs_(self):
        '''创建地理坐标系窗口'''
        NewCRSWin = CreateGCS()
        self.SubWindows.append(NewCRSWin)
        NewCRSWin.initUI()

        def SetSpat():
            if NewCRSWin.Spat is None:
                return
            WKID = NewCRSWin.Spat.WKID
            if WKID[0]:
                Proj = f'{WKID[1]}:{WKID[0]}'
            else:
                Proj = NewCRSWin.Spat.Export()
                
            self.GCSEdit.setText(Proj)     
            
            self.GCS = NewCRSWin.Spat
 
        NewCRSWin.confirmed.connect(SetSpat)

    def _pcs_name_(self):
        #### 1.名称布局
        NameFrame = QGroupBox('坐标系名')
        NameFrame.setStyleSheet(stl.QGroupBoxStyle) 
        
        self.NameEdit = QLineEdit()
        self.NameEdit.setText('GMA PCS')  
        
        NameLayout = QHBoxLayout()
        NameLayout.addWidget(self.NameEdit) 
        NameFrame.setLayout(NameLayout)
        
        self.MainLayout.addWidget(NameFrame)
        
    def _pcs_lunit_(self):
        #### 2.线性单位
        AUnitFrame = QGroupBox('线性单位')
        AUnitFrame.setStyleSheet(stl.QGroupBoxStyle) 
        
        Items = [n for n in dir(crs.LinearUnits) if '_' not in n]
        self.LUnitComboBox = QComboBox()
        self.LUnitComboBox.setStyleSheet(stl.QComboBoxBarStyle)
        self.LUnitComboBox.setMaxVisibleItems(15)
        self.LUnitComboBox.addItems(Items)
        
        AUnitLayout = QVBoxLayout()
        AUnitLayout.addWidget(self.LUnitComboBox) 
        
        ########### 值提示标签
        TipLabel = self._create_tip_label_()
        AUnitLayout.addWidget(TipLabel)
        ###########

        def currentChanged(Text):
            Text = str(getattr(crs.LinearUnits, Text, ''))
            TipLabel.setText('米  ' + Text)
            
        self.LUnitComboBox.currentTextChanged.connect(currentChanged)      
        self.LUnitComboBox.setCurrentText('Meter')

        AUnitFrame.setLayout(AUnitLayout)
        
        self.MainLayout.addWidget(AUnitFrame)  
        
    def _pcs_projm_(self):
        
        #### 3.投影方法
        ProjMFrame = QGroupBox('投影方法')
        ProjMFrame.setStyleSheet(stl.QGroupBoxStyle) 
        
        Items = [n for n in dir(crs.ProjMethod) if '_' not in n 
                 and 'Unit' not in n]
        self.ProjMComboBox = QComboBox()
        self.ProjMComboBox.setStyleSheet(stl.QComboBoxBarStyle)
        self.ProjMComboBox.setMaxVisibleItems(15)
        self.ProjMComboBox.addItems(Items)
        
        self.ProjMLayout = QVBoxLayout()
        self.ProjMLayout.addWidget(self.ProjMComboBox) 
        
        ###########################
        for k, v in self.ProjMDict.items():
            LW = LayoutWidget()
            n = v[0]    
            Label = LW.Label(n)
            Label.setMinimumWidth(80)
            # Label.setAlignment(Qt.AlignRight)
            LineEdit = LW.LineEdit()
            LineEdit.setValidator(QDoubleValidator())
            self.ProjMDict[k] += [Label, LineEdit]
            self.ProjMLayout.addLayout(LW.MainLayout)
        ###################################

        self.ProjMComboBox.currentTextChanged.connect(self._reset_projm_pars_)

        self.ProjMComboBox.setCurrentText('AlbersConicEqualArea')

        ProjMFrame.setLayout(self.ProjMLayout)
        
        self.MainLayout.addWidget(ProjMFrame)  
        
    def _reset_projm_pars_(self, ProjM):
        '''重置投影方法参数布局'''
        self.ProjMethod = getattr(crs.ProjMethod, ProjM)
        FunPars = GetFunPar(self.ProjMethod)
        
        ParNames = FunPars['Name'].to_list()
        
        for n, v in self.ProjMDict.items():

            if n in ParNames:
                font = QFont()
                font.setPointSize(8)
                # font.setBold(True)
                self.ProjMDict[n][1].setFont(font)
                self.ProjMDict[n][2].setReadOnly(False)
                self.ProjMDict[n][2].setStyleSheet('')
                DefV = FunPars.loc[FunPars['Name'] == n, 'Default'].iat[0]
                self.ProjMDict[n][2].setText(str(DefV))
                font1 = QFont()
                font1.setPointSize(8)
                self.ProjMDict[n][2].setFont(font1)
            else:
                font = QFont()
                font.setPointSize(8)
                font.setItalic(True) 
                self.ProjMDict[n][1].setFont(font)
                self.ProjMDict[n][2].clear()
                self.ProjMDict[n][2].setReadOnly(True)
                self.ProjMDict[n][2].setStyleSheet('background-color: #F5F5F5;')
                self.ProjMDict[n][2].setFont(font)


class CreateGCS(CRSUtil):
    
    def __init__(self, parent = None, BoxLayout = 'V'):
        
        super().__init__(parent, BoxLayout)

    def initUI(self):
        '''初始化UI'''
        self.setWindowIcon(icon.GEOGCS)
        self.setWindowTitle('新建地理坐标系')
        self.setMinimumWidth(550)
        # self.setFixedSize(900, 680)
        
        self._gcs_name_()
        self._gcs_aunit_()
        self._gcs_primem_()
        self._gcs_datum_()
        self._gcs_ellip_()
        self._add_button_()
        
        self.adjustSize() 
        self.Center() # 将窗口居中
        
        self.show()
   
    def _create_cs_(self):
        
        if self.Spat is not None:
            return
        
        Name = self.NameEdit.text()
        AUnit = self.AUnitComboBox.currentText()
        Primem = self.PrimemComboBox.currentText()

        Ellip = self.EllipComboBox.currentText()

        Datum = crs.Datum(self.DatumEdit.text(), EllipsoidName = Ellip)

        GCS = crs.GeogCS(Name, AUnit, Primem, Datum = Datum)
        
        self.Spat = GCS
              
    def _gcs_name_(self):
        #### 1.名称布局
        NameFrame = QGroupBox('坐标系名')
        NameFrame.setStyleSheet(stl.QGroupBoxStyle) 
        
        self.NameEdit = QLineEdit()
        self.NameEdit.setText('GMA GCS')  
        
        NameLayout = QHBoxLayout()
        NameLayout.addWidget(self.NameEdit) 
        NameFrame.setLayout(NameLayout)
        
        self.MainLayout.addWidget(NameFrame)
        
    def _gcs_aunit_(self):
        
        #### 2.角度单位
        AUnitFrame = QGroupBox('角度单位')
        AUnitFrame.setStyleSheet(stl.QGroupBoxStyle) 
        
        Items = [n for n in dir(crs.AngularUnits) if '_' not in n]
        self.AUnitComboBox = QComboBox()
        self.AUnitComboBox.setStyleSheet(stl.QComboBoxBarStyle)
        self.AUnitComboBox.setMaxVisibleItems(15)
        self.AUnitComboBox.addItems(Items)
        

        AUnitLayout = QVBoxLayout()
        AUnitLayout.addWidget(self.AUnitComboBox) 
        
        ########### 值提示标签
        TipLabel = self._create_tip_label_()
        AUnitLayout.addWidget(TipLabel)
        ###########

        def currentChanged(Text):
            Text = str(getattr(crs.AngularUnits, Text, ''))
            TipLabel.setText('弧度  ' + Text)
            
        self.AUnitComboBox.currentTextChanged.connect(currentChanged)      
        self.AUnitComboBox.setCurrentText('Degree')

        AUnitFrame.setLayout(AUnitLayout)
        
        self.MainLayout.addWidget(AUnitFrame)  
        
    def _gcs_primem_(self):     
        #### 3.本初子午线
        PrimemFrame = QGroupBox('本初子午线')
        PrimemFrame.setStyleSheet(stl.QGroupBoxStyle) 
        
        Items = [n for n in dir(crs.Primems) if '_' not in n]
        self.PrimemComboBox = QComboBox()
        self.PrimemComboBox.setStyleSheet(stl.QComboBoxBarStyle)
        self.PrimemComboBox.setMaxVisibleItems(15)
        self.PrimemComboBox.addItems(Items)
        
        PrimemLayout = QVBoxLayout()
        PrimemLayout.addWidget(self.PrimemComboBox) 
        
        ########### 值提示标签
        TipLabel = self._create_tip_label_()
        PrimemLayout.addWidget(TipLabel)
        ###########
        
        def currentChanged(Text):
            Text = str(getattr(crs.Primems, Text, ''))
            TipLabel.setText('经度  ' + Text)
            
        self.PrimemComboBox.currentTextChanged.connect(currentChanged)      
        self.PrimemComboBox.setCurrentText('Greenwich')

        PrimemFrame.setLayout(PrimemLayout)
        
        self.MainLayout.addWidget(PrimemFrame)    
        
    def _gcs_datum_(self):     
        #### 4.基准面
        DatumFrame = QGroupBox('基准面名')
        DatumFrame.setStyleSheet(stl.QGroupBoxStyle) 
        
        self.DatumEdit = QLineEdit()
        self.DatumEdit.setText('GMA Datum')  
        
        DatumLayout = QHBoxLayout()
        DatumLayout.addWidget(self.DatumEdit) 
        DatumFrame.setLayout(DatumLayout)
        
        self.MainLayout.addWidget(DatumFrame)
        
    def _gcs_ellip_(self):
        #### 5.椭球体
        EllipFrame = QGroupBox('参考椭球体')
        EllipFrame.setStyleSheet(stl.QGroupBoxStyle) 
        
        Items = [n for n in dir(crs.Ellips) if '_' not in n]
        self.EllipComboBox = QComboBox()
        self.EllipComboBox.setStyleSheet(stl.QComboBoxBarStyle)
        self.EllipComboBox.setMaxVisibleItems(15)
        self.EllipComboBox.addItems(Items)
        
        
        EllipLayout = QVBoxLayout()
        EllipLayout.addWidget(self.EllipComboBox) 
        
        ########### 值提示标签
        TipLabel = self._create_tip_label_()
        EllipLayout.addWidget(TipLabel)
        ###########
        def currentChanged(Text):
            Text = getattr(crs.Ellips, Text, {})
            TipLabel.setText(f"长半轴  {Text['SemiMajor']}    "
                             f"反扁率  {Text['InvFlattening']}")
            
        self.EllipComboBox.currentTextChanged.connect(currentChanged)      
        self.EllipComboBox.setCurrentText('WGS84')        
        
        
        EllipFrame.setLayout(EllipLayout)
        
        self.MainLayout.addWidget(EllipFrame)         
        

        
        
        
        
        
        
        