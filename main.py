# -*- coding: utf-8 -*-

import sys, os
sys.path.append(os.path.dirname(__file__))

from core.splash import SplashScreen

if __name__ == '__main__':
    
    splash = SplashScreen()

    splash.setMessage('正在加载 GmaGIS……')
    
    splash.show()
    from core.mainwin import main
    splash.close()
    
    del splash

    args = sys.argv
    if len(args) == 1:
        main()
    else:
        ## 为打开文件做准备
        pass
    
    
    
    
    
    
    
    
    

