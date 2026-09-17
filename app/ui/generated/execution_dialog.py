# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'execution_dialog.ui'
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
from PyQt6.QtWidgets import (QApplication, QDialog, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget)

class Ui_ExecutionDialog(object):
    def setupUi(self, ExecutionDialog):
        if not ExecutionDialog.objectName():
            ExecutionDialog.setObjectName(u"ExecutionDialog")
        self.verticalLayout = QVBoxLayout(ExecutionDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.statusLabel = QLabel(ExecutionDialog)
        self.statusLabel.setObjectName(u"statusLabel")

        self.verticalLayout.addWidget(self.statusLabel)

        self.cancelButton = QPushButton(ExecutionDialog)
        self.cancelButton.setObjectName(u"cancelButton")

        self.verticalLayout.addWidget(self.cancelButton)


        self.retranslateUi(ExecutionDialog)

        QMetaObject.connectSlotsByName(ExecutionDialog)
    # setupUi

    def retranslateUi(self, ExecutionDialog):
        ExecutionDialog.setWindowTitle(QCoreApplication.translate("ExecutionDialog", u"CNC execution", None))
        self.statusLabel.setText(QCoreApplication.translate("ExecutionDialog", u"Executing CNC program\u2026", None))
        self.cancelButton.setText(QCoreApplication.translate("ExecutionDialog", u"Cancel", None))
    # retranslateUi
