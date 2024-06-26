from PyQt5.QtGui import QIcon
import glob, os

for f in glob.glob('./icon/*.svg'):
    Name = os.path.basename(f)[:-4].upper()
    try:
        exec(f"{Name} = QIcon(r'{f}')")
    except:
        continue

GMALOGO = eval('LOGO')




