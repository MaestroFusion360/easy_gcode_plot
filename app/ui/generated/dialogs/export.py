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
    QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QSizePolicy, QSpacerItem,
    QSpinBox, QVBoxLayout, QWidget)

class Ui_ExportOptDlg(object):
    def setupUi(self, ExportOptDlg):
        if not ExportOptDlg.objectName():
            ExportOptDlg.setObjectName(u"ExportOptDlg")
        ExportOptDlg.resize(660, 470)
        ExportOptDlg.setMinimumSize(QSize(620, 430))
        self.verticalLayout = QVBoxLayout(ExportOptDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.columnsLayout = QHBoxLayout()
        self.columnsLayout.setObjectName(u"columnsLayout")
        self.leftColumn = QVBoxLayout()
        self.leftColumn.setObjectName(u"leftColumn")
        self.gridLeftMode = QGridLayout()
        self.gridLeftMode.setObjectName(u"gridLeftMode")
        self.gridLeftMode.setContentsMargins(2, -1, 2, -1)
        self.label_Lang = QLabel(ExportOptDlg)
        self.label_Lang.setObjectName(u"label_Lang")

        self.gridLeftMode.addWidget(self.label_Lang, 0, 0, 1, 1)

        self.langCmbBox = QComboBox(ExportOptDlg)
        self.langCmbBox.setObjectName(u"langCmbBox")

        self.gridLeftMode.addWidget(self.langCmbBox, 0, 1, 1, 1)

        self.label_TargetCnc = QLabel(ExportOptDlg)
        self.label_TargetCnc.setObjectName(u"label_TargetCnc")

        self.gridLeftMode.addWidget(self.label_TargetCnc, 1, 0, 1, 1)

        self.targetCncCombo = QComboBox(ExportOptDlg)
        self.targetCncCombo.setObjectName(u"targetCncCombo")

        self.gridLeftMode.addWidget(self.targetCncCombo, 1, 1, 1, 1)

        self.arcOutputLabel = QLabel(ExportOptDlg)
        self.arcOutputLabel.setObjectName(u"arcOutputLabel")

        self.gridLeftMode.addWidget(self.arcOutputLabel, 2, 0, 1, 1)

        self.arcOutputCmbBox = QComboBox(ExportOptDlg)
        self.arcOutputCmbBox.addItem("")
        self.arcOutputCmbBox.addItem("")
        self.arcOutputCmbBox.addItem("")
        self.arcOutputCmbBox.addItem("")
        self.arcOutputCmbBox.setObjectName(u"arcOutputCmbBox")

        self.gridLeftMode.addWidget(self.arcOutputCmbBox, 2, 1, 1, 1)


        self.leftColumn.addLayout(self.gridLeftMode)

        self.leftSeparator = QFrame(ExportOptDlg)
        self.leftSeparator.setObjectName(u"leftSeparator")
        self.leftSeparator.setFrameShape(QFrame.Shape.HLine)
        self.leftSeparator.setFrameShadow(QFrame.Shadow.Sunken)

        self.leftColumn.addWidget(self.leftSeparator)

        self.gridLeftOutput = QGridLayout()
        self.gridLeftOutput.setObjectName(u"gridLeftOutput")
        self.gridLeftOutput.setContentsMargins(2, -1, 2, -1)
        self.modalFeedLabel = QLabel(ExportOptDlg)
        self.modalFeedLabel.setObjectName(u"modalFeedLabel")

        self.gridLeftOutput.addWidget(self.modalFeedLabel, 0, 0, 1, 1)

        self.modalFeedCombo = QComboBox(ExportOptDlg)
        self.modalFeedCombo.addItem("")
        self.modalFeedCombo.addItem("")
        self.modalFeedCombo.setObjectName(u"modalFeedCombo")

        self.gridLeftOutput.addWidget(self.modalFeedCombo, 0, 1, 1, 1)

        self.decimalPlacesLabel = QLabel(ExportOptDlg)
        self.decimalPlacesLabel.setObjectName(u"decimalPlacesLabel")

        self.gridLeftOutput.addWidget(self.decimalPlacesLabel, 1, 0, 1, 1)

        self.decimalPlacesSpin = QSpinBox(ExportOptDlg)
        self.decimalPlacesSpin.setObjectName(u"decimalPlacesSpin")
        self.decimalPlacesSpin.setMaximum(12)

        self.gridLeftOutput.addWidget(self.decimalPlacesSpin, 1, 1, 1, 1)

        self.forceDecimalLabel = QLabel(ExportOptDlg)
        self.forceDecimalLabel.setObjectName(u"forceDecimalLabel")

        self.gridLeftOutput.addWidget(self.forceDecimalLabel, 2, 0, 1, 1)

        self.forceDecimalCombo = QComboBox(ExportOptDlg)
        self.forceDecimalCombo.addItem("")
        self.forceDecimalCombo.addItem("")
        self.forceDecimalCombo.setObjectName(u"forceDecimalCombo")

        self.gridLeftOutput.addWidget(self.forceDecimalCombo, 2, 1, 1, 1)

        self.plusSignLabel = QLabel(ExportOptDlg)
        self.plusSignLabel.setObjectName(u"plusSignLabel")

        self.gridLeftOutput.addWidget(self.plusSignLabel, 3, 0, 1, 1)

        self.plusSignCombo = QComboBox(ExportOptDlg)
        self.plusSignCombo.addItem("")
        self.plusSignCombo.addItem("")
        self.plusSignCombo.setObjectName(u"plusSignCombo")

        self.gridLeftOutput.addWidget(self.plusSignCombo, 3, 1, 1, 1)


        self.leftColumn.addLayout(self.gridLeftOutput)

        self.leftSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.leftColumn.addItem(self.leftSpacer)


        self.columnsLayout.addLayout(self.leftColumn)

        self.columnSeparator = QFrame(ExportOptDlg)
        self.columnSeparator.setObjectName(u"columnSeparator")
        self.columnSeparator.setFrameShape(QFrame.Shape.VLine)
        self.columnSeparator.setFrameShadow(QFrame.Shadow.Sunken)

        self.columnsLayout.addWidget(self.columnSeparator)

        self.rightColumn = QVBoxLayout()
        self.rightColumn.setObjectName(u"rightColumn")
        self.gridRightProgram = QGridLayout()
        self.gridRightProgram.setObjectName(u"gridRightProgram")
        self.gridRightProgram.setContentsMargins(2, -1, 2, -1)
        self.label_StartText = QLabel(ExportOptDlg)
        self.label_StartText.setObjectName(u"label_StartText")

        self.gridRightProgram.addWidget(self.label_StartText, 0, 0, 1, 1)

        self.startLineEdit = QLineEdit(ExportOptDlg)
        self.startLineEdit.setObjectName(u"startLineEdit")

        self.gridRightProgram.addWidget(self.startLineEdit, 0, 1, 1, 1)

        self.label_EndText = QLabel(ExportOptDlg)
        self.label_EndText.setObjectName(u"label_EndText")

        self.gridRightProgram.addWidget(self.label_EndText, 1, 0, 1, 1)

        self.endLineEdit = QLineEdit(ExportOptDlg)
        self.endLineEdit.setObjectName(u"endLineEdit")

        self.gridRightProgram.addWidget(self.endLineEdit, 1, 1, 1, 1)

        self.label_SafLine = QLabel(ExportOptDlg)
        self.label_SafLine.setObjectName(u"label_SafLine")

        self.gridRightProgram.addWidget(self.label_SafLine, 2, 0, 1, 1)

        self.safLineCmbBox = QComboBox(ExportOptDlg)
        self.safLineCmbBox.addItem("")
        self.safLineCmbBox.addItem("")
        self.safLineCmbBox.setObjectName(u"safLineCmbBox")

        self.gridRightProgram.addWidget(self.safLineCmbBox, 2, 1, 1, 1)


        self.rightColumn.addLayout(self.gridRightProgram)

        self.rightSeparator = QFrame(ExportOptDlg)
        self.rightSeparator.setObjectName(u"rightSeparator")
        self.rightSeparator.setFrameShape(QFrame.Shape.HLine)
        self.rightSeparator.setFrameShadow(QFrame.Shadow.Sunken)

        self.rightColumn.addWidget(self.rightSeparator)

        self.gridRightFormat = QGridLayout()
        self.gridRightFormat.setObjectName(u"gridRightFormat")
        self.gridRightFormat.setContentsMargins(2, -1, 2, -1)
        self.label_Incr = QLabel(ExportOptDlg)
        self.label_Incr.setObjectName(u"label_Incr")

        self.gridRightFormat.addWidget(self.label_Incr, 0, 0, 1, 1)

        self.incrCmbBox = QComboBox(ExportOptDlg)
        self.incrCmbBox.addItem("")
        self.incrCmbBox.addItem("")
        self.incrCmbBox.setObjectName(u"incrCmbBox")

        self.gridRightFormat.addWidget(self.incrCmbBox, 0, 1, 1, 1)

        self.label_SeqNum = QLabel(ExportOptDlg)
        self.label_SeqNum.setObjectName(u"label_SeqNum")

        self.gridRightFormat.addWidget(self.label_SeqNum, 1, 0, 1, 1)

        self.seqNumCmbBox = QComboBox(ExportOptDlg)
        self.seqNumCmbBox.addItem("")
        self.seqNumCmbBox.addItem("")
        self.seqNumCmbBox.setObjectName(u"seqNumCmbBox")

        self.gridRightFormat.addWidget(self.seqNumCmbBox, 1, 1, 1, 1)

        self.label_seqStart = QLabel(ExportOptDlg)
        self.label_seqStart.setObjectName(u"label_seqStart")

        self.gridRightFormat.addWidget(self.label_seqStart, 2, 0, 1, 1)

        self.seqStartSpinBox = QSpinBox(ExportOptDlg)
        self.seqStartSpinBox.setObjectName(u"seqStartSpinBox")
        self.seqStartSpinBox.setMinimum(1)
        self.seqStartSpinBox.setMaximum(99999)

        self.gridRightFormat.addWidget(self.seqStartSpinBox, 2, 1, 1, 1)

        self.label_seqInterval = QLabel(ExportOptDlg)
        self.label_seqInterval.setObjectName(u"label_seqInterval")

        self.gridRightFormat.addWidget(self.label_seqInterval, 3, 0, 1, 1)

        self.seqIntervalSpinBox = QSpinBox(ExportOptDlg)
        self.seqIntervalSpinBox.setObjectName(u"seqIntervalSpinBox")
        self.seqIntervalSpinBox.setMinimum(1)
        self.seqIntervalSpinBox.setMaximum(99999)

        self.gridRightFormat.addWidget(self.seqIntervalSpinBox, 3, 1, 1, 1)

        self.label_Delim = QLabel(ExportOptDlg)
        self.label_Delim.setObjectName(u"label_Delim")

        self.gridRightFormat.addWidget(self.label_Delim, 4, 0, 1, 1)

        self.delimCmbBox = QComboBox(ExportOptDlg)
        self.delimCmbBox.addItem("")
        self.delimCmbBox.addItem("")
        self.delimCmbBox.setObjectName(u"delimCmbBox")

        self.gridRightFormat.addWidget(self.delimCmbBox, 4, 1, 1, 1)

        self.labelLeadingZero = QLabel(ExportOptDlg)
        self.labelLeadingZero.setObjectName(u"labelLeadingZero")

        self.gridRightFormat.addWidget(self.labelLeadingZero, 5, 0, 1, 1)

        self.leadingZeroCmbBox = QComboBox(ExportOptDlg)
        self.leadingZeroCmbBox.addItem("")
        self.leadingZeroCmbBox.addItem("")
        self.leadingZeroCmbBox.setObjectName(u"leadingZeroCmbBox")

        self.gridRightFormat.addWidget(self.leadingZeroCmbBox, 5, 1, 1, 1)


        self.rightColumn.addLayout(self.gridRightFormat)

        self.rightSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.rightColumn.addItem(self.rightSpacer)


        self.columnsLayout.addLayout(self.rightColumn)


        self.verticalLayout.addLayout(self.columnsLayout)

        self.buttonBox = QDialogButtonBox(ExportOptDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout.addWidget(self.buttonBox)

        QWidget.setTabOrder(self.langCmbBox, self.targetCncCombo)
        QWidget.setTabOrder(self.targetCncCombo, self.arcOutputCmbBox)
        QWidget.setTabOrder(self.arcOutputCmbBox, self.modalFeedCombo)
        QWidget.setTabOrder(self.modalFeedCombo, self.decimalPlacesSpin)
        QWidget.setTabOrder(self.decimalPlacesSpin, self.forceDecimalCombo)
        QWidget.setTabOrder(self.forceDecimalCombo, self.plusSignCombo)
        QWidget.setTabOrder(self.plusSignCombo, self.startLineEdit)
        QWidget.setTabOrder(self.startLineEdit, self.endLineEdit)
        QWidget.setTabOrder(self.endLineEdit, self.safLineCmbBox)
        QWidget.setTabOrder(self.safLineCmbBox, self.incrCmbBox)
        QWidget.setTabOrder(self.incrCmbBox, self.seqNumCmbBox)
        QWidget.setTabOrder(self.seqNumCmbBox, self.seqStartSpinBox)
        QWidget.setTabOrder(self.seqStartSpinBox, self.seqIntervalSpinBox)
        QWidget.setTabOrder(self.seqIntervalSpinBox, self.delimCmbBox)
        QWidget.setTabOrder(self.delimCmbBox, self.leadingZeroCmbBox)

        self.retranslateUi(ExportOptDlg)
        self.buttonBox.accepted.connect(ExportOptDlg.accept)
        self.buttonBox.rejected.connect(ExportOptDlg.reject)

        QMetaObject.connectSlotsByName(ExportOptDlg)
    # setupUi

    def retranslateUi(self, ExportOptDlg):
        ExportOptDlg.setWindowTitle(QCoreApplication.translate("ExportOptDlg", u"Export Options", None))
        self.label_Lang.setText(QCoreApplication.translate("ExportOptDlg", u"Export Type", None))
        self.label_TargetCnc.setText(QCoreApplication.translate("ExportOptDlg", u"Target CNC", None))
        self.arcOutputLabel.setText(QCoreApplication.translate("ExportOptDlg", u"Arc Output", None))
        self.arcOutputCmbBox.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"IJK RELATIVE", None))
        self.arcOutputCmbBox.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"IJK ABSOLUTE", None))
        self.arcOutputCmbBox.setItemText(2, QCoreApplication.translate("ExportOptDlg", u"R RADIUS", None))
        self.arcOutputCmbBox.setItemText(3, QCoreApplication.translate("ExportOptDlg", u"LINEARIZED", None))

        self.modalFeedLabel.setText(QCoreApplication.translate("ExportOptDlg", u"Modal Feed", None))
        self.modalFeedCombo.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"No", None))
        self.modalFeedCombo.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"Yes", None))

        self.decimalPlacesLabel.setText(QCoreApplication.translate("ExportOptDlg", u"Decimal Places", None))
        self.forceDecimalLabel.setText(QCoreApplication.translate("ExportOptDlg", u"Force Decimal", None))
        self.forceDecimalCombo.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"No", None))
        self.forceDecimalCombo.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"Yes", None))

        self.plusSignLabel.setText(QCoreApplication.translate("ExportOptDlg", u"Plus Sign", None))
        self.plusSignCombo.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"No", None))
        self.plusSignCombo.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"Yes", None))

        self.label_StartText.setText(QCoreApplication.translate("ExportOptDlg", u"Start Program Text", None))
        self.label_EndText.setText(QCoreApplication.translate("ExportOptDlg", u"End Program Text", None))
        self.label_SafLine.setText(QCoreApplication.translate("ExportOptDlg", u"Safety Line", None))
        self.safLineCmbBox.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"No", None))
        self.safLineCmbBox.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"Yes", None))

        self.label_Incr.setText(QCoreApplication.translate("ExportOptDlg", u"Coordinates", None))
        self.incrCmbBox.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"G90 Absolute", None))
        self.incrCmbBox.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"G91 Incremental", None))

        self.label_SeqNum.setText(QCoreApplication.translate("ExportOptDlg", u"Seq. Num.", None))
        self.seqNumCmbBox.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"No", None))
        self.seqNumCmbBox.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"Yes", None))

        self.label_seqStart.setText(QCoreApplication.translate("ExportOptDlg", u"Seq. Num. Start", None))
        self.label_seqInterval.setText(QCoreApplication.translate("ExportOptDlg", u"Seq. Num. Interval", None))
        self.label_Delim.setText(QCoreApplication.translate("ExportOptDlg", u"Delimeter", None))
        self.delimCmbBox.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"No", None))
        self.delimCmbBox.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"Yes", None))

        self.labelLeadingZero.setText(QCoreApplication.translate("ExportOptDlg", u"Leading Zero (G,M,T,H,D)", None))
        self.leadingZeroCmbBox.setItemText(0, QCoreApplication.translate("ExportOptDlg", u"No", None))
        self.leadingZeroCmbBox.setItemText(1, QCoreApplication.translate("ExportOptDlg", u"Yes", None))

    # retranslateUi
