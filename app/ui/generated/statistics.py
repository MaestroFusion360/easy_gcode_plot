# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'statistics.ui'
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
    QDialogButtonBox, QHBoxLayout, QPlainTextEdit, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget)

class Ui_StatisticsDialog(object):
    def setupUi(self, StatisticsDialog):
        if not StatisticsDialog.objectName():
            StatisticsDialog.setObjectName(u"StatisticsDialog")
        StatisticsDialog.setMinimumSize(QSize(480, 320))
        self.verticalLayout = QVBoxLayout(StatisticsDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.reportText = QPlainTextEdit(StatisticsDialog)
        self.reportText.setObjectName(u"reportText")
        self.reportText.setReadOnly(True)
        self.reportText.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.reportText.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.verticalLayout.addWidget(self.reportText)

        self.controlsLayout = QHBoxLayout()
        self.controlsLayout.setObjectName(u"controlsLayout")
        self.inchesCheck = QCheckBox(StatisticsDialog)
        self.inchesCheck.setObjectName(u"inchesCheck")

        self.controlsLayout.addWidget(self.inchesCheck)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.controlsLayout.addItem(self.horizontalSpacer)

        self.buttonBox = QDialogButtonBox(StatisticsDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Close)

        self.controlsLayout.addWidget(self.buttonBox)


        self.verticalLayout.addLayout(self.controlsLayout)


        self.retranslateUi(StatisticsDialog)

        QMetaObject.connectSlotsByName(StatisticsDialog)
    # setupUi

    def retranslateUi(self, StatisticsDialog):
        StatisticsDialog.setWindowTitle(QCoreApplication.translate("StatisticsDialog", u"Toolpath Statistics", None))
#if QT_CONFIG(tooltip)
        self.inchesCheck.setToolTip(QCoreApplication.translate("StatisticsDialog", u"Display all lengths and speeds in inches", None))
#endif // QT_CONFIG(tooltip)
        self.inchesCheck.setText(QCoreApplication.translate("StatisticsDialog", u"Inches", None))
    # retranslateUi
