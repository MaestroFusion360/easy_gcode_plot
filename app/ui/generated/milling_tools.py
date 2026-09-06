# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'milling_tools.ui'
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
from PyQt6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QDialog,
    QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QSizePolicy, QSpacerItem, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

class Ui_MillingToolsDlg(object):
    def setupUi(self, MillingToolsDlg):
        if not MillingToolsDlg.objectName():
            MillingToolsDlg.setObjectName(u"MillingToolsDlg")
        MillingToolsDlg.resize(860, 540)
        MillingToolsDlg.setMinimumSize(QSize(700, 440))
        self.verticalLayout = QVBoxLayout(MillingToolsDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.titleLabel = QLabel(MillingToolsDlg)
        self.titleLabel.setObjectName(u"titleLabel")

        self.verticalLayout.addWidget(self.titleLabel)

        self.helpLabel = QLabel(MillingToolsDlg)
        self.helpLabel.setObjectName(u"helpLabel")
        self.helpLabel.setWordWrap(True)

        self.verticalLayout.addWidget(self.helpLabel)

        self.toolTable = QTableWidget(MillingToolsDlg)
        if (self.toolTable.columnCount() < 6):
            self.toolTable.setColumnCount(6)
        __qtablewidgetitem = QTableWidgetItem()
        self.toolTable.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.toolTable.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.toolTable.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.toolTable.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.toolTable.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.toolTable.setHorizontalHeaderItem(5, __qtablewidgetitem5)
        self.toolTable.setObjectName(u"toolTable")
        self.toolTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.toolTable.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.toolTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.toolTable.setColumnCount(6)

        self.verticalLayout.addWidget(self.toolTable)

        self.toolButtonsLayout = QHBoxLayout()
        self.toolButtonsLayout.setObjectName(u"toolButtonsLayout")
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.toolButtonsLayout.addItem(self.horizontalSpacer)

        self.addButton = QPushButton(MillingToolsDlg)
        self.addButton.setObjectName(u"addButton")

        self.toolButtonsLayout.addWidget(self.addButton)

        self.editButton = QPushButton(MillingToolsDlg)
        self.editButton.setObjectName(u"editButton")

        self.toolButtonsLayout.addWidget(self.editButton)

        self.removeButton = QPushButton(MillingToolsDlg)
        self.removeButton.setObjectName(u"removeButton")

        self.toolButtonsLayout.addWidget(self.removeButton)


        self.verticalLayout.addLayout(self.toolButtonsLayout)

        self.buttonBox = QDialogButtonBox(MillingToolsDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(MillingToolsDlg)
        self.buttonBox.accepted.connect(MillingToolsDlg.accept)
        self.buttonBox.rejected.connect(MillingToolsDlg.reject)

        QMetaObject.connectSlotsByName(MillingToolsDlg)
    # setupUi

    def retranslateUi(self, MillingToolsDlg):
        MillingToolsDlg.setWindowTitle(QCoreApplication.translate("MillingToolsDlg", u"Milling Tools", None))
        self.titleLabel.setText(QCoreApplication.translate("MillingToolsDlg", u"Milling Tool Data", None))
        self.helpLabel.setText(QCoreApplication.translate("MillingToolsDlg", u"Store milling tool geometry for configuration. These values do not change the rendered trace.", None))
        ___qtablewidgetitem = self.toolTable.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MillingToolsDlg", u"Tool", None))
        ___qtablewidgetitem1 = self.toolTable.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MillingToolsDlg", u"Type", None))
        ___qtablewidgetitem2 = self.toolTable.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("MillingToolsDlg", u"Diameter, mm", None))
        ___qtablewidgetitem3 = self.toolTable.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("MillingToolsDlg", u"Corner radius, mm", None))
        ___qtablewidgetitem4 = self.toolTable.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("MillingToolsDlg", u"Length, mm", None))
        ___qtablewidgetitem5 = self.toolTable.horizontalHeaderItem(5)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("MillingToolsDlg", u"Description", None))
        self.addButton.setText(QCoreApplication.translate("MillingToolsDlg", u"Add...", None))
        self.editButton.setText(QCoreApplication.translate("MillingToolsDlg", u"Edit...", None))
        self.removeButton.setText(QCoreApplication.translate("MillingToolsDlg", u"Remove", None))
    # retranslateUi
