
TabStyle = """
            QTabBar::tab {
                background-color: transparent;
                padding: 6px 12px 6px 12px;
                margin-bottom: 1px; 
            }
             QTabBar::tab:selected {
                background-color: #FFFFFF;
                border: 1px solid #C0C0C0;
                color: #191970;
                border-bottom: 1px solid #FFFFFF;
            }
             QTabBar::tab:!selected {
                background-color: #FFFFFF;
                border: 0px;
                border-bottom: 1px solid #C0C0C0;
            }
            QTabBar::tab:hover:!selected {
                 background-color: #E0EEF9; 
                 
                 }
        """

DockStyle = """
            QDockWidget {
                border: 1px solid #A9A9A9;
                border-radius: 3px;
                
            }
            QDockWidget::title {
                background: #ffffff;
                border: 0px solid #A9A9A9;
                border-radius: 0;
                border-bottom: 0px;
                padding: 4px 0px 4px 0px;
            }
            """

ButtonStyle = """
                QPushButton {
                    background-color: #FFFFFF;
                    border-style: outset;
                    border-width: 1px;
                    border-radius: 3px;
                    border-color: gray;
                    color: black;
                    padding: 1px;
                    box-shadow: none;
                }
                QPushButton:hover {
                    background-color: #E0EEF9; 
                    border-color: #0078D4;
                    }
                QToolButton {
                    margin: 0px;  /* 设置外边距 */
                    border-style: outset;
                    border-width: 0px;
                    padding: 0px;  /* 设置内边距 */
                    border-radius: 3px;
                }
                QToolButton:hover,
                QToolButton:pressed {
                    background-color: #E0EEF9; 
                    border-color: #0078D4;
                }
                QToolButton::menu-indicator {
                    subcontrol-position: bottom center;
                    bottom: 5px; 
                    transform: translateX(-50%);
                    }                
            """
            
ProgressBarStyle = """
                    QProgressBar {
                        background-color: white;
                    }
                """
QListWidgetStyle = """     
                    QListWidget QScrollBar::sub-line:vertical,
                    QListWidget QScrollBar::add-line:vertical,
                    QListWidget QScrollBar::sub-line:horizontal,
                    QListWidget QScrollBar::add-line:horizontal {
                        border: none;
                        height: 0; 
                        background: none;
                    }
                    
                    QListWidget QScrollBar::handle:vertical,
                    QListWidget QScrollBar::handle:horizontal {
                        background: #fbffff;
                        border: 1px solid #A9A9A9;
                        border-radius: 4px; 
                        min-height: 40px;
                    }

                    """

QComboBoxBarStyle = """ 
                    QComboBox {combobox-popup: 0;}

                    QComboBox QAbstractItemView {
                            border: 1px solid #C0C0C0; 
                            selection-background-color: #1E90FF;
                            height: 0px;
                     }     
                    QComboBox QScrollBar::sub-line:vertical,
                    QComboBox QScrollBar::add-line:vertical {
                        border: none; 
                        height: 0;
                        background: none;
                    }
                    
                    QComboBox QScrollBar::handle:vertical {
                        background: #fbffff; 
                        border: 1px solid #A9A9A9;
                        border-radius: 4px;
                    }
                    QComboBox QScrollBar {
                        width: 15px;
                    }
                    QComboBox::on {
                        background-color: hsl(100%, 100%, 100%);
                    }

                    """

MenubarStyle = """
               QMenuBar::item:selected {
                   background-color: #eff0fc;
                   }
               QMenu::item:selected {
                   background-color: #1E90FF;
                   color: #F5F5DC;
                   }
               QMenu {
                   border: 1px solid #DCDCDC;
                   }
               """
QGroupBoxStyle = """QGroupBox { border: none; padding-top: 15px;}"""

ReadOnlyEditStlye = """background-color: #fbffff;"""

