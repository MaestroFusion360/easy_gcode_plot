# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'wcs.ui'
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
    QDialogButtonBox, QDoubleSpinBox, QGridLayout, QLabel,
    QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)

class Ui_WcsDlg(object):
    def setupUi(self, WcsDlg):
        if not WcsDlg.objectName():
            WcsDlg.setObjectName(u"WcsDlg")
        WcsDlg.resize(520, 430)
        WcsDlg.setMinimumSize(QSize(520, 430))
        self.verticalLayout = QVBoxLayout(WcsDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.titleLabel = QLabel(WcsDlg)
        self.titleLabel.setObjectName(u"titleLabel")

        self.verticalLayout.addWidget(self.titleLabel)

        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName(u"gridLayout")
        self.nameHeader = QLabel(WcsDlg)
        self.nameHeader.setObjectName(u"nameHeader")

        self.gridLayout.addWidget(self.nameHeader, 0, 0, 1, 1)

        self.xHeader = QLabel(WcsDlg)
        self.xHeader.setObjectName(u"xHeader")

        self.gridLayout.addWidget(self.xHeader, 0, 1, 1, 1)

        self.yHeader = QLabel(WcsDlg)
        self.yHeader.setObjectName(u"yHeader")

        self.gridLayout.addWidget(self.yHeader, 0, 2, 1, 1)

        self.zHeader = QLabel(WcsDlg)
        self.zHeader.setObjectName(u"zHeader")

        self.gridLayout.addWidget(self.zHeader, 0, 3, 1, 1)

        self.g54Label = QLabel(WcsDlg)
        self.g54Label.setObjectName(u"g54Label")

        self.gridLayout.addWidget(self.g54Label, 1, 0, 1, 1)

        self.g54X = QDoubleSpinBox(WcsDlg)
        self.g54X.setObjectName(u"g54X")
        self.g54X.setDecimals(3)
        self.g54X.setMinimum(-999999.998999999952503)
        self.g54X.setMaximum(999999.998999999952503)
        self.g54X.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g54X, 1, 1, 1, 1)

        self.g54Y = QDoubleSpinBox(WcsDlg)
        self.g54Y.setObjectName(u"g54Y")
        self.g54Y.setDecimals(3)
        self.g54Y.setMinimum(-999999.998999999952503)
        self.g54Y.setMaximum(999999.998999999952503)
        self.g54Y.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g54Y, 1, 2, 1, 1)

        self.g54Z = QDoubleSpinBox(WcsDlg)
        self.g54Z.setObjectName(u"g54Z")
        self.g54Z.setDecimals(3)
        self.g54Z.setMinimum(-999999.998999999952503)
        self.g54Z.setMaximum(999999.998999999952503)
        self.g54Z.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g54Z, 1, 3, 1, 1)

        self.g55Label = QLabel(WcsDlg)
        self.g55Label.setObjectName(u"g55Label")

        self.gridLayout.addWidget(self.g55Label, 2, 0, 1, 1)

        self.g55X = QDoubleSpinBox(WcsDlg)
        self.g55X.setObjectName(u"g55X")
        self.g55X.setDecimals(3)
        self.g55X.setMinimum(-999999.998999999952503)
        self.g55X.setMaximum(999999.998999999952503)
        self.g55X.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g55X, 2, 1, 1, 1)

        self.g55Y = QDoubleSpinBox(WcsDlg)
        self.g55Y.setObjectName(u"g55Y")
        self.g55Y.setDecimals(3)
        self.g55Y.setMinimum(-999999.998999999952503)
        self.g55Y.setMaximum(999999.998999999952503)
        self.g55Y.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g55Y, 2, 2, 1, 1)

        self.g55Z = QDoubleSpinBox(WcsDlg)
        self.g55Z.setObjectName(u"g55Z")
        self.g55Z.setDecimals(3)
        self.g55Z.setMinimum(-999999.998999999952503)
        self.g55Z.setMaximum(999999.998999999952503)
        self.g55Z.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g55Z, 2, 3, 1, 1)

        self.g56Label = QLabel(WcsDlg)
        self.g56Label.setObjectName(u"g56Label")

        self.gridLayout.addWidget(self.g56Label, 3, 0, 1, 1)

        self.g56X = QDoubleSpinBox(WcsDlg)
        self.g56X.setObjectName(u"g56X")
        self.g56X.setDecimals(3)
        self.g56X.setMinimum(-999999.998999999952503)
        self.g56X.setMaximum(999999.998999999952503)
        self.g56X.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g56X, 3, 1, 1, 1)

        self.g56Y = QDoubleSpinBox(WcsDlg)
        self.g56Y.setObjectName(u"g56Y")
        self.g56Y.setDecimals(3)
        self.g56Y.setMinimum(-999999.998999999952503)
        self.g56Y.setMaximum(999999.998999999952503)
        self.g56Y.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g56Y, 3, 2, 1, 1)

        self.g56Z = QDoubleSpinBox(WcsDlg)
        self.g56Z.setObjectName(u"g56Z")
        self.g56Z.setDecimals(3)
        self.g56Z.setMinimum(-999999.998999999952503)
        self.g56Z.setMaximum(999999.998999999952503)
        self.g56Z.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g56Z, 3, 3, 1, 1)

        self.g57Label = QLabel(WcsDlg)
        self.g57Label.setObjectName(u"g57Label")

        self.gridLayout.addWidget(self.g57Label, 4, 0, 1, 1)

        self.g57X = QDoubleSpinBox(WcsDlg)
        self.g57X.setObjectName(u"g57X")
        self.g57X.setDecimals(3)
        self.g57X.setMinimum(-999999.998999999952503)
        self.g57X.setMaximum(999999.998999999952503)
        self.g57X.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g57X, 4, 1, 1, 1)

        self.g57Y = QDoubleSpinBox(WcsDlg)
        self.g57Y.setObjectName(u"g57Y")
        self.g57Y.setDecimals(3)
        self.g57Y.setMinimum(-999999.998999999952503)
        self.g57Y.setMaximum(999999.998999999952503)
        self.g57Y.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g57Y, 4, 2, 1, 1)

        self.g57Z = QDoubleSpinBox(WcsDlg)
        self.g57Z.setObjectName(u"g57Z")
        self.g57Z.setDecimals(3)
        self.g57Z.setMinimum(-999999.998999999952503)
        self.g57Z.setMaximum(999999.998999999952503)
        self.g57Z.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g57Z, 4, 3, 1, 1)

        self.g58Label = QLabel(WcsDlg)
        self.g58Label.setObjectName(u"g58Label")

        self.gridLayout.addWidget(self.g58Label, 5, 0, 1, 1)

        self.g58X = QDoubleSpinBox(WcsDlg)
        self.g58X.setObjectName(u"g58X")
        self.g58X.setDecimals(3)
        self.g58X.setMinimum(-999999.998999999952503)
        self.g58X.setMaximum(999999.998999999952503)
        self.g58X.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g58X, 5, 1, 1, 1)

        self.g58Y = QDoubleSpinBox(WcsDlg)
        self.g58Y.setObjectName(u"g58Y")
        self.g58Y.setDecimals(3)
        self.g58Y.setMinimum(-999999.998999999952503)
        self.g58Y.setMaximum(999999.998999999952503)
        self.g58Y.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g58Y, 5, 2, 1, 1)

        self.g58Z = QDoubleSpinBox(WcsDlg)
        self.g58Z.setObjectName(u"g58Z")
        self.g58Z.setDecimals(3)
        self.g58Z.setMinimum(-999999.998999999952503)
        self.g58Z.setMaximum(999999.998999999952503)
        self.g58Z.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g58Z, 5, 3, 1, 1)

        self.g59Label = QLabel(WcsDlg)
        self.g59Label.setObjectName(u"g59Label")

        self.gridLayout.addWidget(self.g59Label, 6, 0, 1, 1)

        self.g59X = QDoubleSpinBox(WcsDlg)
        self.g59X.setObjectName(u"g59X")
        self.g59X.setDecimals(3)
        self.g59X.setMinimum(-999999.998999999952503)
        self.g59X.setMaximum(999999.998999999952503)
        self.g59X.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g59X, 6, 1, 1, 1)

        self.g59Y = QDoubleSpinBox(WcsDlg)
        self.g59Y.setObjectName(u"g59Y")
        self.g59Y.setDecimals(3)
        self.g59Y.setMinimum(-999999.998999999952503)
        self.g59Y.setMaximum(999999.998999999952503)
        self.g59Y.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g59Y, 6, 2, 1, 1)

        self.g59Z = QDoubleSpinBox(WcsDlg)
        self.g59Z.setObjectName(u"g59Z")
        self.g59Z.setDecimals(3)
        self.g59Z.setMinimum(-999999.998999999952503)
        self.g59Z.setMaximum(999999.998999999952503)
        self.g59Z.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.g59Z, 6, 3, 1, 1)

        self.homeLabel = QLabel(WcsDlg)
        self.homeLabel.setObjectName(u"homeLabel")

        self.gridLayout.addWidget(self.homeLabel, 7, 0, 1, 1)

        self.homeX = QDoubleSpinBox(WcsDlg)
        self.homeX.setObjectName(u"homeX")
        self.homeX.setDecimals(3)
        self.homeX.setMinimum(-999999.998999999952503)
        self.homeX.setMaximum(999999.998999999952503)
        self.homeX.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.homeX, 7, 1, 1, 1)

        self.homeY = QDoubleSpinBox(WcsDlg)
        self.homeY.setObjectName(u"homeY")
        self.homeY.setDecimals(3)
        self.homeY.setMinimum(-999999.998999999952503)
        self.homeY.setMaximum(999999.998999999952503)
        self.homeY.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.homeY, 7, 2, 1, 1)

        self.homeZ = QDoubleSpinBox(WcsDlg)
        self.homeZ.setObjectName(u"homeZ")
        self.homeZ.setDecimals(3)
        self.homeZ.setMinimum(-999999.998999999952503)
        self.homeZ.setMaximum(999999.998999999952503)
        self.homeZ.setSingleStep(0.001000000000000)

        self.gridLayout.addWidget(self.homeZ, 7, 3, 1, 1)


        self.verticalLayout.addLayout(self.gridLayout)

        self.homeConfiguredCheck = QCheckBox(WcsDlg)
        self.homeConfiguredCheck.setObjectName(u"homeConfiguredCheck")

        self.verticalLayout.addWidget(self.homeConfiguredCheck)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)

        self.buttonBox = QDialogButtonBox(WcsDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(WcsDlg)
        self.buttonBox.accepted.connect(WcsDlg.accept)
        self.buttonBox.rejected.connect(WcsDlg.reject)

        QMetaObject.connectSlotsByName(WcsDlg)
    # setupUi

    def retranslateUi(self, WcsDlg):
        WcsDlg.setWindowTitle(QCoreApplication.translate("WcsDlg", u"WCS", None))
        self.titleLabel.setText(QCoreApplication.translate("WcsDlg", u"Coordinate Offsets", None))
        self.nameHeader.setText(QCoreApplication.translate("WcsDlg", u"Name", None))
        self.xHeader.setText(QCoreApplication.translate("WcsDlg", u"X", None))
        self.yHeader.setText(QCoreApplication.translate("WcsDlg", u"Y", None))
        self.zHeader.setText(QCoreApplication.translate("WcsDlg", u"Z", None))
        self.g54Label.setText(QCoreApplication.translate("WcsDlg", u"G54", None))
        self.g55Label.setText(QCoreApplication.translate("WcsDlg", u"G55", None))
        self.g56Label.setText(QCoreApplication.translate("WcsDlg", u"G56", None))
        self.g57Label.setText(QCoreApplication.translate("WcsDlg", u"G57", None))
        self.g58Label.setText(QCoreApplication.translate("WcsDlg", u"G58", None))
        self.g59Label.setText(QCoreApplication.translate("WcsDlg", u"G59", None))
        self.homeLabel.setText(QCoreApplication.translate("WcsDlg", u"Home (G28)", None))
        self.homeConfiguredCheck.setText(QCoreApplication.translate("WcsDlg", u"Use configured G28 home for machine-space rapid checks", None))
    # retranslateUi
