# -*- coding: utf-8 -*-

from .iplib import dt, inspect, pd, QIcon

from style import default as stl
from style import icon

## 配置信息
def ReadJson(CFGFile):
    try:
        CFG = eval(open(CFGFile, encoding = 'utf-8').read())
    except:
        CFG = {}
    return CFG

MainWinCFG = ReadJson('./config/main.json') ## 主配置
SubWinCFG = ReadJson('./config/subwin.json') ## 子窗口配置
ToolCFG = ReadJson('./config/tools.json') ## 工具按钮配置

def GetIcon(Icon):
    '''从图标名获取 图标'''
    if isinstance(Icon, str):
        return getattr(icon, Icon.upper(), QIcon())
    elif isinstance(Icon, QIcon):
        return Icon
    else:
        return QIcon()

def GetCurrentTime():
    '''获取当前时间'''
    CurrentTime = dt.datetime.now()
    CurrentTimeString = CurrentTime.strftime("%Y-%m-%d %H:%M:%S")   
    
    return CurrentTimeString

def GetFunPar(Fun):
    '''获取函数参数及默认值'''
    
    Pars = pd.DataFrame(columns = ['Name', 'Default', 'Must'], dtype = 'object')
    try:
        funparams = inspect.signature(Fun).parameters
    except:
        return Pars
    
    for i, (param_name, param) in enumerate(funparams.items()):
        
        if param_name in ['kwargs', 'args']:
            continue
        
        Pars.loc[i, 'Name'] = param_name

        if param.default == inspect.Parameter.empty:
            Pars.loc[i, 'Must'] = True
        else:
            Pars.loc[i, 'Default'] = param.default 
            Pars.loc[i, 'Must'] = False
    return Pars

def GetParInfo():
    '''获取参数信息'''
    ParData = pd.read_csv('./config/parinfo.csv')
    return ParData

    
    