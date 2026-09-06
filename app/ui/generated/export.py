# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'export.ui'
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
    QDialogButtonBox, QGridLayout, QLabel, QLineEdit,
    QSizePolicy, QSpinBox, QVBoxLayout, QWidget)

class Ui_ExportOptDlg(object):
    def setupUi(self, ExportOptDlg):
        if not ExportOptDlg.objectName():
            ExportOptDlg.setObjectName(u"ExportOptDlg")
        ExportOptDlg.resize(380, 380)
        ExportOptDlg.setMinimumSize(QSize(380, 380))
        self.verticalLayout = QVBoxLayout(ExportOptDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, -1, 2, -1)
        self.label_seqStart = QLabel(ExportOptDlg)
        self.label_seqStart.setObjectName(u"label_seqStart")

        self.gridLayout.addWidget(self.label_seqStart, 7, 0, 1, 1)

        self.labelForce = QLabel(ExportOptDlg)
        self.labelForce.setObjectName(u"labelForce")

        self.gridLayout.addWidget(self.labelForce, 1, 0, 1, 1)

        self.startLineEdit = QLineEdit(ExportOptDlg)
        self.startLineEdit.setObjectName(u"startLineEdit")
        self.startLineEdit.setEnabled(True)

        self.gridLayout.addWidget(self.startLineEdit, 3, 1, 1, 1)

        self.safLineCmbBox = QComboBox(ExportOptDlg)
        self.safLineCmbBox.addItem("")
        self.safLineCmbBox.addItem("")
        self.safLineCmbBox.setObjectName(u"safLineCmbBox")

        self.gridLayout.addWidget(self.safLineCmbBox, 5, 1, 1, 1)

        self.label_Lang = QLabel(ExportOptDlg)
        self.label_Lang.setObjectName(u"label_Lang")

        self.gridLayout.addWidget(self.label_Lang, 0, 0, 1, 1)

        self.delimCmbBox = QComboBox(ExportOptDlg)
        self.delimCmbBox.addItem("")
        self.delimCmbBox.addItem("")
        self.delimCmbBox.setObjectName(u"delimCmbBox")

        self.gridLayout.addWidget(self.delimCmbBox, 9, 1, 1, 1)

        self.langCmbBox = QComboBox(ExportOptDlg)
        self.langCmbBox.addItem("")
        self.langCmbBox.addItem("")
        self.langCmbBox.addItem("")
        self.langCmbBox.addItem("")
        self.langCmbBox.addItem("")
        self.langCmbBox.addItem("")
        self.langCmbBox.addItem("")
        self.langCmbBox.setObjectName(u"langCmbBox")

        self.gridLayout.addWidget(self.langCmbBox, 0, 1, 1, 1)

        self.label_seqInterval = QLabel(ExportOptDlg)
        self.label_seqInterval.setObjectName(u"label_seqInterval")

        self.gridLayout.addWidget(self.label_seqInterval, 8, 0, 1, 1)

        self.seqStartSpinBox = QSpinBox(ExportOptDlg)
        self.seqStartSpinBox.setObjectName(u"seqStartSpinBox")
        self.seqStartSpinBox.setMinimum(1)
        self.seqStartSpinBox.setMaximum(99999)

        self.gridLayout.addWidget(self.seqStartSpinBox, 7, 1, 1, 1)

        self.label_Incr = QLabel(ExportOptDlg)
        self.label_Incr.setObjectName(u"label_Incr")

        self.gridLayout.addWidget(self.label_Incr, 2, 0, 1, 1)

        self.label_StartText = QLabel(ExportOptDlg)
        self.label_StartText.setObjectName(u"label_StartText")

        self.gridLayout.addWidget(self.label_StartText, 3, 0, 1, 1)

        self.label_Delim = QLabel(ExportOptDlg)
        self.label_Delim.setObjectName(u"label_Delim")

        self.gridLayout.addWidget(self.label_Delim, 9, 0, 1, 1)

        self.seqNumCmbBox = QComboBox(ExportOptDlg)
        self.seqNumCmbBox.addItem("")
        self.seqNumCmbBox.addItem("")
        self.seqNumCmbBox.setObjectName(u"seqNumCmbBox")

        self.gridLayout.addWidget(self.seqNumCmbBox, 6, 1, 1, 1)

        self.incrCmbBox = QComboBox(ExportOptDlg)
        self.incrCmbBox.addItem("")
        self.incrCmbBox.addItem("")
        self.incrCmbBox.setObjectName(u"incrCmbBox")

        self.gridLayout.addWidget(self.incrCmbBox, 2, 1, 1, 1)

        self.seqIntervalSpinBox = QSpinBox(ExportOptDlg)
        self.seqIntervalSpinBox.setObjectName(u"seqIntervalSpinBox")
        self.seqIntervalSpinBox.setMinimum(1)
        self.seqIntervalSpinBox.setMaximum(99999)

        self.gridLayout.addWidget(self.seqIntervalSpinBox, 8, 1, 1, 1)

        self.forceCmbBox = QComboBox(ExportOptDlg)
        self.forceCmbBox.addItem("")
        self.forceCmbBox.addItem("")
        self.forceCmbBox.setObjectName(u"forceCmbBox")

        self.gridLayout.addWidget(self.forceCmbBox, 1, 1, 1, 1)

        self.label_SafLine = QLabel(ExportOptDlg)
        self.label_SafLine.setObjectName(u"label_SafLine")

        self.gridLayout.addWidget(self.label_SafLine, 5, 0, 1, 1)

        self.label_SeqNum = QLabel(ExportOptDlg)
        self.label_SeqNum.setObjectName(u"label_SeqNum")

        self.gridLayout.addWidget(self.label_SeqNum, 6, 0, 1, 1)

        self.label_EndText = QLabel(ExportOptDlg)
        self.label_EndText.setObjectName(u"label_EndText")

        self.gridLayout.addWidget(self.label_EndText, 4, 0, 1, 1)

        self.endLineEdit = QLineEdit(ExportOptDlg)
        self.endLineEdit.setObjectName(u"endLineEdit")

        self.gridLayout.addWidget(self.endLineEdit, 4, 1, 1, 1)

        self.leadingZeroCmbBox = QComboBox(ExportOptDlg)
        self.leadingZeroCmbBox.addItem("")
        self.leadingZeroCmbBox.addItem("")
        self.leadingZeroCmbBox.setObjectName(u"leadingZeroCmbBox")

        self.gridLayout.addWidget(self.leadingZeroCmbBox, 10, 1, 1, 1)

        self.labelLeadingZero = QLabel(ExportOptDlg)
        self.labelLeadingZero.setObjectName(u"labelLeadingZero")

        self.gridLayout.addWidget(self.labelLeadingZero, 10, 0, 1, 1)


        self.verticalLayout.addLayout(self.gridLayout)

        self.buttonBox = QDialogButtonBox(ExportOptDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout.addWidget(self.buttonBox)

        QWidget.setTabOrder(self.langCmbBox, self.forceCmbBox)
        QWidget.setTabOrder(self.forceCmbBox, self.incrCmbBox)
        QWidget.setTabOrder(self.incrCmbBox, self.startLineEdit)
        QWidget.setTabOrder(self.startLineEdit, self.endLineEdit)
        QWidget.setTabOrder(self.endLineEdit, self.safLineCmbBox)
        QWidget.setTabOrder(self.safLineCmbBox, self.seqNumCmbBox)
        QWidget.setTabOrder(self.seqNumCmbBox, self.seqStartSpinBox)
        QWidget.setTabOrder(self.seqStartSpinBox, self.seqIntervalSpinBox)

        self.retranslateUi(ExportOptDlg)
        self.buttonBox.accepted.connect(ExportOptDlg.accept)
        self.buttonBox.rejected.connect(ExportOptDlg.reject)

        QMetaObject.connectSlotsByName(ExportOptDlg)
    # setupUi

    def retranslateUi(self, ExportOptDlg):
        ExportOptDlg.setWindowTitle(QCoreApplication.translate("ExportOptDlg", u"Export Options", None))
        self.label_seqStart.setText(QCoreApplication.translate("ExportOptDlg", u"Seq. Num. Start", None))
        self.labelForce.setText(QCoreApplication.translate("ExportOptDlg", u"Address Force Output ", None))
        self.safLineCmbBox.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"No", None))
        self.safLineCmbBox.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"Yes", None))

        self.label_Lang.setText(QCoreApplication.translate("ExportOptDlg", u"G-code", None))
        self.delimCmbBox.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"No", None))
        self.delimCmbBox.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"Yes", None))

        self.langCmbBox.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"ISO IJ ARC INCR", None))
        self.langCmbBox.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"ISO IJ ARC ABS", None))
        self.langCmbBox.setItemText(2, QCoreApplication.translate("ExportOptDlg", u"ISO R ARC", None))
        self.langCmbBox.setItemText(3, QCoreApplication.translate("ExportOptDlg", u"ISO NO ARC", None))
        self.langCmbBox.setItemText(4, QCoreApplication.translate("ExportOptDlg", u"PLOT DATA", None))
        self.langCmbBox.setItemText(5, QCoreApplication.translate("ExportOptDlg", u"EXPANDED TURN PROGRAM", None))
        self.langCmbBox.setItemText(6, QCoreApplication.translate("ExportOptDlg", u"EXPANDED MILL PROGRAM", None))

        self.label_seqInterval.setText(QCoreApplication.translate("ExportOptDlg", u"Seq. Num. Interval", None))
        self.label_Incr.setText(QCoreApplication.translate("ExportOptDlg", u"Incremental Mode", None))
        self.label_StartText.setText(QCoreApplication.translate("ExportOptDlg", u"Start Program Text", None))
        self.label_Delim.setText(QCoreApplication.translate("ExportOptDlg", u"Delimeter", None))
        self.seqNumCmbBox.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"No", None))
        self.seqNumCmbBox.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"Yes", None))

        self.incrCmbBox.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"No", None))
        self.incrCmbBox.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"Yes", None))

        self.forceCmbBox.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"No", None))
        self.forceCmbBox.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"Yes", None))

        self.label_SafLine.setText(QCoreApplication.translate("ExportOptDlg", u"Safety Line", None))
        self.label_SeqNum.setText(QCoreApplication.translate("ExportOptDlg", u"Seq. Num.", None))
        self.label_EndText.setText(QCoreApplication.translate("ExportOptDlg", u"End Program Text", None))
        self.leadingZeroCmbBox.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"No", None))
        self.leadingZeroCmbBox.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"Yes", None))

        self.labelLeadingZero.setText(QCoreApplication.translate("ExportOptDlg", u"Leading Zero (G,M,T,H,D)", None))
    # retranslateUi
