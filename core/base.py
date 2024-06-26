# -*- coding: utf-8 -*-

from .iplib import *
from .utils import *

# 线程类，以供调用
class WorkerThread(QThread):
    
    WTFinSig = pyqtSignal(str) # 结束信号
    WTSignal = pyqtSignal(int) # 运行状态
    
    def __init__(self, Fun = None, **kwargs):  
        super().__init__()  

        self.Fun = Fun

        self.kwargs = kwargs
        
    def WTProgress(self, Progress, *args, **kwargs):
        '''重建线程驱动的 GDAL 回调函数'''
        ## 将状态更新到进度
        self.WTSignal.emit(int(Progress * 100 - 1))
        
    def run(self):
        env.CallBack = self.WTProgress

        try:
            self.Fun(**self.kwargs)  # 执行传入的函数
            self.WTProgress(1.01)
            self.WTFinSig.emit('Finish')
            
        except Exception as E:
            self.WTFinSig.emit(str(E))
            
        env.CallBack = None    

# 进度条，以供调用
class ProgressBar:
    def __init__(self):

        self.BarLayout = QVBoxLayout()
        # 添加进度条到底部布局
        self.PBar = QProgressBar()
        self.PBar.setValue(0)  # 设置进度条的值
        self.PBar.setFixedHeight(20)
        
        self.BarLayout.addWidget(self.PBar)

        # 底部布局放在窗口底部
        # self.BarLayout.addStretch(1)
        
    def PBSetValue(self, Value):
        self.PBar.setValue(int(Value))

    def GDALProgress(self, progress, message, callback_data):
        self.PBar.setValue(int(progress * 100))

        # QApplication.processEvents()        

class UtilWindow(QMainWindow):
    
    closed = pyqtSignal() ## 关闭信号
    confirmed = pyqtSignal() ## 确认信号
    completed = pyqtSignal(object) ## 完成信号

    def __init__(self, parent = None):

        super().__init__(parent)
        
        self.TaskExecuting = True
        self.LastOpenDir = '.'
        self.SubWindows = []
        
        self.setStyleSheet(f"{MainWinCFG['StyleSheet']}" + stl.MenubarStyle) 


    def _GetFormats(self, Format, Select = None):
        if Select:
            FormatsList = [v.replace('.', '*.').split()[0] for k, v in Format.items()
                           if k in Select]
        else:
            FormatsList = [v.replace('.', '*.').split()[0] for k, v in Format.items()]
        CFormats = ' '.join(set(FormatsList))
        return CFormats
    
    def _GetRAFormats(self):
        FMTs = gft.RasterSummary()._RAConfig['Extension'].drop_duplicates()
        FMTs = FMTs[FMTs != '']
        
        CF = ['HDF4Image', 'HFA', 'SRP', 'netCDF', 'ENVI', 'WEBP', 'PNG', 'JP2OpenJPEG', 
              'JPEG', 'BMP', 'GTiff']
        
        SInfo0 = f'常用栅格 ({self._GetFormats(FMTs, CF)})'
        # SInfo1 = f'所有栅格 ({self._GetFormats(FMTs)})'
        SInfo1 = '所有文件 (*)'
        SInfo = f'{SInfo0};;{SInfo1}'
        
        return SInfo

    def _GetVEFormats(self):
        FMTs = gft.VectorSummary()._VEConfig['Extension'].drop_duplicates()
        FMTs = FMTs[FMTs != '']
        
        CF = ['ESRI Shapefile', 'GeoJSON', 'GPKG', 'GML', 'XLSX', 'JML', 'KML']
        
        SInfo0 = f'常用矢量 ({self._GetFormats(FMTs, CF)})'
        # SInfo1 = f'所有矢量 ({self._GetFormats(FMTs)})'
        SInfo1 = '所有文件 (*)'
        SInfo = f'{SInfo0};;{SInfo1}'
        
        return SInfo        
 
    def OpenRasterDialog(self):
        # 打开栅格（单个）选择对话框

        SInfo = self._GetRAFormats()
        InFile, _ = QFileDialog.getOpenFileName(self, '选择文件', self.LastOpenDir, SInfo)
        if InFile:
            self.LastOpenDir = os.path.dirname(InFile)
       
        return InFile
    
    def OpenRastersDialog(self):
        # 打开栅格（多个）选择对话框

        SInfo = self._GetRAFormats()
        InFiles, _ = QFileDialog.getOpenFileNames(self, '选择文件', self.LastOpenDir, SInfo)
        if InFiles:
            self.LastOpenDir = os.path.dirname(InFiles[0])

        return InFiles

    def SaveRasterDialog(self):
        # 保存文件选择对话框
        SFormat = gft.RasterSummary()._RAConfig
        SFormat = SFormat.loc[SFormat['Creation'] == 'Yes']
        
        EXT = SFormat.loc[SFormat['Extension'] != '', ['Extension']]
        EXT['Extension'] = [f.split(' ')[0] for f in EXT['Extension']]

        SInfo = ';;'.join([f'{k} 文件 (*{v.iloc[0]})' for k, v in EXT.iterrows()])
    
        OutFile, _ = QFileDialog.getSaveFileName(self, '保存文件', self.LastOpenDir, SInfo,
                                                  'GTiff 文件 (*.tif)' )

        Format = _.split(' 文件')[0]
        
        self.LastOpenDir = os.path.dirname(OutFile)
        
        return OutFile, Format
    
    def OpenVectorDialog(self):
        # 打开矢量（单个）选择对话框
        SInfo = self._GetVEFormats()
        InFile, _ = QFileDialog.getOpenFileName(self, '选择文件', self.LastOpenDir, SInfo)
        if InFile:
            self.LastOpenDir = os.path.dirname(InFile)

        return InFile
    
    def OpenVectorsDialog(self):
        # 打开矢量（多个）选择对话框
        SInfo = self._GetVEFormats()
        InFiles, _ = QFileDialog.getOpenFileNames(self, '选择文件', self.LastOpenDir, SInfo)
        if InFiles:
            self.LastOpenDir = os.path.dirname(InFiles[0])

        return InFiles

    def SaveVectorDialog(self):
        # 保存矢量选择对话框
        SFormat = gft.VectorSummary()._VEConfig
        SFormat = SFormat.loc[SFormat['Creation'] == 'Yes']

        EXT = SFormat.loc[SFormat['Extension'] != '', ['Extension']]
        EXT['Extension'] = [f.split(' ')[0] for f in EXT['Extension']]
        SInfo = ';;'.join([f'{k} 文件 (*{v.iloc[0]})' for k, v in EXT.iterrows()])
    
        OutFile, _ = QFileDialog.getSaveFileName(self, '保存文件', self.LastOpenDir, SInfo,
                                                'ESRI Shapefile 文件 (*.shp)' )
        
        Format = _.split(' 文件')[0]
        
        self.LastOpenDir = os.path.dirname(OutFile)
        
        return OutFile, Format
    
    def OpenFolderDialog(self):
        '''打开文件夹对话框'''
        FolderPath = QFileDialog.getExistingDirectory(self, '选择文件夹')
        if FolderPath:
            self.LastOpenDir = FolderPath
        
        return FolderPath
    
    def OpenRaDialog(self, i, D):
        '''打开文件指令（栅格）'''
        InFile = self.OpenRasterDialog()
        if InFile:

            D['TextEdit'][0].setText(InFile)
        
    def OpenRaFsDialog(self, i, D):
        '''文件列表指令（栅格）'''
        InFiles = self.OpenRastersDialog()
        if InFiles:
            D['ListWT'][0].addItems(InFiles)
        
        self.GetInFiles(i, None)
        
    def OpenVeFsDialog(self, i, D):
        '''文件列表指令（矢量）'''
        InFiles = self.OpenVectorsDialog()
        if InFiles:
            D['ListWT'][0].addItems(InFiles)
        
        self.GetInFiles(i, None)

    def OpenRaFsFromDirDialog(self, i, D):
        '''从文件夹获取栅格列表指令'''
        DirPath = self.OpenFolderDialog()
        
        # EXT = gft.RasterSummary()._RAConfig['Extension']
        # EXT = sum([e.split() for e in EXT if e != '' or '.' not in e], [])
        EXT = ['.hdf', '.img', '.img', '.nc', '.dat', '.webp', '.png', '.jp2', '.j2k', 
               '.jpg', '.jpeg', '.bmp', '.tif', '.tiff']
        InFiles = osf.FindPath(DirPath, EXT)

        if InFiles:
            D['ListWT'][0].addItems(InFiles)
        
        self.GetInFiles(i, None)
        
    def OpenVeFsFromDirDialog(self, i, D):
        '''从文件夹获取矢量列表指令'''
        DirPath = self.OpenFolderDialog()
        
        EXT = ['.shp', '.json', '.geojson', '.gpkg', '.gml', '.svg', '.jml', '.kml']
        InFiles = osf.FindPath(DirPath, EXT)
        
        if InFiles:
            D['ListWT'][0].addItems(InFiles)
        
        self.GetInFiles(i, None)

    def SaveRaDialog(self, i):
        '''保存文件指令'''
        OutFile, Format = self.SaveRasterDialog()
        OutFileLineEdit = self.AddPars.at[i, 'TextEdit'][0]
        OutFileLineEdit.setText(OutFile)
        
        if self.Format.empty == False:
            self.Format.iat[0] = Format

    def OpenVeDialog(self, i, D):
        '''打开文件指令'''
        InFile = self.OpenVectorDialog()
        if InFile:
            ## 写入路径，并打开文件
            D['TextEdit'][0].setText(InFile)  
            
    ########################################################## 针对任意文件    
    def OpenFileDialog(self, SInfo):
        # 打开文件选择对话框
        InFile, _ = QFileDialog.getOpenFileName(self, '选择文件', self.LastOpenDir, SInfo)
        if InFile:
            self.LastOpenDir = os.path.dirname(InFile)

        return InFile
    
    def SaveFileDialog(self, SInfo, Def = None):
        # 保存选择对话框
        OutFile, _ = QFileDialog.getSaveFileName(self, '保存文件', self.LastOpenDir, 
                                                 SInfo, Def)
        
        Format = _.split(' 文件')[0]
        self.LastOpenDir = os.path.dirname(OutFile)
        
        return OutFile, Format
    
    def SaveFDialog(self, i, SInfo, Def = None):
        '''打开文件指令'''
        OutFile, Format = self.SaveFileDialog(SInfo, Def)
        if OutFile:
            OutFileLineEdit = self.AddPars.at[i, 'TextEdit'][0]
            OutFileLineEdit.setText(OutFile)

        if self.Format.empty == False:
            self.Format.iat[0] = Format 
    
    ########################################################## 针对任意文件

    def SaveVeDialog(self, i):
        '''保存文件指令'''
        OutFile, Format = self.SaveVectorDialog()
        if OutFile:
            OutFileLineEdit = self.AddPars.at[i, 'TextEdit'][0]
            OutFileLineEdit.setText(OutFile)

        if self.Format.empty == False:
            self.Format.iat[0] = Format
            
  
    def OpenDir(self, i):
        '''打开文件夹'''
        DirPath = self.OpenFolderDialog()
        if DirPath:
            
            InDirLineEdit = self.AddPars.at[i, 'TextEdit'][0]
            InDirLineEdit.setText(DirPath) 
    
    def Center(self):
        # 获取屏幕坐标系
        QR = self.frameGeometry()
        CP = QDesktopWidget().availableGeometry().center()
        QR.moveCenter(CP)
        self.move(QR.topLeft())
  
    def MSGBox(self, Type = 'Information', MSG = None):    

        MSGBox = QMessageBox(self)
        
        if Type in ['Information', 0]:
            MSGBox.setIcon(QMessageBox.Information)
            MSGBox.setWindowTitle("提示")
        elif Type in ['Warning', 1]:
            MSGBox.setIcon(QMessageBox.Warning)
            MSGBox.setWindowTitle("警告")
        else:
            MSGBox.setIcon(QMessageBox.Critical)
            MSGBox.setWindowTitle("错误") 
            
        Button = MSGBox.addButton(QMessageBox.Ok) 
        Button.setText("确定")
        
        MSGBox.setText(MSG)
        MSGBox.exec_()
        
    def closeEvent(self, event):
 
        TaskExecuting = [SubWin for SubWin in self.SubWindows if SubWin.TaskExecuting]

        if TaskExecuting:
            MSGBox = QMessageBox(self)
            MSGBox.setWindowTitle('提示')
            MSGBox.setIcon(QMessageBox.Information)
            
            MSGBox.setText('确定退出所有任务，并关闭所有子窗口？')
            MSGBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            MSGBox.setDefaultButton(QMessageBox.No)
    
            # 设置按钮文本为中文
            MSGBox.button(QMessageBox.Yes).setText('是')
            MSGBox.button(QMessageBox.No).setText('否')
            Reply = MSGBox.exec_()
        
            if Reply == QMessageBox.Yes:
                for SubWin in TaskExecuting:
                    SubWin.close()
                    SubWin.TaskExecuting = False
                    # SubWin.deleteLater()
            else:
                event.ignore() 
                return

        self.close()
        self.closed.emit()
        # self.deleteLater()
        self.TaskExecuting = False
            
    def OpenProjWin(self, D):
        
        from .crswin import CRSInfoWin
        
        NewCRSWin = CRSInfoWin()
        try:
            Proj = D['TextEdit'][0].text()
            if Proj:
                Spat = crs.SpatRef(Proj)
                NewCRSWin._reset_info_(Spat)
        except:
            pass
        
        NewCRSWin.show()
        
        self.SubWindows.append(NewCRSWin)

        def SetValue():
            if NewCRSWin.Spat is None:
                return
            WKID = NewCRSWin.Spat.WKID
            if WKID[0]:
                Proj = f'{WKID[1]}:{WKID[0]}'
            else:
                Proj = NewCRSWin.Spat.Export()
            D['TextEdit'][0].setText(Proj)
            
            self.SubWindows.remove(NewCRSWin)

        NewCRSWin.confirmed.connect(SetValue)
        

    def DelectAll(self):
        
        self.QWidget = QWidget()  
        self.setCentralWidget(self.QWidget)
        self.MainLayout = QVBoxLayout() ## 主布局
        self.QWidget.setLayout(self.MainLayout) ## 将主布局插入控件中
        return
    
class GroupBox:
    '''创建分组控件'''
    def __init__(self, D):
        
        self.D = D
        self.GroupFrame = QGroupBox(D['WinName'])
        self.GroupFrame.setStyleSheet(stl.QGroupBoxStyle) 

        self.LayoutInfo = {k:[] for k in ['Button', 'TextEdit', 'ComboBox', 
                                          'TableWT', 'ListWT']}
        
    def ProjWidget(self):
        '''坐标系控件'''
        LineEdit = QLineEdit()
        if self.D['SetText'] == True :
            LineEdit.setText(str(self.D['Default']))
            
        ### 添加按钮
        Button = QPushButton("...", )
        Button.setStyleSheet(stl.ButtonStyle)
        Button.setIcon(icon.WORLD)
            
        ProjLayout = QHBoxLayout()    
        ProjLayout.addWidget(LineEdit)    
        ProjLayout.addWidget(Button)
        
        self.GroupFrame.setLayout(ProjLayout)
      
        self.LayoutInfo['Button'].append(Button)
        self.LayoutInfo['TextEdit'].append(LineEdit)

        return LineEdit        
        
      
    def FileWidget(self, ReadOnly = True):
        '''文件型控件'''

        ### 添加文本框
        LineEdit = QLineEdit()
        if ReadOnly:
            LineEdit.setReadOnly(True)
            LineEdit.setStyleSheet(stl.ReadOnlyEditStlye)
        
        ### 添加按钮
        Button = QPushButton("...", )
        Button.setStyleSheet(stl.ButtonStyle)
        Button.setIcon(icon.FOLDER)
        
        FileLayout = QHBoxLayout()  # 输入输出布局/水平
        FileLayout.addWidget(LineEdit)
        FileLayout.addWidget(Button) 
        
        self.GroupFrame.setLayout(FileLayout)

        self.LayoutInfo['Button'].append(Button)
        self.LayoutInfo['TextEdit'].append(LineEdit)

        return LineEdit, Button
    
    def FilesWidget(self):
        '''多文件型控件'''

        ### 添加文本框
        ListWidget = QListWidget()
        # ListWidget.setMaximumHeight(150)
        
        ### 添加按钮
        Button = QPushButton(".")
        Button.setStyleSheet(stl.ButtonStyle)
        Button.setIcon(icon.FOLDER)
        
        Menu = QMenu()
        SelectFileAction = QAction('选择文件', Button)
        SelectFolderAction = QAction('选择文件夹', Button)

        Menu.addAction(SelectFileAction) 
        Menu.addAction(SelectFolderAction)
        
        Button.setMenu(Menu)
        
        FileLayout = QHBoxLayout()  # 输入输出布局/水平
        FileLayout.addWidget(ListWidget)
        FileLayout.addWidget(Button)  
    
        self.GroupFrame.setLayout(FileLayout)
        
        self.LayoutInfo['ListWT'].append(ListWidget)
        self.LayoutInfo['Button'].append(Button)

        return ListWidget, Button
        
    def SelectWidget(self):
        '''参数选择型控件'''
        
        if self.D['ToPY'] == 'bool':
            Methods = ['True', 'False']
            
        else:
            Methods = self.D['Values'].split()
  
        Deft = self.D['Value']
        if pd.isna(Deft):
            Deft = Methods[0]
            self.D['Value'] = Deft
        else:
            Deft = str(Deft)
        Methods = [Deft] + list(set(Methods) - set([Deft]))

        ComboBox = QComboBox()
        ComboBox.setStyleSheet(stl.QComboBoxBarStyle)
        ComboBox.setMaxVisibleItems(15)
        ComboBox.addItems(Methods)
        ComboBox.setCurrentText(Deft)

        ParSub = QVBoxLayout()
        ParSub.addWidget(ComboBox)   
  
        self.GroupFrame.setLayout(ParSub)            
        self.LayoutInfo['ComboBox'].append(ComboBox)

        return ComboBox
        
    def TextWidget(self):
        '''文本/数字参数型控件'''
        
        LineEdit = QLineEdit()
        if self.D['ToPY'] == 'float':
            LineEdit.setValidator(QDoubleValidator())
        elif self.D['ToPY'] == 'int':
            LineEdit.setValidator(QIntValidator())
            
        if self.D['SetText'] == True :
            LineEdit.setText(str(self.D['Default']))
            
        if self.D['ToPY'] == '':
            LineEdit.setReadOnly(True)
            LineEdit.setStyleSheet("background-color: transparent;"
                                   "border: transparent;")  
            LineEdit.setFocusPolicy(0)
 
        ParSub = QVBoxLayout()    
        ParSub.addWidget(LineEdit)    
        self.GroupFrame.setLayout(ParSub)
      
        self.LayoutInfo['TextEdit'].append(LineEdit)

        return LineEdit
        
    def MultiTextWidget(self):
        '''多文本窗口'''
        Labels = str(self.D['Values']).split()
        Defaults = self.D['Default']

        Layout = QHBoxLayout()
        
        if self.D['Type'] == 'float':
            Validator = QDoubleValidator()
        else:
            Validator = None

        TX = []
      
        for i, lb in enumerate(Labels):
            
            Label = QLabel(lb + ':')
            TextEdit = QLineEdit()
            TextEdit.setValidator(QDoubleValidator())
            try:
                text = Defaults[i]
                TextEdit.setText(str(text))
            except:
                pass

            Layout.addWidget(Label)
            Layout.addWidget(TextEdit)

            TX.append(TextEdit)
            self.LayoutInfo['TextEdit'].append(TextEdit)
            
        self.GroupFrame.setLayout(Layout)

        return TX
        
    def Table(self, DataFrame = None):
        '''添加表格控件'''

        if self.LayoutInfo['TableWT'] == []:
            Layout = QVBoxLayout()
            QTable = QTableWidget()
            Layout.addWidget(QTable) 
            self.GroupFrame.setLayout(Layout)
            self.LayoutInfo['TableWT'].append(QTable)
        else:
            QTable = self.LayoutInfo['TableWT'][0]

        if DataFrame is None:
            return
            
        SHP = DataFrame.shape 
            
        # 设置表格的行数和列数  
        QTable.setRowCount(SHP[0]) 
        QTable.setColumnCount(SHP[1])
        
        QTable.setHorizontalHeaderLabels(DataFrame.columns)
        
        font = QTable.horizontalHeader().font()
        font.setBold(True)
        QTable.horizontalHeader().setFont(font)

        if 'RowHeight' in self.D:
            RowHeight = self.D['RowHeight']
        else:
            RowHeight = 25
            
        if 'ColumnWidth' in self.D:
            ColumnWidth = self.D['ColumnWidth']
        else:
            ColumnWidth = 75
        
        for r in range(SHP[0]):
            QTable.setRowHeight(r, RowHeight)
            
        for c in range(SHP[1]):
            QTable.setColumnWidth(c, ColumnWidth)       

        # 添加一些数据到表格中
        for i, j in np.ndindex(SHP):
            QTable.setItem(i, j, QTableWidgetItem(str(DataFrame.iat[i, j]))) 

        return QTable
    
    
        
class LayoutWidget:
    
    def __init__(self, BoxLayout = 'H', Spacing = 20):
        '''创建布局控件''' 
        if BoxLayout in [0, 'V']:
            self.MainLayout = QVBoxLayout()  
        else:
            self.MainLayout = QHBoxLayout() 
        
        self.InTSpace = 0
        self.Spacing = Spacing
        
    def Button(self, Name, Icon, FixSize = True):
        if self.InTSpace != 0:
            self.Layout.setSpacing(self.Spacing)
            self.InTSpace += self.Spacing

        QButton = QPushButton(Name)
        QButton.setStyleSheet(stl.ButtonStyle)
        if FixSize:
            QButton.setFixedSize(*SubWinCFG["Button"]["Fun"]["Size"])
        QButton.setIcon(Icon)   
        
        self.MainLayout.addWidget(QButton) 

        return QButton
        
    def TextEdit(self):
        
        # 创建文本框
        TextEdit = QTextEdit()
        self.MainLayout.addWidget(TextEdit) 
        
        return TextEdit
    
    def LineEdit(self, ReadOnly = False):
        
        # 创建文本框
        LineEdit = QLineEdit()
        self.MainLayout.addWidget(LineEdit) 
        
        if ReadOnly:    
            LineEdit.setReadOnly(True)
            LineEdit.setStyleSheet(stl.ReadOnlyEditStlye)
        
        return LineEdit
    
    def Label(self, Text = ''):
        
        # 创建标签
        Label = QLabel()
        Label.setText(Text)
        self.MainLayout.addWidget(Label) 

        return Label
    
    def RadioButton(self, BoxLayout = 'H', Name = '', Radias = []):
        # 创建单选按钮组
        
        GroupFrame = QGroupBox(Name)
        # GroupFrame.setStyleSheet(stl.QGroupBoxStyle) 
        
        if BoxLayout in [0, 'V']:
            RadiasLayout = QVBoxLayout()  
        else:
            RadiasLayout = QHBoxLayout() 
   
        GroupFrame.setLayout(RadiasLayout)
        RadioGroup = QButtonGroup()  
        RadiasLayout.addStretch(1)
        for i, n in enumerate(Radias):
            # 创建单选按钮并添加到组中  
            RadioBu = QRadioButton(n)  
            RadioGroup.addButton(RadioBu, i)
            RadiasLayout.addWidget(RadioBu)
            RadiasLayout.addStretch(1)
            if i == 0:
                RadioBu.setChecked(True)    
        
        self.MainLayout.addWidget(GroupFrame)
        
        return RadioGroup

class SearchWidget:
    
    def __init__(self, Name = '', Items = []): 
         
        self.GroupFrame = QGroupBox(Name)
        
        self.SearchLayout = QVBoxLayout()
        
        ## 0.搜索功能
        Search0 = QHBoxLayout() 
        
        ### 0.1 文本框
        self.searchLineEdit = QLineEdit()  
        self.searchLineEdit.textChanged.connect(self.on_search)  
        self.searchLineEdit.setPlaceholderText("搜索...")
        Search0.addWidget(self.searchLineEdit)
        
        ### 0.2 清空按钮
        self.clearButton = QPushButton()  
        self.clearButton.setIcon(icon.CLEAR)
        self.clearButton.setStyleSheet(stl.ButtonStyle)
        self.clearButton.clicked.connect(self.on_clear_search)  
        self.clearButton.setToolTip('清空搜索内容') 
        Search0.addWidget(self.clearButton)
        
        ## 1.内容项目
        ItemLayer = QVBoxLayout() 
        self.listWidget = QListWidget() 
        self.listWidget.setStyleSheet(stl.QListWidgetStyle)
  
        ItemLayer.addWidget(self.listWidget)
        
        self.SearchLayout.addLayout(Search0)
        self.SearchLayout.addLayout(ItemLayer)
        
        self.GroupFrame.setLayout(self.SearchLayout)
        
        for n in Items:
            self.listWidget.addItem(n.strip())  
    
    def on_search(self, text):  
        # 清除当前的选择和过滤  
        self.listWidget.clearSelection()  
        for i in range(self.listWidget.count()):  
            self.listWidget.item(i).setHidden(not text.lower() in self.listWidget.item(i).text().lower())  
  
    def on_clear_search(self):  
        # 清除搜索框并显示所有项  
        self.searchLineEdit.clear()  
        for i in range(self.listWidget.count()):  
            self.listWidget.item(i).setHidden(False)      
    
    
    
    
        
