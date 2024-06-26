# -*- coding: utf-8 -*-

from .iplib import io

# 文本框变化动作
class TextChange:
    
    def ReadRaster(self, i, Text):
        '''读取栅格数据的监控函数'''
        if Text == "":
            return
        # try:
        #     DataSet = io.ReadRaster(Text)
        # except:
        #     self.MSGBox(2, f'无法打开 {Text} 文件！')
        #     return

        self.AddPars.at[i, 'Value'] = Text
        
        return Text
    
    def ReadVector(self, i, Text):
        '''读取矢量数据的监控函数'''
        if Text == "":
            return
        # try:
        #     Layer = io.ReadVector(Text)
        # except:
        #     self.MSGBox(2, f'无法打开 {Text} 文件！')
        #     return

        self.AddPars.at[i, 'Value'] = Text
        
        return Text   

    def GetInFiles(self, i, Item):
        
        D = self.AddPars.loc[i]
        ListWIGs = D['ListWT'][0]

        self.AddPars.at[i, 'Value'] = [ListWIGs.item(i).text() for i in range(ListWIGs.count())] 

    def SaveFileOrDir(self, i, Text):
        '''写入文件或文件夹'''

        self.AddPars.at[i, 'Value'] = Text

    def _ToPY(self, Value):
        '''转为 PY 变量'''
        try:
            Value = eval(Value)
        except:
            Value = str(Value)
                    
        return Value

    def PYText(self, i, Text):
        '''可以直接转换问 Pyhon 变量的文本框'''

        D = self.AddPars.loc[i]

        ValueWIGs = D['TextEdit']
        
        Values = []
        for WIG in ValueWIGs:
            Value = WIG.text()
            Value = None if Value == '' else self._ToPY(Value)
            Values.append(Value)

        Values = Values[0] if len(Values) == 1 else Values

        self.AddPars.at[i, 'Value'] = Values

    def PYComb(self, i, Text):
        '''可以直接转换问 Pyhon 变量的文本框'''
        
        D = self.AddPars.loc[i]
        ValueWIGs = D['ComboBox']
        Values = []
        for WIG in ValueWIGs:
            Value = WIG.currentText()
            Value = None if Value == '' else self._ToPY(Value)
            Values.append(Value)
                     
        Values = Values[0] if len(Values) == 1 else Values

        self.AddPars.at[i, 'Value'] = Values
