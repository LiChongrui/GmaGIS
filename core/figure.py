# -*- coding: utf-8 -*-

from .iplib import (Qt, QSizePolicy, plot, Figure, FigureCanvas, plt, np)

PAR = {'font.sans-serif': 'Times New Roman',
       'axes.unicode_minus': False,
       }

class MatplotlibWidget(FigureCanvas):  
    
    def __init__(self, parent = None, Subplots = [1, 1], 
                 **kwargs): 
        
        plt.rcParams.update(PAR)
        
        self.fig = Figure(**kwargs)  
        self.fig.tight_layout()
        self.fig.subplots_adjust(left = 0, bottom = 0, right = 1, top = 1)
        # self.fig.patch.set_color('red')
        super().__init__(self.fig)
        
        self.setParent(parent)

        self.setSizePolicy(QSizePolicy.Expanding,
                           QSizePolicy.Expanding)
        
        self.updateGeometry()
        
        self.AllAxes = self.fig.subplots(*Subplots)
        if isinstance(self.AllAxes, np.ndarray) is False:
            self.AllAxes = np.array(self.AllAxes)
        self.AllAxes = self.AllAxes.flatten()    
            
        self._init_mapframes_()

        # 鼠标滚轮事件
        self.mpl_connect('scroll_event', self.on_scroll)
        self.mpl_connect('button_press_event', self.on_press)
        self.mpl_connect('button_release_event', self.on_release)
        self.mpl_connect('motion_notify_event', self.on_motion)
        self.mpl_connect('figure_enter_event', self.on_enter_figure)
        self.mpl_connect('figure_leave_event', self.on_leave_figure)
        self.mpl_connect('button_press_event', self.on_click)
        
        self.pressed = False
        self.move_flag = False
        self.xpress = None
        self.ypress = None
        
        plt.ion()
        self._get_base_XY_()
        self.MapLayers = {}
        
    def _get_base_XY_(self):
        self.BWidth = self.width()
        self.BHeight = self.height()
        
    def _init_mapframes_(self):
        self.MapFrames = []
        for Axes in self.AllAxes: 
            MapF = plot.MapFrame(Axes = Axes)
            self.MapFrames.append(MapF)
        
        self._set_activate_mapframe()
        self._resize_axes_()
        
    def _set_activate_mapframe(self, i = 0):
        self.MapF = self.MapFrames[i]
        self.Axes = self.MapF.Axes
        
    def AddLayer(self, *args, **kwargs):
        '''添加矢量图层'''
        StartID = len(self.Axes.collections)
        
        GmaPlotItem = self.MapF.AddLayer(*args, **kwargs)
        self._update_plot_new_(GmaPlotItem)
        
        EndID = len(self.Axes.collections)
        self.MapLayers[args[0].Name] = ['Vector', 
                                        self.Axes, 
                                        [StartID, EndID],
                                        args[0]]

        return GmaPlotItem
        
    def AddDataSetDiscrete(self, *args, **kwargs):
        '''添加重分类栅格数据集'''

        GmaPlotItem = self.MapF.AddDataSetDiscrete(*args, **kwargs)  
        self._update_plot_new_(GmaPlotItem)
        self.MapLayers[args[0].Name] = ['Raster', 
                                        self.Axes, 
                                        GmaPlotItem.IM, 
                                        args[0]]

        return GmaPlotItem
    
    def handleItemChanged(self, item, column):
        # 检查是否是复选框状态改变
        Name = item.text(column)

        if item.checkState(column) == Qt.Checked:
            self.show_gl(Name)
        else:
            self.hide_gl(Name)
    
    def show_gl(self, Name):
        '''显示'''
        Type, Axes, IDorIM, _ = self.MapLayers.get(Name, [None] * 4)
        
        if Type == 'Vector':
            for i in range(*IDorIM):
                Axes.collections[i].set_visible(True)
        elif Type == 'Raster':
            IDorIM.set_visible(True)

        self.draw_idle()

    def hide_gl(self, Name):
        '''隐藏'''
        Type, Axes, IDorIM, _ = self.MapLayers.get(Name, [None] * 4)
        
        if Type == 'Vector':
            for i in range(*IDorIM):
                Axes.collections[i].set_visible(False)
        elif Type == 'Raster':
            IDorIM.set_visible(False)

        self.draw_idle()

    def _update_plot_new_(self, GmaPlotItem):
        
        if len(self.MapF.PlotX) == 1:
            self.Axes.autoscale()
            self._resize_axes_()
        
        background = self.fig.canvas.copy_from_bbox(self.fig.bbox)
        self.fig.canvas.restore_region(background)
        for i, collection in GmaPlotItem.GeomOptInfo['Artists'].items():
            self.Axes.add_collection(collection)
        self.fig.canvas.blit(self.fig.bbox)

        self.draw_idle()
        
    def _resize_axes_(self):
        # 保持图形内容的相对大小不变
        xlim = self.Axes.get_xlim()
        ylim = self.Axes.get_ylim()

        width = self.width()
        height = self.height()
        
        if width > height: # 缩放 Y
            new_xlim = xlim
            ylen = (xlim[1] - xlim[0]) * (height / width)
            ycent = (ylim[1] + ylim[0]) * 0.5
            new_ylim = [ycent - ylen * 0.5, ycent + ylen * 0.5]
        
        else: # 缩放 X
            xlen = (ylim[1] - ylim[0]) * (width / height)
            xcent = (xlim[1] + xlim[0]) * 0.5
            new_xlim = [xcent - xlen * 0.5, xcent + xlen * 0.5]
            new_ylim = ylim
            
        self.Axes.set_xlim(new_xlim)
        self.Axes.set_ylim(new_ylim)   

        self.draw_idle() 

    def resizeEvent(self, event):
        self._resize_axes_()
        super(MatplotlibWidget, self).resizeEvent(event)

    def on_scroll(self, event):
        try:
            scale_factor = 1.5 if event.button == 'up' else 0.67
            curr_xlim = self.Axes.get_xlim()
            curr_ylim = self.Axes.get_ylim()
            new_width = (curr_xlim[1] - curr_xlim[0]) * scale_factor
            new_height = (curr_ylim[1] - curr_ylim[0]) * scale_factor
            relx = (curr_xlim[1] - event.xdata) / (curr_xlim[1] - curr_xlim[0])
            rely = (curr_ylim[1] - event.ydata) / (curr_ylim[1] - curr_ylim[0])
            self.Axes.set_xlim([event.xdata - new_width * (1 - relx),
                                event.xdata + new_width * relx])
            self.Axes.set_ylim([event.ydata - new_height * (1 - rely), 
                                event.ydata + new_height * rely])
            self.draw_idle() 
        except:
            pass
        
    def on_press(self, event):
        if event.button == 1:  # Left mouse button
            self.pressed = True
            self.xpress = event.xdata
            self.ypress = event.ydata

    def on_release(self, event):
        self.pressed = False
        self.xpress = None
        self.ypress = None

    def on_motion(self, event):
        if self.pressed and event.xdata is not None and event.ydata is not None:
            dx = event.xdata - self.xpress
            dy = event.ydata - self.ypress
            xlim = self.Axes.get_xlim()
            ylim = self.Axes.get_ylim()
            self.Axes.set_xlim(xlim[0] - dx, 
                               xlim[1] - dx)
            self.Axes.set_ylim(ylim[0] - dy, 
                               ylim[1] - dy)
            self.draw_idle() 
            
    def on_enter_figure(self, event):
        self.setCursor(Qt.OpenHandCursor)

    def on_leave_figure(self, event):
        self.unsetCursor()
        
    def on_click(self, event):
        for i, Axes in enumerate(self.AllAxes):
            if event.inaxes == Axes:
                self._set_activate_mapframe(i)
                return