# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'milling_tool_editor.ui'
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
    QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel,
    QLineEdit, QSizePolicy, QVBoxLayout, QWidget)

class Ui_MillingToolEditor(object):
    def setupUi(self, MillingToolEditor):
        if not MillingToolEditor.objectName():
            MillingToolEditor.setObjectName(u"MillingToolEditor")
        MillingToolEditor.setMinimumSize(QSize(420, 0))
        self.verticalLayout = QVBoxLayout(MillingToolEditor)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.formLayout = QFormLayout()
        self.formLayout.setObjectName(u"formLayout")
        self.toolCodeLabel = QLabel(MillingToolEditor)
        self.toolCodeLabel.setObjectName(u"toolCodeLabel")

        self.formLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.toolCodeLabel)

        self.toolCode = QLineEdit(MillingToolEditor)
        self.toolCode.setObjectName(u"toolCode")

        self.formLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.toolCode)

        self.toolTypeLabel = QLabel(MillingToolEditor)
        self.toolTypeLabel.setObjectName(u"toolTypeLabel")

        self.formLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.toolTypeLabel)

        self.toolType = QComboBox(MillingToolEditor)
        self.toolType.setObjectName(u"toolType")

        self.formLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.toolType)

        self.diameterLabel = QLabel(MillingToolEditor)
        self.diameterLabel.setObjectName(u"diameterLabel")

        self.formLayout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.diameterLabel)

        self.diameter = QDoubleSpinBox(MillingToolEditor)
        self.diameter.setObjectName(u"diameter")
        self.diameter.setDecimals(3)
        self.diameter.setMaximum(10000.000000000000000)

        self.formLayout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.diameter)

        self.cornerRadiusLabel = QLabel(MillingToolEditor)
        self.cornerRadiusLabel.setObjectName(u"cornerRadiusLabel")

        self.formLayout.setWidget(3, QFormLayout.ItemRole.LabelRole, self.cornerRadiusLabel)

        self.cornerRadius = QDoubleSpinBox(MillingToolEditor)
        self.cornerRadius.setObjectName(u"cornerRadius")
        self.cornerRadius.setDecimals(3)
        self.cornerRadius.setMaximum(10000.000000000000000)

        self.formLayout.setWidget(3, QFormLayout.ItemRole.FieldRole, self.cornerRadius)

        self.lengthLabel = QLabel(MillingToolEditor)
        self.lengthLabel.setObjectName(u"lengthLabel")

        self.formLayout.setWidget(4, QFormLayout.ItemRole.LabelRole, self.lengthLabel)

        self.length = QDoubleSpinBox(MillingToolEditor)
        self.length.setObjectName(u"length")
        self.length.setDecimals(3)
        self.length.setMaximum(10000.000000000000000)

        self.formLayout.setWidget(4, QFormLayout.ItemRole.FieldRole, self.length)

        self.cuttingHeightLabel = QLabel(MillingToolEditor)
        self.cuttingHeightLabel.setObjectName(u"cuttingHeightLabel")

        self.formLayout.setWidget(5, QFormLayout.ItemRole.LabelRole, self.cuttingHeightLabel)

        self.cuttingHeight = QDoubleSpinBox(MillingToolEditor)
        self.cuttingHeight.setObjectName(u"cuttingHeight")
        self.cuttingHeight.setDecimals(3)
        self.cuttingHeight.setMaximum(10000.000000000000000)

        self.formLayout.setWidget(5, QFormLayout.ItemRole.FieldRole, self.cuttingHeight)

        self.shankDiameterLabel = QLabel(MillingToolEditor)
        self.shankDiameterLabel.setObjectName(u"shankDiameterLabel")

        self.formLayout.setWidget(6, QFormLayout.ItemRole.LabelRole, self.shankDiameterLabel)

        self.shankDiameter = QDoubleSpinBox(MillingToolEditor)
        self.shankDiameter.setObjectName(u"shankDiameter")
        self.shankDiameter.setDecimals(3)
        self.shankDiameter.setMaximum(10000.000000000000000)

        self.formLayout.setWidget(6, QFormLayout.ItemRole.FieldRole, self.shankDiameter)

        self.tipDiameterLabel = QLabel(MillingToolEditor)
        self.tipDiameterLabel.setObjectName(u"tipDiameterLabel")

        self.formLayout.setWidget(7, QFormLayout.ItemRole.LabelRole, self.tipDiameterLabel)

        self.tipDiameter = QDoubleSpinBox(MillingToolEditor)
        self.tipDiameter.setObjectName(u"tipDiameter")
        self.tipDiameter.setDecimals(3)
        self.tipDiameter.setMaximum(10000.000000000000000)

        self.formLayout.setWidget(7, QFormLayout.ItemRole.FieldRole, self.tipDiameter)

        self.chamferAngleLabel = QLabel(MillingToolEditor)
        self.chamferAngleLabel.setObjectName(u"chamferAngleLabel")

        self.formLayout.setWidget(8, QFormLayout.ItemRole.LabelRole, self.chamferAngleLabel)

        self.chamferAngle = QDoubleSpinBox(MillingToolEditor)
        self.chamferAngle.setObjectName(u"chamferAngle")
        self.chamferAngle.setDecimals(1)
        self.chamferAngle.setMinimum(1.000000000000000)
        self.chamferAngle.setMaximum(179.000000000000000)

        self.formLayout.setWidget(8, QFormLayout.ItemRole.FieldRole, self.chamferAngle)

        self.tipAngleLabel = QLabel(MillingToolEditor)
        self.tipAngleLabel.setObjectName(u"tipAngleLabel")

        self.formLayout.setWidget(9, QFormLayout.ItemRole.LabelRole, self.tipAngleLabel)

        self.tipAngle = QDoubleSpinBox(MillingToolEditor)
        self.tipAngle.setObjectName(u"tipAngle")
        self.tipAngle.setDecimals(1)
        self.tipAngle.setMinimum(1.000000000000000)
        self.tipAngle.setMaximum(179.000000000000000)

        self.formLayout.setWidget(9, QFormLayout.ItemRole.FieldRole, self.tipAngle)

        self.descriptionLabel = QLabel(MillingToolEditor)
        self.descriptionLabel.setObjectName(u"descriptionLabel")

        self.formLayout.setWidget(10, QFormLayout.ItemRole.LabelRole, self.descriptionLabel)

        self.description = QLineEdit(MillingToolEditor)
        self.description.setObjectName(u"description")

        self.formLayout.setWidget(10, QFormLayout.ItemRole.FieldRole, self.description)


        self.verticalLayout.addLayout(self.formLayout)

        self.buttonBox = QDialogButtonBox(MillingToolEditor)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(MillingToolEditor)

        QMetaObject.connectSlotsByName(MillingToolEditor)
    # setupUi

    def retranslateUi(self, MillingToolEditor):
        self.toolCodeLabel.setText(QCoreApplication.translate("MillingToolEditor", u"T code", None))
        self.toolTypeLabel.setText(QCoreApplication.translate("MillingToolEditor", u"Type", None))
        self.diameterLabel.setText(QCoreApplication.translate("MillingToolEditor", u"Diameter, mm", None))
        self.cornerRadiusLabel.setText(QCoreApplication.translate("MillingToolEditor", u"Corner radius, mm", None))
        self.lengthLabel.setText(QCoreApplication.translate("MillingToolEditor", u"Length, mm", None))
        self.cuttingHeightLabel.setText(QCoreApplication.translate("MillingToolEditor", u"Cutting height, mm", None))
        self.shankDiameterLabel.setText(QCoreApplication.translate("MillingToolEditor", u"Shank diameter, mm", None))
        self.tipDiameterLabel.setText(QCoreApplication.translate("MillingToolEditor", u"Tip diameter, mm", None))
        self.chamferAngleLabel.setText(QCoreApplication.translate("MillingToolEditor", u"Chamfer angle, deg", None))
        self.tipAngleLabel.setText(QCoreApplication.translate("MillingToolEditor", u"Tip angle, deg", None))
        self.descriptionLabel.setText(QCoreApplication.translate("MillingToolEditor", u"Description", None))
        pass
    # retranslateUi
