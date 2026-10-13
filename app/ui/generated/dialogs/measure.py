# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'measure.ui'
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
from PyQt6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QCheckBox,
    QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView,
    QLabel, QSizePolicy, QSpacerItem, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

class Ui_MeasureDialog(object):
    def setupUi(self, MeasureDialog):
        if not MeasureDialog.objectName():
            MeasureDialog.setObjectName(u"MeasureDialog")
        self.measureLayout = QVBoxLayout(MeasureDialog)
        self.measureLayout.setObjectName(u"measureLayout")
        self.coordinatesTable = QTableWidget(MeasureDialog)
        if (self.coordinatesTable.columnCount() < 3):
            self.coordinatesTable.setColumnCount(3)
        __qtablewidgetitem = QTableWidgetItem()
        self.coordinatesTable.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.coordinatesTable.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.coordinatesTable.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        if (self.coordinatesTable.rowCount() < 3):
            self.coordinatesTable.setRowCount(3)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.coordinatesTable.setVerticalHeaderItem(0, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.coordinatesTable.setVerticalHeaderItem(1, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.coordinatesTable.setVerticalHeaderItem(2, __qtablewidgetitem5)
        self.coordinatesTable.setObjectName(u"coordinatesTable")
        self.coordinatesTable.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.coordinatesTable.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.coordinatesTable.setRowCount(3)

        self.measureLayout.addWidget(self.coordinatesTable)

        self.statusLabel = QLabel(MeasureDialog)
        self.statusLabel.setObjectName(u"statusLabel")
        self.statusLabel.setWordWrap(True)
        self.statusLabel.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.statusLabel.sizePolicy().hasHeightForWidth())
        self.statusLabel.setSizePolicy(sizePolicy)

        self.measureLayout.addWidget(self.statusLabel)

        self.footerLayout = QHBoxLayout()
        self.footerLayout.setObjectName(u"footerLayout")
        self.inchesCheck = QCheckBox(MeasureDialog)
        self.inchesCheck.setObjectName(u"inchesCheck")

        self.footerLayout.addWidget(self.inchesCheck)

        self.footerSpacer = QSpacerItem(20, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.footerLayout.addItem(self.footerSpacer)

        self.buttonBox = QDialogButtonBox(MeasureDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Close|QDialogButtonBox.StandardButton.Reset)
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.buttonBox.sizePolicy().hasHeightForWidth())
        self.buttonBox.setSizePolicy(sizePolicy1)

        self.footerLayout.addWidget(self.buttonBox)

        self.footerLayout.setStretch(1, 1)

        self.measureLayout.addLayout(self.footerLayout)


        self.retranslateUi(MeasureDialog)

        QMetaObject.connectSlotsByName(MeasureDialog)
    # setupUi

    def retranslateUi(self, MeasureDialog):
        MeasureDialog.setWindowTitle(QCoreApplication.translate("MeasureDialog", u"Measure", None))
        ___qtablewidgetitem = self.coordinatesTable.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MeasureDialog", u"X", None))
        ___qtablewidgetitem1 = self.coordinatesTable.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MeasureDialog", u"Y", None))
        ___qtablewidgetitem2 = self.coordinatesTable.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("MeasureDialog", u"Z", None))
        ___qtablewidgetitem3 = self.coordinatesTable.verticalHeaderItem(0)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("MeasureDialog", u"From", None))
        ___qtablewidgetitem4 = self.coordinatesTable.verticalHeaderItem(1)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("MeasureDialog", u"To", None))
        ___qtablewidgetitem5 = self.coordinatesTable.verticalHeaderItem(2)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("MeasureDialog", u"Difference", None))
        self.statusLabel.setText("")
        self.inchesCheck.setText(QCoreApplication.translate("MeasureDialog", u"Inches", None))
    # retranslateUi
