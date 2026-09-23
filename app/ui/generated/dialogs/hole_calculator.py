# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'hole_calculator.ui'
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
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDialog, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QSpacerItem, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget)

class Ui_HoleCalculatorDialog(object):
    def setupUi(self, HoleCalculatorDialog):
        if not HoleCalculatorDialog.objectName():
            HoleCalculatorDialog.setObjectName(u"HoleCalculatorDialog")
        HoleCalculatorDialog.resize(760, 360)
        self.verticalLayout = QVBoxLayout(HoleCalculatorDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.bodyLayout = QHBoxLayout()
        self.bodyLayout.setObjectName(u"bodyLayout")
        self.patternTabs = QTabWidget(HoleCalculatorDialog)
        self.patternTabs.setObjectName(u"patternTabs")
        self.circleTab = QWidget()
        self.circleTab.setObjectName(u"circleTab")
        self.circleForm = QFormLayout(self.circleTab)
        self.circleForm.setObjectName(u"circleForm")
        self.diameterLabel = QLabel(self.circleTab)
        self.diameterLabel.setObjectName(u"diameterLabel")

        self.circleForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.diameterLabel)

        self.diameterSpin = QDoubleSpinBox(self.circleTab)
        self.diameterSpin.setObjectName(u"diameterSpin")
        self.diameterSpin.setDecimals(3)
        self.diameterSpin.setMaximum(1000000.000000000000000)
        self.diameterSpin.setValue(100.000000000000000)

        self.circleForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.diameterSpin)

        self.startAngleLabel = QLabel(self.circleTab)
        self.startAngleLabel.setObjectName(u"startAngleLabel")

        self.circleForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.startAngleLabel)

        self.startAngleSpin = QDoubleSpinBox(self.circleTab)
        self.startAngleSpin.setObjectName(u"startAngleSpin")
        self.startAngleSpin.setDecimals(3)
        self.startAngleSpin.setMinimum(-360.000000000000000)
        self.startAngleSpin.setMaximum(360.000000000000000)

        self.circleForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.startAngleSpin)

        self.centerXLabel = QLabel(self.circleTab)
        self.centerXLabel.setObjectName(u"centerXLabel")

        self.circleForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.centerXLabel)

        self.centerXSpin = QDoubleSpinBox(self.circleTab)
        self.centerXSpin.setObjectName(u"centerXSpin")
        self.centerXSpin.setDecimals(3)
        self.centerXSpin.setMinimum(-1000000.000000000000000)
        self.centerXSpin.setMaximum(1000000.000000000000000)

        self.circleForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.centerXSpin)

        self.centerYLabel = QLabel(self.circleTab)
        self.centerYLabel.setObjectName(u"centerYLabel")

        self.circleForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.centerYLabel)

        self.centerYSpin = QDoubleSpinBox(self.circleTab)
        self.centerYSpin.setObjectName(u"centerYSpin")
        self.centerYSpin.setDecimals(3)
        self.centerYSpin.setMinimum(-1000000.000000000000000)
        self.centerYSpin.setMaximum(1000000.000000000000000)

        self.circleForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.centerYSpin)

        self.holeCountLabel = QLabel(self.circleTab)
        self.holeCountLabel.setObjectName(u"holeCountLabel")

        self.circleForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.holeCountLabel)

        self.holeCountSpin = QSpinBox(self.circleTab)
        self.holeCountSpin.setObjectName(u"holeCountSpin")
        self.holeCountSpin.setMinimum(1)
        self.holeCountSpin.setMaximum(10000)
        self.holeCountSpin.setValue(10)

        self.circleForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.holeCountSpin)

        self.ccwCheck = QCheckBox(self.circleTab)
        self.ccwCheck.setObjectName(u"ccwCheck")
        self.ccwCheck.setChecked(True)

        self.circleForm.setWidget(5, QFormLayout.ItemRole.SpanningRole, self.ccwCheck)

        self.patternTabs.addTab(self.circleTab, "")
        self.gridTab = QWidget()
        self.gridTab.setObjectName(u"gridTab")
        self.gridForm = QFormLayout(self.gridTab)
        self.gridForm.setObjectName(u"gridForm")
        self.startXLabel = QLabel(self.gridTab)
        self.startXLabel.setObjectName(u"startXLabel")

        self.gridForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.startXLabel)

        self.startXSpin = QDoubleSpinBox(self.gridTab)
        self.startXSpin.setObjectName(u"startXSpin")
        self.startXSpin.setDecimals(3)
        self.startXSpin.setMinimum(-1000000.000000000000000)
        self.startXSpin.setMaximum(1000000.000000000000000)

        self.gridForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.startXSpin)

        self.startYLabel = QLabel(self.gridTab)
        self.startYLabel.setObjectName(u"startYLabel")

        self.gridForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.startYLabel)

        self.startYSpin = QDoubleSpinBox(self.gridTab)
        self.startYSpin.setObjectName(u"startYSpin")
        self.startYSpin.setDecimals(3)
        self.startYSpin.setMinimum(-1000000.000000000000000)
        self.startYSpin.setMaximum(1000000.000000000000000)

        self.gridForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.startYSpin)

        self.stepXLabel = QLabel(self.gridTab)
        self.stepXLabel.setObjectName(u"stepXLabel")

        self.gridForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.stepXLabel)

        self.stepXSpin = QDoubleSpinBox(self.gridTab)
        self.stepXSpin.setObjectName(u"stepXSpin")
        self.stepXSpin.setDecimals(3)
        self.stepXSpin.setMinimum(-1000000.000000000000000)
        self.stepXSpin.setMaximum(1000000.000000000000000)
        self.stepXSpin.setValue(10.000000000000000)

        self.gridForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.stepXSpin)

        self.stepYLabel = QLabel(self.gridTab)
        self.stepYLabel.setObjectName(u"stepYLabel")

        self.gridForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.stepYLabel)

        self.stepYSpin = QDoubleSpinBox(self.gridTab)
        self.stepYSpin.setObjectName(u"stepYSpin")
        self.stepYSpin.setDecimals(3)
        self.stepYSpin.setMinimum(-1000000.000000000000000)
        self.stepYSpin.setMaximum(1000000.000000000000000)
        self.stepYSpin.setValue(10.000000000000000)

        self.gridForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.stepYSpin)

        self.countXLabel = QLabel(self.gridTab)
        self.countXLabel.setObjectName(u"countXLabel")

        self.gridForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.countXLabel)

        self.countXSpin = QSpinBox(self.gridTab)
        self.countXSpin.setObjectName(u"countXSpin")
        self.countXSpin.setMinimum(1)
        self.countXSpin.setMaximum(10000)
        self.countXSpin.setValue(1)

        self.gridForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.countXSpin)

        self.countYLabel = QLabel(self.gridTab)
        self.countYLabel.setObjectName(u"countYLabel")

        self.gridForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.countYLabel)

        self.countYSpin = QSpinBox(self.gridTab)
        self.countYSpin.setObjectName(u"countYSpin")
        self.countYSpin.setMinimum(1)
        self.countYSpin.setMaximum(10000)
        self.countYSpin.setValue(1)

        self.gridForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.countYSpin)

        self.patternTabs.addTab(self.gridTab, "")

        self.bodyLayout.addWidget(self.patternTabs)

        self.previewHost = QWidget(HoleCalculatorDialog)
        self.previewHost.setObjectName(u"previewHost")
        self.previewHost.setMinimumSize(QSize(240, 220))
        self.previewLayout = QVBoxLayout(self.previewHost)
        self.previewLayout.setObjectName(u"previewLayout")
        self.previewLayout.setContentsMargins(0, 0, 0, 0)

        self.bodyLayout.addWidget(self.previewHost)


        self.verticalLayout.addLayout(self.bodyLayout)

        self.buttonsLayout = QHBoxLayout()
        self.buttonsLayout.setObjectName(u"buttonsLayout")
        self.buttonSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.buttonsLayout.addItem(self.buttonSpacer)

        self.clearButton = QPushButton(HoleCalculatorDialog)
        self.clearButton.setObjectName(u"clearButton")

        self.buttonsLayout.addWidget(self.clearButton)

        self.insertButton = QPushButton(HoleCalculatorDialog)
        self.insertButton.setObjectName(u"insertButton")

        self.buttonsLayout.addWidget(self.insertButton)


        self.verticalLayout.addLayout(self.buttonsLayout)


        self.retranslateUi(HoleCalculatorDialog)

        QMetaObject.connectSlotsByName(HoleCalculatorDialog)
    # setupUi

    def retranslateUi(self, HoleCalculatorDialog):
        HoleCalculatorDialog.setWindowTitle(QCoreApplication.translate("HoleCalculatorDialog", u"Hole Calculator", None))
        self.diameterLabel.setText(QCoreApplication.translate("HoleCalculatorDialog", u"Diameter", None))
        self.startAngleLabel.setText(QCoreApplication.translate("HoleCalculatorDialog", u"Start angle", None))
        self.centerXLabel.setText(QCoreApplication.translate("HoleCalculatorDialog", u"Center X", None))
        self.centerYLabel.setText(QCoreApplication.translate("HoleCalculatorDialog", u"Center Y", None))
        self.holeCountLabel.setText(QCoreApplication.translate("HoleCalculatorDialog", u"Hole count", None))
        self.ccwCheck.setText(QCoreApplication.translate("HoleCalculatorDialog", u"Counterclockwise", None))
        self.patternTabs.setTabText(self.patternTabs.indexOf(self.circleTab), QCoreApplication.translate("HoleCalculatorDialog", u"Circular", None))
        self.startXLabel.setText(QCoreApplication.translate("HoleCalculatorDialog", u"Start X", None))
        self.startYLabel.setText(QCoreApplication.translate("HoleCalculatorDialog", u"Start Y", None))
        self.stepXLabel.setText(QCoreApplication.translate("HoleCalculatorDialog", u"Step X", None))
        self.stepYLabel.setText(QCoreApplication.translate("HoleCalculatorDialog", u"Step Y", None))
        self.countXLabel.setText(QCoreApplication.translate("HoleCalculatorDialog", u"Count X", None))
        self.countYLabel.setText(QCoreApplication.translate("HoleCalculatorDialog", u"Count Y", None))
        self.patternTabs.setTabText(self.patternTabs.indexOf(self.gridTab), QCoreApplication.translate("HoleCalculatorDialog", u"Grid", None))
        self.clearButton.setText(QCoreApplication.translate("HoleCalculatorDialog", u"Clear", None))
        self.insertButton.setText(QCoreApplication.translate("HoleCalculatorDialog", u"Insert", None))
    # retranslateUi
