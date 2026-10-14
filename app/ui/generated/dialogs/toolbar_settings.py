# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'toolbar_settings.ui'
##
## Created by: Qt User Interface Compiler version 6.11.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PyQt6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PyQt6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PyQt6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QSizePolicy, QSpacerItem, QToolButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget)

import app.resources.files_res  # noqa: F401  # Registers Qt resources on import.

class Ui_ToolbarSettingsDlg(object):
    def setupUi(self, ToolbarSettingsDlg):
        if not ToolbarSettingsDlg.objectName():
            ToolbarSettingsDlg.setObjectName(u"ToolbarSettingsDlg")
        ToolbarSettingsDlg.resize(620, 600)
        self.verticalLayout = QVBoxLayout(ToolbarSettingsDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.hintLabel = QLabel(ToolbarSettingsDlg)
        self.hintLabel.setObjectName(u"hintLabel")
        self.hintLabel.setWordWrap(True)

        self.verticalLayout.addWidget(self.hintLabel)

        self.searchEdit = QLineEdit(ToolbarSettingsDlg)
        self.searchEdit.setObjectName(u"searchEdit")
        self.searchEdit.setClearButtonEnabled(False)

        self.verticalLayout.addWidget(self.searchEdit)

        self.commandTree = QTreeWidget(ToolbarSettingsDlg)
        self.commandTree.setObjectName(u"commandTree")
        self.commandTree.setHeaderHidden(True)
        self.commandTree.setUniformRowHeights(True)

        self.verticalLayout.addWidget(self.commandTree)

        self.orderLayout = QHBoxLayout()
        self.orderLayout.setObjectName(u"orderLayout")
        self.upButton = QToolButton(ToolbarSettingsDlg)
        self.upButton.setObjectName(u"upButton")
        icon = QIcon()
        icon.addFile(u":/resource/icons/up.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.upButton.setIcon(icon)

        self.orderLayout.addWidget(self.upButton)

        self.downButton = QToolButton(ToolbarSettingsDlg)
        self.downButton.setObjectName(u"downButton")
        icon1 = QIcon()
        icon1.addFile(u":/resource/icons/down.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.downButton.setIcon(icon1)

        self.orderLayout.addWidget(self.downButton)

        self.orderSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.orderLayout.addItem(self.orderSpacer)


        self.verticalLayout.addLayout(self.orderLayout)

        self.buttonBox = QDialogButtonBox(ToolbarSettingsDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.RestoreDefaults)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(ToolbarSettingsDlg)

        QMetaObject.connectSlotsByName(ToolbarSettingsDlg)
    # setupUi

    def retranslateUi(self, ToolbarSettingsDlg):
        ToolbarSettingsDlg.setWindowTitle(QCoreApplication.translate("ToolbarSettingsDlg", u"Customize Toolbars", None))
        self.hintLabel.setText(QCoreApplication.translate("ToolbarSettingsDlg", u"Choose the buttons to show on each toolbar. Commands remain available in the menus.", None))
        self.searchEdit.setPlaceholderText(QCoreApplication.translate("ToolbarSettingsDlg", u"Find a command", None))
        ___qtreewidgetitem = self.commandTree.headerItem()
        ___qtreewidgetitem.setText(0, QCoreApplication.translate("ToolbarSettingsDlg", u"Command", None))
#if QT_CONFIG(tooltip)
        self.upButton.setToolTip(QCoreApplication.translate("ToolbarSettingsDlg", u"Move up", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.downButton.setToolTip(QCoreApplication.translate("ToolbarSettingsDlg", u"Move down", None))
#endif // QT_CONFIG(tooltip)
    # retranslateUi
