# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'options.ui'
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
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFontComboBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget)

class Ui_OptionsDlg(object):
    def setupUi(self, OptionsDlg):
        if not OptionsDlg.objectName():
            OptionsDlg.setObjectName(u"OptionsDlg")
        OptionsDlg.resize(620, 650)
        self.verticalLayout = QVBoxLayout(OptionsDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.tabs = QTabWidget(OptionsDlg)
        self.tabs.setObjectName(u"tabs")
        self.generalTab = QWidget()
        self.generalTab.setObjectName(u"generalTab")
        self.generalForm = QFormLayout(self.generalTab)
        self.generalForm.setObjectName(u"generalForm")
        self.encodingLabel = QLabel(self.generalTab)
        self.encodingLabel.setObjectName(u"encodingLabel")

        self.generalForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.encodingLabel)

        self.encodingCombo = QComboBox(self.generalTab)
        self.encodingCombo.addItem("")
        self.encodingCombo.addItem("")
        self.encodingCombo.setObjectName(u"encodingCombo")

        self.generalForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.encodingCombo)

        self.fileTypeLabel = QLabel(self.generalTab)
        self.fileTypeLabel.setObjectName(u"fileTypeLabel")

        self.generalForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.fileTypeLabel)

        self.fileTypeCombo = QComboBox(self.generalTab)
        self.fileTypeCombo.addItem("")
        self.fileTypeCombo.addItem("")
        self.fileTypeCombo.setObjectName(u"fileTypeCombo")

        self.generalForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.fileTypeCombo)

        self.unitsLabel = QLabel(self.generalTab)
        self.unitsLabel.setObjectName(u"unitsLabel")

        self.generalForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.unitsLabel)

        self.unitsCombo = QComboBox(self.generalTab)
        self.unitsCombo.addItem("")
        self.unitsCombo.addItem("")
        self.unitsCombo.setObjectName(u"unitsCombo")

        self.generalForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.unitsCombo)

        self.languageLabel = QLabel(self.generalTab)
        self.languageLabel.setObjectName(u"languageLabel")

        self.generalForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.languageLabel)

        self.languageCombo = QComboBox(self.generalTab)
        self.languageCombo.addItem("")
        self.languageCombo.addItem("")
        self.languageCombo.setObjectName(u"languageCombo")
        self.languageCombo.setEnabled(False)

        self.generalForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.languageCombo)

        self.loggingCheck = QCheckBox(self.generalTab)
        self.loggingCheck.setObjectName(u"loggingCheck")

        self.generalForm.setWidget(4, QFormLayout.ItemRole.SpanningRole, self.loggingCheck)

        self.correctionCheck = QCheckBox(self.generalTab)
        self.correctionCheck.setObjectName(u"correctionCheck")

        self.generalForm.setWidget(5, QFormLayout.ItemRole.SpanningRole, self.correctionCheck)

        self.arcToleranceLabel = QLabel(self.generalTab)
        self.arcToleranceLabel.setObjectName(u"arcToleranceLabel")

        self.generalForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.arcToleranceLabel)

        self.arcToleranceSpin = QDoubleSpinBox(self.generalTab)
        self.arcToleranceSpin.setObjectName(u"arcToleranceSpin")
        self.arcToleranceSpin.setDecimals(6)
        self.arcToleranceSpin.setMinimum(0.000001000000000)
        self.arcToleranceSpin.setMaximum(10.000000000000000)
        self.arcToleranceSpin.setValue(0.001000000000000)

        self.generalForm.setWidget(6, QFormLayout.ItemRole.FieldRole, self.arcToleranceSpin)

        self.tabs.addTab(self.generalTab, "")
        self.editorTab = QWidget()
        self.editorTab.setObjectName(u"editorTab")
        self.editorForm = QFormLayout(self.editorTab)
        self.editorForm.setObjectName(u"editorForm")
        self.fontLabel = QLabel(self.editorTab)
        self.fontLabel.setObjectName(u"fontLabel")

        self.editorForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.fontLabel)

        self.fontCombo = QFontComboBox(self.editorTab)
        self.fontCombo.setObjectName(u"fontCombo")

        self.editorForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.fontCombo)

        self.fontSizeLabel = QLabel(self.editorTab)
        self.fontSizeLabel.setObjectName(u"fontSizeLabel")

        self.editorForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.fontSizeLabel)

        self.fontSizeSpin = QSpinBox(self.editorTab)
        self.fontSizeSpin.setObjectName(u"fontSizeSpin")
        self.fontSizeSpin.setMinimum(6)
        self.fontSizeSpin.setMaximum(48)

        self.editorForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.fontSizeSpin)

        self.caretLineCheck = QCheckBox(self.editorTab)
        self.caretLineCheck.setObjectName(u"caretLineCheck")

        self.editorForm.setWidget(2, QFormLayout.ItemRole.SpanningRole, self.caretLineCheck)

        self.eolCheck = QCheckBox(self.editorTab)
        self.eolCheck.setObjectName(u"eolCheck")

        self.editorForm.setWidget(3, QFormLayout.ItemRole.SpanningRole, self.eolCheck)

        self.whitespaceCheck = QCheckBox(self.editorTab)
        self.whitespaceCheck.setObjectName(u"whitespaceCheck")

        self.editorForm.setWidget(4, QFormLayout.ItemRole.SpanningRole, self.whitespaceCheck)

        self.marginCheck = QCheckBox(self.editorTab)
        self.marginCheck.setObjectName(u"marginCheck")

        self.editorForm.setWidget(5, QFormLayout.ItemRole.SpanningRole, self.marginCheck)

        self.tabs.addTab(self.editorTab, "")
        self.plotTab = QWidget()
        self.plotTab.setObjectName(u"plotTab")
        self.plotForm = QFormLayout(self.plotTab)
        self.plotForm.setObjectName(u"plotForm")
        self.rapidLabel = QLabel(self.plotTab)
        self.rapidLabel.setObjectName(u"rapidLabel")

        self.plotForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.rapidLabel)

        self.rapidColorLayout = QHBoxLayout()
        self.rapidColorLayout.setSpacing(6)
        self.rapidColorLayout.setObjectName(u"rapidColorLayout")
        self.rapidColorEdit = QLineEdit(self.plotTab)
        self.rapidColorEdit.setObjectName(u"rapidColorEdit")

        self.rapidColorLayout.addWidget(self.rapidColorEdit)

        self.rapidColorButton = QPushButton(self.plotTab)
        self.rapidColorButton.setObjectName(u"rapidColorButton")
        self.rapidColorButton.setMaximumSize(QSize(72, 16777215))

        self.rapidColorLayout.addWidget(self.rapidColorButton)


        self.plotForm.setLayout(0, QFormLayout.ItemRole.FieldRole, self.rapidColorLayout)

        self.linearLabel = QLabel(self.plotTab)
        self.linearLabel.setObjectName(u"linearLabel")

        self.plotForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.linearLabel)

        self.linearColorLayout = QHBoxLayout()
        self.linearColorLayout.setSpacing(6)
        self.linearColorLayout.setObjectName(u"linearColorLayout")
        self.linearColorEdit = QLineEdit(self.plotTab)
        self.linearColorEdit.setObjectName(u"linearColorEdit")

        self.linearColorLayout.addWidget(self.linearColorEdit)

        self.linearColorButton = QPushButton(self.plotTab)
        self.linearColorButton.setObjectName(u"linearColorButton")
        self.linearColorButton.setMaximumSize(QSize(72, 16777215))

        self.linearColorLayout.addWidget(self.linearColorButton)


        self.plotForm.setLayout(1, QFormLayout.ItemRole.FieldRole, self.linearColorLayout)

        self.arcLabel = QLabel(self.plotTab)
        self.arcLabel.setObjectName(u"arcLabel")

        self.plotForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.arcLabel)

        self.arcColorLayout = QHBoxLayout()
        self.arcColorLayout.setSpacing(6)
        self.arcColorLayout.setObjectName(u"arcColorLayout")
        self.arcColorEdit = QLineEdit(self.plotTab)
        self.arcColorEdit.setObjectName(u"arcColorEdit")

        self.arcColorLayout.addWidget(self.arcColorEdit)

        self.arcColorButton = QPushButton(self.plotTab)
        self.arcColorButton.setObjectName(u"arcColorButton")
        self.arcColorButton.setMaximumSize(QSize(72, 16777215))

        self.arcColorLayout.addWidget(self.arcColorButton)


        self.plotForm.setLayout(2, QFormLayout.ItemRole.FieldRole, self.arcColorLayout)

        self.currentLabel = QLabel(self.plotTab)
        self.currentLabel.setObjectName(u"currentLabel")

        self.plotForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.currentLabel)

        self.currentColorLayout = QHBoxLayout()
        self.currentColorLayout.setSpacing(6)
        self.currentColorLayout.setObjectName(u"currentColorLayout")
        self.currentColorEdit = QLineEdit(self.plotTab)
        self.currentColorEdit.setObjectName(u"currentColorEdit")

        self.currentColorLayout.addWidget(self.currentColorEdit)

        self.currentColorButton = QPushButton(self.plotTab)
        self.currentColorButton.setObjectName(u"currentColorButton")
        self.currentColorButton.setMaximumSize(QSize(72, 16777215))

        self.currentColorLayout.addWidget(self.currentColorButton)


        self.plotForm.setLayout(3, QFormLayout.ItemRole.FieldRole, self.currentColorLayout)

        self.backgroundLabel = QLabel(self.plotTab)
        self.backgroundLabel.setObjectName(u"backgroundLabel")

        self.plotForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.backgroundLabel)

        self.backgroundColorLayout = QHBoxLayout()
        self.backgroundColorLayout.setSpacing(6)
        self.backgroundColorLayout.setObjectName(u"backgroundColorLayout")
        self.backgroundColorEdit = QLineEdit(self.plotTab)
        self.backgroundColorEdit.setObjectName(u"backgroundColorEdit")

        self.backgroundColorLayout.addWidget(self.backgroundColorEdit)

        self.backgroundColorButton = QPushButton(self.plotTab)
        self.backgroundColorButton.setObjectName(u"backgroundColorButton")
        self.backgroundColorButton.setMaximumSize(QSize(72, 16777215))

        self.backgroundColorLayout.addWidget(self.backgroundColorButton)


        self.plotForm.setLayout(4, QFormLayout.ItemRole.FieldRole, self.backgroundColorLayout)

        self.lineWidthLabel = QLabel(self.plotTab)
        self.lineWidthLabel.setObjectName(u"lineWidthLabel")

        self.plotForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.lineWidthLabel)

        self.lineWidthSpin = QDoubleSpinBox(self.plotTab)
        self.lineWidthSpin.setObjectName(u"lineWidthSpin")
        self.lineWidthSpin.setMinimum(0.250000000000000)
        self.lineWidthSpin.setMaximum(6.000000000000000)
        self.lineWidthSpin.setValue(1.500000000000000)

        self.plotForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.lineWidthSpin)

        self.gridStepLabel = QLabel(self.plotTab)
        self.gridStepLabel.setObjectName(u"gridStepLabel")

        self.plotForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.gridStepLabel)

        self.gridStepSpin = QDoubleSpinBox(self.plotTab)
        self.gridStepSpin.setObjectName(u"gridStepSpin")
        self.gridStepSpin.setMaximum(1000000.000000000000000)

        self.plotForm.setWidget(6, QFormLayout.ItemRole.FieldRole, self.gridStepSpin)

        self.axesCheck = QCheckBox(self.plotTab)
        self.axesCheck.setObjectName(u"axesCheck")

        self.plotForm.setWidget(7, QFormLayout.ItemRole.SpanningRole, self.axesCheck)

        self.gridCheck = QCheckBox(self.plotTab)
        self.gridCheck.setObjectName(u"gridCheck")

        self.plotForm.setWidget(8, QFormLayout.ItemRole.SpanningRole, self.gridCheck)

        self.tabs.addTab(self.plotTab, "")

        self.verticalLayout.addWidget(self.tabs)

        self.buttonBox = QDialogButtonBox(OptionsDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.RestoreDefaults)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(OptionsDlg)
        self.buttonBox.accepted.connect(OptionsDlg.accept)
        self.buttonBox.rejected.connect(OptionsDlg.reject)

        QMetaObject.connectSlotsByName(OptionsDlg)
    # setupUi

    def retranslateUi(self, OptionsDlg):
        OptionsDlg.setWindowTitle(QCoreApplication.translate("OptionsDlg", u"Options", None))
        self.encodingLabel.setText(QCoreApplication.translate("OptionsDlg", u"Encoding", None))
        self.encodingCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"UTF-8", None))
        self.encodingCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"Windows-1251", None))

        self.fileTypeLabel.setText(QCoreApplication.translate("OptionsDlg", u"Default file type", None))
        self.fileTypeCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"Text", None))
        self.fileTypeCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"ISO G-code", None))

        self.unitsLabel.setText(QCoreApplication.translate("OptionsDlg", u"Default units", None))
        self.unitsCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"Millimeters", None))
        self.unitsCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"Inches", None))

        self.languageLabel.setText(QCoreApplication.translate("OptionsDlg", u"Language", None))
        self.languageCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"English", None))
        self.languageCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"Russian", None))

#if QT_CONFIG(tooltip)
        self.languageCombo.setToolTip(QCoreApplication.translate("OptionsDlg", u"Language switching is not available yet", None))
#endif // QT_CONFIG(tooltip)
        self.loggingCheck.setText(QCoreApplication.translate("OptionsDlg", u"Enable application log", None))
        self.correctionCheck.setText(QCoreApplication.translate("OptionsDlg", u"Correction (G41/G42) \u2014 On / Off", None))
        self.arcToleranceLabel.setText(QCoreApplication.translate("OptionsDlg", u"Arc tolerance", None))
        self.tabs.setTabText(self.tabs.indexOf(self.generalTab), QCoreApplication.translate("OptionsDlg", u"General", None))
        self.fontLabel.setText(QCoreApplication.translate("OptionsDlg", u"Font family", None))
        self.fontSizeLabel.setText(QCoreApplication.translate("OptionsDlg", u"Font size", None))
        self.caretLineCheck.setText(QCoreApplication.translate("OptionsDlg", u"Highlight current line", None))
        self.eolCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show end-of-line markers", None))
        self.whitespaceCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show whitespace", None))
        self.marginCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show line-number margin", None))
        self.tabs.setTabText(self.tabs.indexOf(self.editorTab), QCoreApplication.translate("OptionsDlg", u"Editor", None))
        self.rapidLabel.setText(QCoreApplication.translate("OptionsDlg", u"Rapid color (G0)", None))
        self.rapidColorButton.setText(QCoreApplication.translate("OptionsDlg", u"Pick...", None))
        self.linearLabel.setText(QCoreApplication.translate("OptionsDlg", u"Linear color (G1)", None))
        self.linearColorButton.setText(QCoreApplication.translate("OptionsDlg", u"Pick...", None))
        self.arcLabel.setText(QCoreApplication.translate("OptionsDlg", u"Arc color (G2/G3)", None))
        self.arcColorButton.setText(QCoreApplication.translate("OptionsDlg", u"Pick...", None))
        self.currentLabel.setText(QCoreApplication.translate("OptionsDlg", u"Current segment color", None))
        self.currentColorButton.setText(QCoreApplication.translate("OptionsDlg", u"Pick...", None))
        self.backgroundLabel.setText(QCoreApplication.translate("OptionsDlg", u"Canvas background", None))
        self.backgroundColorButton.setText(QCoreApplication.translate("OptionsDlg", u"Pick...", None))
        self.lineWidthLabel.setText(QCoreApplication.translate("OptionsDlg", u"Line thickness (0.25\u20136.0)", None))
        self.gridStepLabel.setText(QCoreApplication.translate("OptionsDlg", u"Grid step (0 = adaptive)", None))
        self.axesCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show canvas axes", None))
        self.gridCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show canvas grid", None))
        self.tabs.setTabText(self.tabs.indexOf(self.plotTab), QCoreApplication.translate("OptionsDlg", u"Plot", None))
    # retranslateUi
