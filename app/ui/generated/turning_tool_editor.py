# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'turning_tool_editor.ui'
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
from PyQt6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QRadioButton,
    QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)

import app.resources.files_res  # noqa: F401  # Registers Qt resources on import.

class Ui_TurningToolEditor(object):
    def setupUi(self, TurningToolEditor):
        if not TurningToolEditor.objectName():
            TurningToolEditor.setObjectName(u"TurningToolEditor")
        TurningToolEditor.setMinimumSize(QSize(620, 0))
        self.verticalLayout = QVBoxLayout(TurningToolEditor)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.formLayout = QFormLayout()
        self.formLayout.setObjectName(u"formLayout")
        self.toolCodeLabel = QLabel(TurningToolEditor)
        self.toolCodeLabel.setObjectName(u"toolCodeLabel")

        self.formLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.toolCodeLabel)

        self.toolCode = QLineEdit(TurningToolEditor)
        self.toolCode.setObjectName(u"toolCode")

        self.formLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.toolCode)

        self.categoryLabel = QLabel(TurningToolEditor)
        self.categoryLabel.setObjectName(u"categoryLabel")

        self.formLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.categoryLabel)

        self.categoryWidget = QWidget(TurningToolEditor)
        self.categoryWidget.setObjectName(u"categoryWidget")
        self.categoryLayout = QHBoxLayout(self.categoryWidget)
        self.categoryLayout.setObjectName(u"categoryLayout")
        self.categoryLayout.setContentsMargins(0, 0, 0, 0)
        self.insertCategoryButton = QRadioButton(self.categoryWidget)
        self.insertCategoryButton.setObjectName(u"insertCategoryButton")

        self.categoryLayout.addWidget(self.insertCategoryButton)

        self.grooveCategoryButton = QRadioButton(self.categoryWidget)
        self.grooveCategoryButton.setObjectName(u"grooveCategoryButton")

        self.categoryLayout.addWidget(self.grooveCategoryButton)

        self.threadCategoryButton = QRadioButton(self.categoryWidget)
        self.threadCategoryButton.setObjectName(u"threadCategoryButton")

        self.categoryLayout.addWidget(self.threadCategoryButton)

        self.drillCategoryButton = QRadioButton(self.categoryWidget)
        self.drillCategoryButton.setObjectName(u"drillCategoryButton")

        self.categoryLayout.addWidget(self.drillCategoryButton)

        self.tapCategoryButton = QRadioButton(self.categoryWidget)
        self.tapCategoryButton.setObjectName(u"tapCategoryButton")

        self.categoryLayout.addWidget(self.tapCategoryButton)


        self.formLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.categoryWidget)

        self.directionLabel = QLabel(TurningToolEditor)
        self.directionLabel.setObjectName(u"directionLabel")

        self.formLayout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.directionLabel)

        self.directionWidget = QWidget(TurningToolEditor)
        self.directionWidget.setObjectName(u"directionWidget")
        self.directionLayout = QHBoxLayout(self.directionWidget)
        self.directionLayout.setObjectName(u"directionLayout")
        self.directionLayout.setContentsMargins(0, 0, 0, 0)
        self.odCheck = QCheckBox(self.directionWidget)
        self.odCheck.setObjectName(u"odCheck")

        self.directionLayout.addWidget(self.odCheck)

        self.idCheck = QCheckBox(self.directionWidget)
        self.idCheck.setObjectName(u"idCheck")

        self.directionLayout.addWidget(self.idCheck)

        self.faceCheck = QCheckBox(self.directionWidget)
        self.faceCheck.setObjectName(u"faceCheck")

        self.directionLayout.addWidget(self.faceCheck)

        self.directionSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.directionLayout.addItem(self.directionSpacer)


        self.formLayout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.directionWidget)

        self.insertTypeLabel = QLabel(TurningToolEditor)
        self.insertTypeLabel.setObjectName(u"insertTypeLabel")

        self.formLayout.setWidget(3, QFormLayout.ItemRole.LabelRole, self.insertTypeLabel)

        self.insertType = QComboBox(TurningToolEditor)
        self.insertType.setObjectName(u"insertType")

        self.formLayout.setWidget(3, QFormLayout.ItemRole.FieldRole, self.insertType)

        self.grooveTypeLabel = QLabel(TurningToolEditor)
        self.grooveTypeLabel.setObjectName(u"grooveTypeLabel")

        self.formLayout.setWidget(4, QFormLayout.ItemRole.LabelRole, self.grooveTypeLabel)

        self.grooveType = QComboBox(TurningToolEditor)
        self.grooveType.setObjectName(u"grooveType")

        self.formLayout.setWidget(4, QFormLayout.ItemRole.FieldRole, self.grooveType)

        self.threadTypeLabel = QLabel(TurningToolEditor)
        self.threadTypeLabel.setObjectName(u"threadTypeLabel")

        self.formLayout.setWidget(5, QFormLayout.ItemRole.LabelRole, self.threadTypeLabel)

        self.threadType = QComboBox(TurningToolEditor)
        self.threadType.setObjectName(u"threadType")

        self.formLayout.setWidget(5, QFormLayout.ItemRole.FieldRole, self.threadType)

        self.drillTypeLabel = QLabel(TurningToolEditor)
        self.drillTypeLabel.setObjectName(u"drillTypeLabel")

        self.formLayout.setWidget(6, QFormLayout.ItemRole.LabelRole, self.drillTypeLabel)

        self.drillType = QComboBox(TurningToolEditor)
        self.drillType.setObjectName(u"drillType")

        self.formLayout.setWidget(6, QFormLayout.ItemRole.FieldRole, self.drillType)

        self.tapTypeLabel = QLabel(TurningToolEditor)
        self.tapTypeLabel.setObjectName(u"tapTypeLabel")

        self.formLayout.setWidget(7, QFormLayout.ItemRole.LabelRole, self.tapTypeLabel)

        self.tapType = QComboBox(TurningToolEditor)
        self.tapType.setObjectName(u"tapType")

        self.formLayout.setWidget(7, QFormLayout.ItemRole.FieldRole, self.tapType)

        self.noseRadiusLabel = QLabel(TurningToolEditor)
        self.noseRadiusLabel.setObjectName(u"noseRadiusLabel")

        self.formLayout.setWidget(8, QFormLayout.ItemRole.LabelRole, self.noseRadiusLabel)

        self.noseRadius = QDoubleSpinBox(TurningToolEditor)
        self.noseRadius.setObjectName(u"noseRadius")
        self.noseRadius.setDecimals(3)
        self.noseRadius.setMaximum(999999.998999999952503)

        self.formLayout.setWidget(8, QFormLayout.ItemRole.FieldRole, self.noseRadius)

        self.tipOrientationLabel = QLabel(TurningToolEditor)
        self.tipOrientationLabel.setObjectName(u"tipOrientationLabel")

        self.formLayout.setWidget(9, QFormLayout.ItemRole.LabelRole, self.tipOrientationLabel)

        self.tipOrientation = QComboBox(TurningToolEditor)
        self.tipOrientation.setObjectName(u"tipOrientation")

        self.formLayout.setWidget(9, QFormLayout.ItemRole.FieldRole, self.tipOrientation)

        self.insertLengthLabel = QLabel(TurningToolEditor)
        self.insertLengthLabel.setObjectName(u"insertLengthLabel")

        self.formLayout.setWidget(10, QFormLayout.ItemRole.LabelRole, self.insertLengthLabel)

        self.insertLength = QDoubleSpinBox(TurningToolEditor)
        self.insertLength.setObjectName(u"insertLength")
        self.insertLength.setDecimals(3)
        self.insertLength.setMinimum(0.001000000000000)
        self.insertLength.setMaximum(10000.000000000000000)

        self.formLayout.setWidget(10, QFormLayout.ItemRole.FieldRole, self.insertLength)

        self.widthLabel = QLabel(TurningToolEditor)
        self.widthLabel.setObjectName(u"widthLabel")

        self.formLayout.setWidget(11, QFormLayout.ItemRole.LabelRole, self.widthLabel)

        self.width = QDoubleSpinBox(TurningToolEditor)
        self.width.setObjectName(u"width")
        self.width.setDecimals(3)
        self.width.setMinimum(0.001000000000000)
        self.width.setMaximum(10000.000000000000000)

        self.formLayout.setWidget(11, QFormLayout.ItemRole.FieldRole, self.width)

        self.diameterLabel = QLabel(TurningToolEditor)
        self.diameterLabel.setObjectName(u"diameterLabel")

        self.formLayout.setWidget(12, QFormLayout.ItemRole.LabelRole, self.diameterLabel)

        self.diameter = QDoubleSpinBox(TurningToolEditor)
        self.diameter.setObjectName(u"diameter")
        self.diameter.setDecimals(3)
        self.diameter.setMinimum(0.001000000000000)
        self.diameter.setMaximum(10000.000000000000000)

        self.formLayout.setWidget(12, QFormLayout.ItemRole.FieldRole, self.diameter)

        self.lengthLabel = QLabel(TurningToolEditor)
        self.lengthLabel.setObjectName(u"lengthLabel")

        self.formLayout.setWidget(13, QFormLayout.ItemRole.LabelRole, self.lengthLabel)

        self.length = QDoubleSpinBox(TurningToolEditor)
        self.length.setObjectName(u"length")
        self.length.setDecimals(3)
        self.length.setMinimum(0.001000000000000)
        self.length.setMaximum(100000.000000000000000)

        self.formLayout.setWidget(13, QFormLayout.ItemRole.FieldRole, self.length)

        self.tipAngleLabel = QLabel(TurningToolEditor)
        self.tipAngleLabel.setObjectName(u"tipAngleLabel")

        self.formLayout.setWidget(14, QFormLayout.ItemRole.LabelRole, self.tipAngleLabel)

        self.tipAngle = QDoubleSpinBox(TurningToolEditor)
        self.tipAngle.setObjectName(u"tipAngle")
        self.tipAngle.setDecimals(1)
        self.tipAngle.setMinimum(1.000000000000000)
        self.tipAngle.setMaximum(179.000000000000000)

        self.formLayout.setWidget(14, QFormLayout.ItemRole.FieldRole, self.tipAngle)

        self.threadHelpLabel = QLabel(TurningToolEditor)
        self.threadHelpLabel.setObjectName(u"threadHelpLabel")

        self.formLayout.setWidget(15, QFormLayout.ItemRole.LabelRole, self.threadHelpLabel)

        self.threadHelp = QLabel(TurningToolEditor)
        self.threadHelp.setObjectName(u"threadHelp")
        self.threadHelp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.threadHelp.setPixmap(QPixmap(u":/resource/icons/thread.png"))

        self.formLayout.setWidget(15, QFormLayout.ItemRole.FieldRole, self.threadHelp)

        self.threadAngleLabel = QLabel(TurningToolEditor)
        self.threadAngleLabel.setObjectName(u"threadAngleLabel")

        self.formLayout.setWidget(16, QFormLayout.ItemRole.LabelRole, self.threadAngleLabel)

        self.threadAngle = QDoubleSpinBox(TurningToolEditor)
        self.threadAngle.setObjectName(u"threadAngle")
        self.threadAngle.setDecimals(1)
        self.threadAngle.setMinimum(1.000000000000000)
        self.threadAngle.setMaximum(179.000000000000000)

        self.formLayout.setWidget(16, QFormLayout.ItemRole.FieldRole, self.threadAngle)

        self.threadTipWidthLabel = QLabel(TurningToolEditor)
        self.threadTipWidthLabel.setObjectName(u"threadTipWidthLabel")

        self.formLayout.setWidget(17, QFormLayout.ItemRole.LabelRole, self.threadTipWidthLabel)

        self.threadTipWidth = QDoubleSpinBox(TurningToolEditor)
        self.threadTipWidth.setObjectName(u"threadTipWidth")
        self.threadTipWidth.setDecimals(3)
        self.threadTipWidth.setMinimum(0.001000000000000)
        self.threadTipWidth.setMaximum(10000.000000000000000)

        self.formLayout.setWidget(17, QFormLayout.ItemRole.FieldRole, self.threadTipWidth)

        self.threadCornerRadiusLabel = QLabel(TurningToolEditor)
        self.threadCornerRadiusLabel.setObjectName(u"threadCornerRadiusLabel")

        self.formLayout.setWidget(18, QFormLayout.ItemRole.LabelRole, self.threadCornerRadiusLabel)

        self.threadCornerRadius = QDoubleSpinBox(TurningToolEditor)
        self.threadCornerRadius.setObjectName(u"threadCornerRadius")
        self.threadCornerRadius.setDecimals(3)
        self.threadCornerRadius.setMaximum(10000.000000000000000)

        self.formLayout.setWidget(18, QFormLayout.ItemRole.FieldRole, self.threadCornerRadius)

        self.descriptionLabel = QLabel(TurningToolEditor)
        self.descriptionLabel.setObjectName(u"descriptionLabel")

        self.formLayout.setWidget(19, QFormLayout.ItemRole.LabelRole, self.descriptionLabel)

        self.description = QLineEdit(TurningToolEditor)
        self.description.setObjectName(u"description")

        self.formLayout.setWidget(19, QFormLayout.ItemRole.FieldRole, self.description)


        self.verticalLayout.addLayout(self.formLayout)

        self.buttonBox = QDialogButtonBox(TurningToolEditor)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(TurningToolEditor)

        QMetaObject.connectSlotsByName(TurningToolEditor)
    # setupUi

    def retranslateUi(self, TurningToolEditor):
        self.toolCodeLabel.setText(QCoreApplication.translate("TurningToolEditor", u"T code", None))
        self.categoryLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Category", None))
        self.insertCategoryButton.setText(QCoreApplication.translate("TurningToolEditor", u"Cutting tool", None))
        self.grooveCategoryButton.setText(QCoreApplication.translate("TurningToolEditor", u"Groove", None))
        self.threadCategoryButton.setText(QCoreApplication.translate("TurningToolEditor", u"Thread", None))
        self.drillCategoryButton.setText(QCoreApplication.translate("TurningToolEditor", u"Drill", None))
        self.tapCategoryButton.setText(QCoreApplication.translate("TurningToolEditor", u"Tap", None))
        self.directionLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Machining direction", None))
        self.odCheck.setText(QCoreApplication.translate("TurningToolEditor", u"OD", None))
        self.idCheck.setText(QCoreApplication.translate("TurningToolEditor", u"ID", None))
        self.faceCheck.setText(QCoreApplication.translate("TurningToolEditor", u"Face", None))
        self.insertTypeLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Turning tool", None))
        self.grooveTypeLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Groove type", None))
        self.threadTypeLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Thread type", None))
        self.drillTypeLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Drill type", None))
        self.tapTypeLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Tap type", None))
        self.noseRadiusLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Nose radius, mm", None))
        self.tipOrientationLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Tip orientation", None))
        self.insertLengthLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Length/Diameter, mm", None))
        self.widthLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Groove width, mm", None))
        self.diameterLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Tool diameter, mm", None))
        self.lengthLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Tool length, mm", None))
        self.tipAngleLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Tip angle, deg", None))
        self.threadHelpLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Thread geometry", None))
        self.threadHelp.setText("")
        self.threadAngleLabel.setText(QCoreApplication.translate("TurningToolEditor", u"E, deg", None))
        self.threadTipWidthLabel.setText(QCoreApplication.translate("TurningToolEditor", u"EX, mm", None))
        self.threadCornerRadiusLabel.setText(QCoreApplication.translate("TurningToolEditor", u"RC, mm", None))
        self.descriptionLabel.setText(QCoreApplication.translate("TurningToolEditor", u"Description", None))
        pass
    # retranslateUi
