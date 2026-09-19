# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'block_num.ui'
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
from PyQt6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QDialog,
    QDialogButtonBox, QGridLayout, QLabel, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget)

class Ui_BlockNumberDlg(object):
    def setupUi(self, BlockNumberDlg):
        if not BlockNumberDlg.objectName():
            BlockNumberDlg.setObjectName(u"BlockNumberDlg")
        BlockNumberDlg.resize(200, 150)
        BlockNumberDlg.setMinimumSize(QSize(200, 150))
        self.verticalLayout = QVBoxLayout(BlockNumberDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName(u"gridLayout")
        self.labelStart = QLabel(BlockNumberDlg)
        self.labelStart.setObjectName(u"labelStart")

        self.gridLayout.addWidget(self.labelStart, 0, 0, 1, 1)

        self.labelInterval = QLabel(BlockNumberDlg)
        self.labelInterval.setObjectName(u"labelInterval")

        self.gridLayout.addWidget(self.labelInterval, 1, 0, 1, 1)

        self.labelSpacing = QLabel(BlockNumberDlg)
        self.labelSpacing.setObjectName(u"labelSpacing")

        self.gridLayout.addWidget(self.labelSpacing, 2, 0, 1, 1)

        self.spacingCmbBox = QComboBox(BlockNumberDlg)
        self.spacingCmbBox.addItem("")
        self.spacingCmbBox.addItem("")
        self.spacingCmbBox.setObjectName(u"spacingCmbBox")

        self.gridLayout.addWidget(self.spacingCmbBox, 2, 1, 1, 1)

        self.startSpinBox = QSpinBox(BlockNumberDlg)
        self.startSpinBox.setObjectName(u"startSpinBox")
        self.startSpinBox.setMinimum(1)
        self.startSpinBox.setMaximum(99999)

        self.gridLayout.addWidget(self.startSpinBox, 0, 1, 1, 1)

        self.intervSpinBox = QSpinBox(BlockNumberDlg)
        self.intervSpinBox.setObjectName(u"intervSpinBox")
        self.intervSpinBox.setMinimum(1)
        self.intervSpinBox.setMaximum(99999)

        self.gridLayout.addWidget(self.intervSpinBox, 1, 1, 1, 1)


        self.verticalLayout.addLayout(self.gridLayout)

        self.buttonBox = QDialogButtonBox(BlockNumberDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(BlockNumberDlg)
        self.buttonBox.accepted.connect(BlockNumberDlg.accept)
        self.buttonBox.rejected.connect(BlockNumberDlg.reject)

        QMetaObject.connectSlotsByName(BlockNumberDlg)
    # setupUi

    def retranslateUi(self, BlockNumberDlg):
        BlockNumberDlg.setWindowTitle(QCoreApplication.translate("BlockNumberDlg", u"Block Numbers", None))
        self.labelStart.setText(QCoreApplication.translate("BlockNumberDlg", u"Start", None))
        self.labelInterval.setText(QCoreApplication.translate("BlockNumberDlg", u"Interval", None))
        self.labelSpacing.setText(QCoreApplication.translate("BlockNumberDlg", u"Spacing", None))
        self.spacingCmbBox.setItemText(0, QCoreApplication.translate("BlockNumberDlg", u"No", None))
        self.spacingCmbBox.setItemText(1, QCoreApplication.translate("BlockNumberDlg", u"Yes", None))

    # retranslateUi
