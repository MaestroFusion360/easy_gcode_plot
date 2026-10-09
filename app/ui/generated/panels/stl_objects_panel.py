# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'stl_objects_panel.ui'
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
from PyQt6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QSizePolicy, QSpacerItem,
    QStackedWidget, QToolButton, QVBoxLayout, QWidget)

class Ui_StlObjectsPanelForm(object):
    def setupUi(self, StlObjectsPanelForm):
        if not StlObjectsPanelForm.objectName():
            StlObjectsPanelForm.setObjectName(u"StlObjectsPanelForm")
        self.rootLayout = QVBoxLayout(StlObjectsPanelForm)
        self.rootLayout.setSpacing(5)
        self.rootLayout.setObjectName(u"rootLayout")
        self.rootLayout.setContentsMargins(6, 6, 6, 6)
        self.objectList = QListWidget(StlObjectsPanelForm)
        self.objectList.setObjectName(u"objectList")
        self.objectList.setMaximumSize(QSize(16777215, 100))

        self.rootLayout.addWidget(self.objectList)

        self.actionsLayout = QHBoxLayout()
        self.actionsLayout.setSpacing(1)
        self.actionsLayout.setObjectName(u"actionsLayout")
        self.undoButton = QToolButton(StlObjectsPanelForm)
        self.undoButton.setObjectName(u"undoButton")

        self.actionsLayout.addWidget(self.undoButton)

        self.redoButton = QToolButton(StlObjectsPanelForm)
        self.redoButton.setObjectName(u"redoButton")

        self.actionsLayout.addWidget(self.redoButton)

        self.statisticsButton = QToolButton(StlObjectsPanelForm)
        self.statisticsButton.setObjectName(u"statisticsButton")

        self.actionsLayout.addWidget(self.statisticsButton)

        self.deleteButton = QToolButton(StlObjectsPanelForm)
        self.deleteButton.setObjectName(u"deleteButton")

        self.actionsLayout.addWidget(self.deleteButton)


        self.rootLayout.addLayout(self.actionsLayout)

        self.operationCombo = QComboBox(StlObjectsPanelForm)
        self.operationCombo.setObjectName(u"operationCombo")

        self.rootLayout.addWidget(self.operationCombo)

        self.operationStack = QStackedWidget(StlObjectsPanelForm)
        self.operationStack.setObjectName(u"operationStack")
        self.operationPage0 = QWidget()
        self.operationPage0.setObjectName(u"operationPage0")
        self.operationStack.addWidget(self.operationPage0)
        self.operationPage1 = QWidget()
        self.operationPage1.setObjectName(u"operationPage1")
        self.operationStack.addWidget(self.operationPage1)
        self.operationPage2 = QWidget()
        self.operationPage2.setObjectName(u"operationPage2")
        self.operationStack.addWidget(self.operationPage2)
        self.operationPage3 = QWidget()
        self.operationPage3.setObjectName(u"operationPage3")
        self.operationStack.addWidget(self.operationPage3)
        self.operationPage4 = QWidget()
        self.operationPage4.setObjectName(u"operationPage4")
        self.operationStack.addWidget(self.operationPage4)
        self.operationPage5 = QWidget()
        self.operationPage5.setObjectName(u"operationPage5")
        self.operationStack.addWidget(self.operationPage5)

        self.rootLayout.addWidget(self.operationStack)

        self.bottomSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.rootLayout.addItem(self.bottomSpacer)

        self.closeButton = QPushButton(StlObjectsPanelForm)
        self.closeButton.setObjectName(u"closeButton")
        self.closeButton.setMinimumSize(QSize(90, 0))

        self.rootLayout.addWidget(self.closeButton, 0, Qt.AlignmentFlag.AlignRight)


        self.retranslateUi(StlObjectsPanelForm)

        QMetaObject.connectSlotsByName(StlObjectsPanelForm)
    # setupUi

    def retranslateUi(self, StlObjectsPanelForm):
        StlObjectsPanelForm.setWindowTitle(QCoreApplication.translate("StlObjectsPanelForm", u"STL Objects", None))
        self.undoButton.setText(QCoreApplication.translate("StlObjectsPanelForm", u"Undo", None))
        self.redoButton.setText(QCoreApplication.translate("StlObjectsPanelForm", u"Redo", None))
        self.statisticsButton.setText(QCoreApplication.translate("StlObjectsPanelForm", u"Statistics", None))
        self.deleteButton.setText(QCoreApplication.translate("StlObjectsPanelForm", u"Delete", None))
        self.closeButton.setText(QCoreApplication.translate("StlObjectsPanelForm", u"Close", None))
    # retranslateUi
