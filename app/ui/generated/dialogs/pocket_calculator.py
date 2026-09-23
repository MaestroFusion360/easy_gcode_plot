# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'pocket_calculator.ui'
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
    QRadioButton, QSizePolicy, QSpacerItem, QVBoxLayout,
    QWidget)

class Ui_PocketCalculatorDialog(object):
    def setupUi(self, PocketCalculatorDialog):
        if not PocketCalculatorDialog.objectName():
            PocketCalculatorDialog.setObjectName(u"PocketCalculatorDialog")
        PocketCalculatorDialog.resize(1000, 420)
        self.verticalLayout = QVBoxLayout(PocketCalculatorDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.bodyLayout = QHBoxLayout()
        self.bodyLayout.setObjectName(u"bodyLayout")
        self.fieldsWidget = QWidget(PocketCalculatorDialog)
        self.fieldsWidget.setObjectName(u"fieldsWidget")
        self.fieldsLayout = QHBoxLayout(self.fieldsWidget)
        self.fieldsLayout.setObjectName(u"fieldsLayout")
        self.fieldsLayout.setContentsMargins(0, 0, 0, 0)
        self.geometryForm = QFormLayout()
        self.geometryForm.setObjectName(u"geometryForm")
        self.typeLabel = QLabel(self.fieldsWidget)
        self.typeLabel.setObjectName(u"typeLabel")

        self.geometryForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.typeLabel)

        self.typeLayout = QHBoxLayout()
        self.typeLayout.setObjectName(u"typeLayout")
        self.circularRadio = QRadioButton(self.fieldsWidget)
        self.circularRadio.setObjectName(u"circularRadio")
        self.circularRadio.setChecked(True)

        self.typeLayout.addWidget(self.circularRadio)

        self.rectangularRadio = QRadioButton(self.fieldsWidget)
        self.rectangularRadio.setObjectName(u"rectangularRadio")

        self.typeLayout.addWidget(self.rectangularRadio)


        self.geometryForm.setLayout(0, QFormLayout.ItemRole.FieldRole, self.typeLayout)

        self.toolDiameterLabel = QLabel(self.fieldsWidget)
        self.toolDiameterLabel.setObjectName(u"toolDiameterLabel")

        self.geometryForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.toolDiameterLabel)

        self.toolDiameterSpin = QDoubleSpinBox(self.fieldsWidget)
        self.toolDiameterSpin.setObjectName(u"toolDiameterSpin")

        self.geometryForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.toolDiameterSpin)

        self.pocketDiameterLabel = QLabel(self.fieldsWidget)
        self.pocketDiameterLabel.setObjectName(u"pocketDiameterLabel")

        self.geometryForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.pocketDiameterLabel)

        self.pocketDiameterSpin = QDoubleSpinBox(self.fieldsWidget)
        self.pocketDiameterSpin.setObjectName(u"pocketDiameterSpin")

        self.geometryForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.pocketDiameterSpin)

        self.pocketWidthLabel = QLabel(self.fieldsWidget)
        self.pocketWidthLabel.setObjectName(u"pocketWidthLabel")

        self.geometryForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.pocketWidthLabel)

        self.pocketWidthSpin = QDoubleSpinBox(self.fieldsWidget)
        self.pocketWidthSpin.setObjectName(u"pocketWidthSpin")

        self.geometryForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.pocketWidthSpin)

        self.pocketHeightLabel = QLabel(self.fieldsWidget)
        self.pocketHeightLabel.setObjectName(u"pocketHeightLabel")

        self.geometryForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.pocketHeightLabel)

        self.pocketHeightSpin = QDoubleSpinBox(self.fieldsWidget)
        self.pocketHeightSpin.setObjectName(u"pocketHeightSpin")

        self.geometryForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.pocketHeightSpin)

        self.cornerRadiusLabel = QLabel(self.fieldsWidget)
        self.cornerRadiusLabel.setObjectName(u"cornerRadiusLabel")

        self.geometryForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.cornerRadiusLabel)

        self.cornerRadiusSpin = QDoubleSpinBox(self.fieldsWidget)
        self.cornerRadiusSpin.setObjectName(u"cornerRadiusSpin")

        self.geometryForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.cornerRadiusSpin)

        self.stepoverLabel = QLabel(self.fieldsWidget)
        self.stepoverLabel.setObjectName(u"stepoverLabel")

        self.geometryForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.stepoverLabel)

        self.stepoverSpin = QDoubleSpinBox(self.fieldsWidget)
        self.stepoverSpin.setObjectName(u"stepoverSpin")

        self.geometryForm.setWidget(6, QFormLayout.ItemRole.FieldRole, self.stepoverSpin)

        self.centerXLabel = QLabel(self.fieldsWidget)
        self.centerXLabel.setObjectName(u"centerXLabel")

        self.geometryForm.setWidget(7, QFormLayout.ItemRole.LabelRole, self.centerXLabel)

        self.centerXSpin = QDoubleSpinBox(self.fieldsWidget)
        self.centerXSpin.setObjectName(u"centerXSpin")

        self.geometryForm.setWidget(7, QFormLayout.ItemRole.FieldRole, self.centerXSpin)

        self.centerYLabel = QLabel(self.fieldsWidget)
        self.centerYLabel.setObjectName(u"centerYLabel")

        self.geometryForm.setWidget(8, QFormLayout.ItemRole.LabelRole, self.centerYLabel)

        self.centerYSpin = QDoubleSpinBox(self.fieldsWidget)
        self.centerYSpin.setObjectName(u"centerYSpin")

        self.geometryForm.setWidget(8, QFormLayout.ItemRole.FieldRole, self.centerYSpin)

        self.directionLabel = QLabel(self.fieldsWidget)
        self.directionLabel.setObjectName(u"directionLabel")

        self.geometryForm.setWidget(9, QFormLayout.ItemRole.LabelRole, self.directionLabel)

        self.directionLayout = QHBoxLayout()
        self.directionLayout.setObjectName(u"directionLayout")
        self.ccwRadio = QRadioButton(self.fieldsWidget)
        self.ccwRadio.setObjectName(u"ccwRadio")
        self.ccwRadio.setChecked(True)

        self.directionLayout.addWidget(self.ccwRadio)

        self.cwRadio = QRadioButton(self.fieldsWidget)
        self.cwRadio.setObjectName(u"cwRadio")

        self.directionLayout.addWidget(self.cwRadio)


        self.geometryForm.setLayout(9, QFormLayout.ItemRole.FieldRole, self.directionLayout)

        self.optionsLayout = QVBoxLayout()
        self.optionsLayout.setObjectName(u"optionsLayout")
        self.spiralCheck = QCheckBox(self.fieldsWidget)
        self.spiralCheck.setObjectName(u"spiralCheck")

        self.optionsLayout.addWidget(self.spiralCheck)

        self.helixCheck = QCheckBox(self.fieldsWidget)
        self.helixCheck.setObjectName(u"helixCheck")

        self.optionsLayout.addWidget(self.helixCheck)

        self.correctionCheck = QCheckBox(self.fieldsWidget)
        self.correctionCheck.setObjectName(u"correctionCheck")

        self.optionsLayout.addWidget(self.correctionCheck)


        self.geometryForm.setLayout(10, QFormLayout.ItemRole.SpanningRole, self.optionsLayout)


        self.fieldsLayout.addLayout(self.geometryForm)

        self.cuttingForm = QFormLayout()
        self.cuttingForm.setObjectName(u"cuttingForm")
        self.cuttingHeaderSpacer = QLabel(self.fieldsWidget)
        self.cuttingHeaderSpacer.setObjectName(u"cuttingHeaderSpacer")
        self.cuttingHeaderSpacer.setText(u"")

        self.cuttingForm.setWidget(0, QFormLayout.ItemRole.SpanningRole, self.cuttingHeaderSpacer)

        self.zReferenceLabel = QLabel(self.fieldsWidget)
        self.zReferenceLabel.setObjectName(u"zReferenceLabel")

        self.cuttingForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.zReferenceLabel)

        self.zReferenceSpin = QDoubleSpinBox(self.fieldsWidget)
        self.zReferenceSpin.setObjectName(u"zReferenceSpin")

        self.cuttingForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.zReferenceSpin)

        self.zStartLabel = QLabel(self.fieldsWidget)
        self.zStartLabel.setObjectName(u"zStartLabel")

        self.cuttingForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.zStartLabel)

        self.zStartSpin = QDoubleSpinBox(self.fieldsWidget)
        self.zStartSpin.setObjectName(u"zStartSpin")

        self.cuttingForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.zStartSpin)

        self.zEndLabel = QLabel(self.fieldsWidget)
        self.zEndLabel.setObjectName(u"zEndLabel")

        self.cuttingForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.zEndLabel)

        self.zEndSpin = QDoubleSpinBox(self.fieldsWidget)
        self.zEndSpin.setObjectName(u"zEndSpin")

        self.cuttingForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.zEndSpin)

        self.zStepLabel = QLabel(self.fieldsWidget)
        self.zStepLabel.setObjectName(u"zStepLabel")

        self.cuttingForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.zStepLabel)

        self.zStepSpin = QDoubleSpinBox(self.fieldsWidget)
        self.zStepSpin.setObjectName(u"zStepSpin")

        self.cuttingForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.zStepSpin)

        self.stockXYLabel = QLabel(self.fieldsWidget)
        self.stockXYLabel.setObjectName(u"stockXYLabel")

        self.cuttingForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.stockXYLabel)

        self.stockXYSpin = QDoubleSpinBox(self.fieldsWidget)
        self.stockXYSpin.setObjectName(u"stockXYSpin")

        self.cuttingForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.stockXYSpin)

        self.stockZLabel = QLabel(self.fieldsWidget)
        self.stockZLabel.setObjectName(u"stockZLabel")

        self.cuttingForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.stockZLabel)

        self.stockZSpin = QDoubleSpinBox(self.fieldsWidget)
        self.stockZSpin.setObjectName(u"stockZSpin")

        self.cuttingForm.setWidget(6, QFormLayout.ItemRole.FieldRole, self.stockZSpin)

        self.feedLabel = QLabel(self.fieldsWidget)
        self.feedLabel.setObjectName(u"feedLabel")

        self.cuttingForm.setWidget(7, QFormLayout.ItemRole.LabelRole, self.feedLabel)

        self.feedSpin = QDoubleSpinBox(self.fieldsWidget)
        self.feedSpin.setObjectName(u"feedSpin")

        self.cuttingForm.setWidget(7, QFormLayout.ItemRole.FieldRole, self.feedSpin)


        self.fieldsLayout.addLayout(self.cuttingForm)


        self.bodyLayout.addWidget(self.fieldsWidget)

        self.previewHost = QWidget(PocketCalculatorDialog)
        self.previewHost.setObjectName(u"previewHost")
        self.previewHost.setMinimumSize(QSize(260, 220))
        self.previewLayout = QVBoxLayout(self.previewHost)
        self.previewLayout.setObjectName(u"previewLayout")
        self.previewLayout.setContentsMargins(0, 0, 0, 0)

        self.bodyLayout.addWidget(self.previewHost)


        self.verticalLayout.addLayout(self.bodyLayout)

        self.buttonsLayout = QHBoxLayout()
        self.buttonsLayout.setObjectName(u"buttonsLayout")
        self.buttonSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.buttonsLayout.addItem(self.buttonSpacer)

        self.clearButton = QPushButton(PocketCalculatorDialog)
        self.clearButton.setObjectName(u"clearButton")

        self.buttonsLayout.addWidget(self.clearButton)

        self.insertButton = QPushButton(PocketCalculatorDialog)
        self.insertButton.setObjectName(u"insertButton")

        self.buttonsLayout.addWidget(self.insertButton)


        self.verticalLayout.addLayout(self.buttonsLayout)


        self.retranslateUi(PocketCalculatorDialog)

        QMetaObject.connectSlotsByName(PocketCalculatorDialog)
    # setupUi

    def retranslateUi(self, PocketCalculatorDialog):
        PocketCalculatorDialog.setWindowTitle(QCoreApplication.translate("PocketCalculatorDialog", u"Pocket Calculator", None))
        self.typeLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Pocket type", None))
        self.circularRadio.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Circular", None))
        self.rectangularRadio.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Rectangular", None))
        self.toolDiameterLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Tool diameter", None))
        self.pocketDiameterLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Pocket diameter", None))
        self.pocketWidthLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Pocket width", None))
        self.pocketHeightLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Pocket height", None))
        self.cornerRadiusLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Corner radius", None))
        self.stepoverLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Stepover", None))
        self.centerXLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Center X", None))
        self.centerYLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Center Y", None))
        self.directionLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Direction", None))
        self.ccwRadio.setText(QCoreApplication.translate("PocketCalculatorDialog", u"CCW", None))
        self.cwRadio.setText(QCoreApplication.translate("PocketCalculatorDialog", u"CW", None))
        self.spiralCheck.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Spiral", None))
        self.helixCheck.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Helical entry", None))
        self.correctionCheck.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Finish contour (tool center)", None))
        self.zReferenceLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Z reference", None))
        self.zStartLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Z start", None))
        self.zEndLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Z end", None))
        self.zStepLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Z step", None))
        self.stockXYLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"XY stock", None))
        self.stockZLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Z stock", None))
        self.feedLabel.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Feed rate", None))
        self.clearButton.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Clear", None))
        self.insertButton.setText(QCoreApplication.translate("PocketCalculatorDialog", u"Insert", None))
    # retranslateUi
