# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'stock.ui'
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
from PyQt6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QDialog,
    QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QSlider,
    QSpacerItem, QVBoxLayout, QWidget)

class Ui_StockDialog(object):
    def setupUi(self, StockDialog):
        if not StockDialog.objectName():
            StockDialog.setObjectName(u"StockDialog")
        self.verticalLayout = QVBoxLayout(StockDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.enabledCheck = QCheckBox(StockDialog)
        self.enabledCheck.setObjectName(u"enabledCheck")

        self.verticalLayout.addWidget(self.enabledCheck)

        self.formLayout = QFormLayout()
        self.formLayout.setObjectName(u"formLayout")
        self.outerLabel = QLabel(StockDialog)
        self.outerLabel.setObjectName(u"outerLabel")

        self.formLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.outerLabel)

        self.outerSpin = QDoubleSpinBox(StockDialog)
        self.outerSpin.setObjectName(u"outerSpin")
        self.outerSpin.setDecimals(3)
        self.outerSpin.setMinimum(0.010000000000000)
        self.outerSpin.setMaximum(100000.000000000000000)
        self.outerSpin.setValue(50.000000000000000)

        self.formLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.outerSpin)

        self.innerLabel = QLabel(StockDialog)
        self.innerLabel.setObjectName(u"innerLabel")

        self.formLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.innerLabel)

        self.innerSpin = QDoubleSpinBox(StockDialog)
        self.innerSpin.setObjectName(u"innerSpin")
        self.innerSpin.setDecimals(3)
        self.innerSpin.setMaximum(100000.000000000000000)

        self.formLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.innerSpin)

        self.lengthLabel = QLabel(StockDialog)
        self.lengthLabel.setObjectName(u"lengthLabel")

        self.formLayout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.lengthLabel)

        self.lengthSpin = QDoubleSpinBox(StockDialog)
        self.lengthSpin.setObjectName(u"lengthSpin")
        self.lengthSpin.setDecimals(3)
        self.lengthSpin.setMinimum(0.010000000000000)
        self.lengthSpin.setMaximum(100000.000000000000000)
        self.lengthSpin.setValue(100.000000000000000)

        self.formLayout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.lengthSpin)

        self.frontAllowanceLabel = QLabel(StockDialog)
        self.frontAllowanceLabel.setObjectName(u"frontAllowanceLabel")

        self.formLayout.setWidget(3, QFormLayout.ItemRole.LabelRole, self.frontAllowanceLabel)

        self.frontAllowanceSpin = QDoubleSpinBox(StockDialog)
        self.frontAllowanceSpin.setObjectName(u"frontAllowanceSpin")
        self.frontAllowanceSpin.setDecimals(3)
        self.frontAllowanceSpin.setMinimum(-100000.000000000000000)
        self.frontAllowanceSpin.setMaximum(100000.000000000000000)
        self.frontAllowanceSpin.setValue(2.000000000000000)

        self.formLayout.setWidget(3, QFormLayout.ItemRole.FieldRole, self.frontAllowanceSpin)

        self.accuracyLabel = QLabel(StockDialog)
        self.accuracyLabel.setObjectName(u"accuracyLabel")

        self.formLayout.setWidget(4, QFormLayout.ItemRole.LabelRole, self.accuracyLabel)

        self.accuracySlider = QSlider(StockDialog)
        self.accuracySlider.setObjectName(u"accuracySlider")
        self.accuracySlider.setMaximum(4)
        self.accuracySlider.setPageStep(1)
        self.accuracySlider.setValue(2)
        self.accuracySlider.setOrientation(Qt.Orientation.Horizontal)
        self.accuracySlider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.accuracySlider.setTickInterval(1)

        self.formLayout.setWidget(4, QFormLayout.ItemRole.FieldRole, self.accuracySlider)


        self.verticalLayout.addLayout(self.formLayout)

        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.setObjectName(u"buttonLayout")
        self.inchesCheck = QCheckBox(StockDialog)
        self.inchesCheck.setObjectName(u"inchesCheck")

        self.buttonLayout.addWidget(self.inchesCheck)

        self.resetAutoButton = QPushButton(StockDialog)
        self.resetAutoButton.setObjectName(u"resetAutoButton")

        self.buttonLayout.addWidget(self.resetAutoButton)

        self.buttonSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.buttonLayout.addItem(self.buttonSpacer)

        self.buttonBox = QDialogButtonBox(StockDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.buttonLayout.addWidget(self.buttonBox)


        self.verticalLayout.addLayout(self.buttonLayout)


        self.retranslateUi(StockDialog)

        QMetaObject.connectSlotsByName(StockDialog)
    # setupUi

    def retranslateUi(self, StockDialog):
        StockDialog.setWindowTitle(QCoreApplication.translate("StockDialog", u"Stock", None))
        self.enabledCheck.setText(QCoreApplication.translate("StockDialog", u"Run Stock Removal when Play is pressed", None))
        self.outerLabel.setText(QCoreApplication.translate("StockDialog", u"Outside diameter", None))
        self.outerSpin.setSuffix(QCoreApplication.translate("StockDialog", u" mm", None))
        self.innerLabel.setText(QCoreApplication.translate("StockDialog", u"Inside diameter", None))
        self.innerSpin.setSuffix(QCoreApplication.translate("StockDialog", u" mm", None))
        self.lengthLabel.setText(QCoreApplication.translate("StockDialog", u"Length", None))
        self.lengthSpin.setSuffix(QCoreApplication.translate("StockDialog", u" mm", None))
        self.frontAllowanceLabel.setText(QCoreApplication.translate("StockDialog", u"Stock front Z", None))
        self.frontAllowanceSpin.setSuffix(QCoreApplication.translate("StockDialog", u" mm", None))
        self.accuracyLabel.setText(QCoreApplication.translate("StockDialog", u"Accuracy", None))
#if QT_CONFIG(tooltip)
        self.accuracySlider.setToolTip(QCoreApplication.translate("StockDialog", u"Higher accuracy gives a finer stock model and uses more processing time.", None))
#endif // QT_CONFIG(tooltip)
        self.inchesCheck.setText(QCoreApplication.translate("StockDialog", u"Inches", None))
        self.resetAutoButton.setText(QCoreApplication.translate("StockDialog", u"Reset to Auto", None))
    # retranslateUi
