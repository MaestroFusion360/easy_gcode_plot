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
from PyQt6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QCheckBox,
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFontComboBox, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton,
    QSizePolicy, QSlider, QSpacerItem, QSpinBox,
    QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)

import app.resources.files_res  # noqa: F401  # Registers Qt resources on import.

class Ui_OptionsDlg(object):
    def setupUi(self, OptionsDlg):
        if not OptionsDlg.objectName():
            OptionsDlg.setObjectName(u"OptionsDlg")
        OptionsDlg.resize(1060, 720)
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

        self.generalForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.languageCombo)

        self.themeLabel = QLabel(self.generalTab)
        self.themeLabel.setObjectName(u"themeLabel")

        self.generalForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.themeLabel)

        self.themeCombo = QComboBox(self.generalTab)
        self.themeCombo.addItem("")
        self.themeCombo.addItem("")
        self.themeCombo.setObjectName(u"themeCombo")

        self.generalForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.themeCombo)

        self.toolpanelIconsLabel = QLabel(self.generalTab)
        self.toolpanelIconsLabel.setObjectName(u"toolpanelIconsLabel")

        self.generalForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.toolpanelIconsLabel)

        self.toolpanelIconsCombo = QComboBox(self.generalTab)
        self.toolpanelIconsCombo.addItem("")
        self.toolpanelIconsCombo.addItem("")
        self.toolpanelIconsCombo.addItem("")
        self.toolpanelIconsCombo.setObjectName(u"toolpanelIconsCombo")

        self.generalForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.toolpanelIconsCombo)

        self.autoUpdateMaxSegmentsLabel = QLabel(self.generalTab)
        self.autoUpdateMaxSegmentsLabel.setObjectName(u"autoUpdateMaxSegmentsLabel")

        self.generalForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.autoUpdateMaxSegmentsLabel)

        self.autoUpdateMaxSegmentsSpin = QSpinBox(self.generalTab)
        self.autoUpdateMaxSegmentsSpin.setObjectName(u"autoUpdateMaxSegmentsSpin")
        self.autoUpdateMaxSegmentsSpin.setMinimum(1000)
        self.autoUpdateMaxSegmentsSpin.setMaximum(2147483647)
        self.autoUpdateMaxSegmentsSpin.setSingleStep(5000)
        self.autoUpdateMaxSegmentsSpin.setValue(2147483647)

        self.generalForm.setWidget(6, QFormLayout.ItemRole.FieldRole, self.autoUpdateMaxSegmentsSpin)

        self.maxGeneratedMotionsLabel = QLabel(self.generalTab)
        self.maxGeneratedMotionsLabel.setObjectName(u"maxGeneratedMotionsLabel")

        self.generalForm.setWidget(7, QFormLayout.ItemRole.LabelRole, self.maxGeneratedMotionsLabel)

        self.maxGeneratedMotionsSpin = QSpinBox(self.generalTab)
        self.maxGeneratedMotionsSpin.setObjectName(u"maxGeneratedMotionsSpin")
        self.maxGeneratedMotionsSpin.setMinimum(1)
        self.maxGeneratedMotionsSpin.setMaximum(2147483647)
        self.maxGeneratedMotionsSpin.setSingleStep(50000)
        self.maxGeneratedMotionsSpin.setValue(2147483647)

        self.generalForm.setWidget(7, QFormLayout.ItemRole.FieldRole, self.maxGeneratedMotionsSpin)

        self.autoUpdateCheck = QCheckBox(self.generalTab)
        self.autoUpdateCheck.setObjectName(u"autoUpdateCheck")

        self.generalForm.setWidget(8, QFormLayout.ItemRole.SpanningRole, self.autoUpdateCheck)

        self.loggingCheck = QCheckBox(self.generalTab)
        self.loggingCheck.setObjectName(u"loggingCheck")

        self.generalForm.setWidget(9, QFormLayout.ItemRole.SpanningRole, self.loggingCheck)

        self.cimcoLikePickingCheck = QCheckBox(self.generalTab)
        self.cimcoLikePickingCheck.setObjectName(u"cimcoLikePickingCheck")

        self.generalForm.setWidget(10, QFormLayout.ItemRole.SpanningRole, self.cimcoLikePickingCheck)

        self.tabs.addTab(self.generalTab, "")
        self.cncTab = QWidget()
        self.cncTab.setObjectName(u"cncTab")
        self.cncForm = QFormLayout(self.cncTab)
        self.cncForm.setObjectName(u"cncForm")
        self.correctionCheck = QCheckBox(self.cncTab)
        self.correctionCheck.setObjectName(u"correctionCheck")

        self.cncForm.setWidget(0, QFormLayout.ItemRole.SpanningRole, self.correctionCheck)

        self.autodetectArcTypeCheck = QCheckBox(self.cncTab)
        self.autodetectArcTypeCheck.setObjectName(u"autodetectArcTypeCheck")
        self.autodetectArcTypeCheck.setChecked(True)

        self.cncForm.setWidget(1, QFormLayout.ItemRole.SpanningRole, self.autodetectArcTypeCheck)

        self.ignoreBlockSkipCheck = QCheckBox(self.cncTab)
        self.ignoreBlockSkipCheck.setObjectName(u"ignoreBlockSkipCheck")

        self.cncForm.setWidget(2, QFormLayout.ItemRole.SpanningRole, self.ignoreBlockSkipCheck)

        self.arcSamplingPresetLabel = QLabel(self.cncTab)
        self.arcSamplingPresetLabel.setObjectName(u"arcSamplingPresetLabel")

        self.cncForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.arcSamplingPresetLabel)

        self.arcSamplingPresetCombo = QComboBox(self.cncTab)
        self.arcSamplingPresetCombo.addItem("")
        self.arcSamplingPresetCombo.addItem("")
        self.arcSamplingPresetCombo.addItem("")
        self.arcSamplingPresetCombo.addItem("")
        self.arcSamplingPresetCombo.setObjectName(u"arcSamplingPresetCombo")

        self.cncForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.arcSamplingPresetCombo)

        self.arcToleranceLabel = QLabel(self.cncTab)
        self.arcToleranceLabel.setObjectName(u"arcToleranceLabel")

        self.cncForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.arcToleranceLabel)

        self.arcToleranceSpin = QDoubleSpinBox(self.cncTab)
        self.arcToleranceSpin.setObjectName(u"arcToleranceSpin")
        self.arcToleranceSpin.setDecimals(6)
        self.arcToleranceSpin.setMinimum(0.000001000000000)
        self.arcToleranceSpin.setMaximum(10.000000000000000)
        self.arcToleranceSpin.setSingleStep(0.001000000000000)
        self.arcToleranceSpin.setValue(0.002000000000000)

        self.cncForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.arcToleranceSpin)

        self.maximumCircularRadiusLabel = QLabel(self.cncTab)
        self.maximumCircularRadiusLabel.setObjectName(u"maximumCircularRadiusLabel")

        self.cncForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.maximumCircularRadiusLabel)

        self.maximumCircularRadiusSpin = QDoubleSpinBox(self.cncTab)
        self.maximumCircularRadiusSpin.setObjectName(u"maximumCircularRadiusSpin")
        self.maximumCircularRadiusSpin.setDecimals(3)
        self.maximumCircularRadiusSpin.setMinimum(0.001000000000000)
        self.maximumCircularRadiusSpin.setMaximum(1000000000.000000000000000)
        self.maximumCircularRadiusSpin.setValue(1000.000000000000000)

        self.cncForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.maximumCircularRadiusSpin)

        self.minimumCircularRadiusLabel = QLabel(self.cncTab)
        self.minimumCircularRadiusLabel.setObjectName(u"minimumCircularRadiusLabel")

        self.cncForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.minimumCircularRadiusLabel)

        self.minimumCircularRadiusSpin = QDoubleSpinBox(self.cncTab)
        self.minimumCircularRadiusSpin.setObjectName(u"minimumCircularRadiusSpin")
        self.minimumCircularRadiusSpin.setDecimals(3)
        self.minimumCircularRadiusSpin.setMaximum(1000000000.000000000000000)
        self.minimumCircularRadiusSpin.setValue(0.010000000000000)

        self.cncForm.setWidget(6, QFormLayout.ItemRole.FieldRole, self.minimumCircularRadiusSpin)

        self.minimumChordLengthLabel = QLabel(self.cncTab)
        self.minimumChordLengthLabel.setObjectName(u"minimumChordLengthLabel")

        self.cncForm.setWidget(7, QFormLayout.ItemRole.LabelRole, self.minimumChordLengthLabel)

        self.minimumChordLengthSpin = QDoubleSpinBox(self.cncTab)
        self.minimumChordLengthSpin.setObjectName(u"minimumChordLengthSpin")
        self.minimumChordLengthSpin.setDecimals(3)
        self.minimumChordLengthSpin.setMaximum(1000000.000000000000000)
        self.minimumChordLengthSpin.setValue(0.250000000000000)

        self.cncForm.setWidget(7, QFormLayout.ItemRole.FieldRole, self.minimumChordLengthSpin)

        self.commentStyleLabel = QLabel(self.cncTab)
        self.commentStyleLabel.setObjectName(u"commentStyleLabel")

        self.cncForm.setWidget(8, QFormLayout.ItemRole.LabelRole, self.commentStyleLabel)

        self.commentStyleCombo = QComboBox(self.cncTab)
        self.commentStyleCombo.addItem("")
        self.commentStyleCombo.addItem("")
        self.commentStyleCombo.setObjectName(u"commentStyleCombo")

        self.cncForm.setWidget(8, QFormLayout.ItemRole.FieldRole, self.commentStyleCombo)

        self.tabs.addTab(self.cncTab, "")
        self.colorsTab = QWidget()
        self.colorsTab.setObjectName(u"colorsTab")
        self.colorsLayout = QVBoxLayout(self.colorsTab)
        self.colorsLayout.setObjectName(u"colorsLayout")
        self.editorColorsGroup = QGroupBox(self.colorsTab)
        self.editorColorsGroup.setObjectName(u"editorColorsGroup")
        self.editorColorsForm = QFormLayout(self.editorColorsGroup)
        self.editorColorsForm.setObjectName(u"editorColorsForm")

        self.colorsLayout.addWidget(self.editorColorsGroup)

        self.plotColorsGroup = QGroupBox(self.colorsTab)
        self.plotColorsGroup.setObjectName(u"plotColorsGroup")
        self.colorsForm = QFormLayout(self.plotColorsGroup)
        self.colorsForm.setObjectName(u"colorsForm")
        self.rapidLabel = QLabel(self.plotColorsGroup)
        self.rapidLabel.setObjectName(u"rapidLabel")

        self.colorsForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.rapidLabel)

        self.rapidColorLayout = QHBoxLayout()
        self.rapidColorLayout.setObjectName(u"rapidColorLayout")
        self.rapidColorButton = QPushButton(self.plotColorsGroup)
        self.rapidColorButton.setObjectName(u"rapidColorButton")

        self.rapidColorLayout.addWidget(self.rapidColorButton)

        self.rapidColorEdit = QLineEdit(self.plotColorsGroup)
        self.rapidColorEdit.setObjectName(u"rapidColorEdit")
        self.rapidColorEdit.setMaxLength(7)

        self.rapidColorLayout.addWidget(self.rapidColorEdit)


        self.colorsForm.setLayout(0, QFormLayout.ItemRole.FieldRole, self.rapidColorLayout)

        self.linearLabel = QLabel(self.plotColorsGroup)
        self.linearLabel.setObjectName(u"linearLabel")

        self.colorsForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.linearLabel)

        self.linearColorLayout = QHBoxLayout()
        self.linearColorLayout.setObjectName(u"linearColorLayout")
        self.linearColorButton = QPushButton(self.plotColorsGroup)
        self.linearColorButton.setObjectName(u"linearColorButton")

        self.linearColorLayout.addWidget(self.linearColorButton)

        self.linearColorEdit = QLineEdit(self.plotColorsGroup)
        self.linearColorEdit.setObjectName(u"linearColorEdit")
        self.linearColorEdit.setMaxLength(7)

        self.linearColorLayout.addWidget(self.linearColorEdit)


        self.colorsForm.setLayout(1, QFormLayout.ItemRole.FieldRole, self.linearColorLayout)

        self.arcLabel = QLabel(self.plotColorsGroup)
        self.arcLabel.setObjectName(u"arcLabel")

        self.colorsForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.arcLabel)

        self.arcColorLayout = QHBoxLayout()
        self.arcColorLayout.setObjectName(u"arcColorLayout")
        self.arcColorButton = QPushButton(self.plotColorsGroup)
        self.arcColorButton.setObjectName(u"arcColorButton")

        self.arcColorLayout.addWidget(self.arcColorButton)

        self.arcColorEdit = QLineEdit(self.plotColorsGroup)
        self.arcColorEdit.setObjectName(u"arcColorEdit")
        self.arcColorEdit.setMaxLength(7)

        self.arcColorLayout.addWidget(self.arcColorEdit)


        self.colorsForm.setLayout(2, QFormLayout.ItemRole.FieldRole, self.arcColorLayout)

        self.currentLabel = QLabel(self.plotColorsGroup)
        self.currentLabel.setObjectName(u"currentLabel")

        self.colorsForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.currentLabel)

        self.currentColorLayout = QHBoxLayout()
        self.currentColorLayout.setObjectName(u"currentColorLayout")
        self.currentColorButton = QPushButton(self.plotColorsGroup)
        self.currentColorButton.setObjectName(u"currentColorButton")

        self.currentColorLayout.addWidget(self.currentColorButton)

        self.currentColorEdit = QLineEdit(self.plotColorsGroup)
        self.currentColorEdit.setObjectName(u"currentColorEdit")
        self.currentColorEdit.setMaxLength(7)

        self.currentColorLayout.addWidget(self.currentColorEdit)


        self.colorsForm.setLayout(3, QFormLayout.ItemRole.FieldRole, self.currentColorLayout)

        self.toolColorLabel = QLabel(self.plotColorsGroup)
        self.toolColorLabel.setObjectName(u"toolColorLabel")

        self.colorsForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.toolColorLabel)

        self.toolColorLayout = QHBoxLayout()
        self.toolColorLayout.setObjectName(u"toolColorLayout")
        self.toolColorButton = QPushButton(self.plotColorsGroup)
        self.toolColorButton.setObjectName(u"toolColorButton")

        self.toolColorLayout.addWidget(self.toolColorButton)

        self.toolColorEdit = QLineEdit(self.plotColorsGroup)
        self.toolColorEdit.setObjectName(u"toolColorEdit")
        self.toolColorEdit.setMaxLength(7)

        self.toolColorLayout.addWidget(self.toolColorEdit)


        self.colorsForm.setLayout(4, QFormLayout.ItemRole.FieldRole, self.toolColorLayout)

        self.backgroundLabel = QLabel(self.plotColorsGroup)
        self.backgroundLabel.setObjectName(u"backgroundLabel")

        self.colorsForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.backgroundLabel)

        self.backgroundColorLayout = QHBoxLayout()
        self.backgroundColorLayout.setObjectName(u"backgroundColorLayout")
        self.backgroundColorButton = QPushButton(self.plotColorsGroup)
        self.backgroundColorButton.setObjectName(u"backgroundColorButton")

        self.backgroundColorLayout.addWidget(self.backgroundColorButton)

        self.backgroundColorEdit = QLineEdit(self.plotColorsGroup)
        self.backgroundColorEdit.setObjectName(u"backgroundColorEdit")
        self.backgroundColorEdit.setMaxLength(7)

        self.backgroundColorLayout.addWidget(self.backgroundColorEdit)


        self.colorsForm.setLayout(5, QFormLayout.ItemRole.FieldRole, self.backgroundColorLayout)

        self.stlColorLabel = QLabel(self.plotColorsGroup)
        self.stlColorLabel.setObjectName(u"stlColorLabel")

        self.colorsForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.stlColorLabel)

        self.stlColorLayout = QHBoxLayout()
        self.stlColorLayout.setObjectName(u"stlColorLayout")
        self.stlColorButton = QPushButton(self.plotColorsGroup)
        self.stlColorButton.setObjectName(u"stlColorButton")

        self.stlColorLayout.addWidget(self.stlColorButton)

        self.stlColorEdit = QLineEdit(self.plotColorsGroup)
        self.stlColorEdit.setObjectName(u"stlColorEdit")
        self.stlColorEdit.setMaxLength(7)

        self.stlColorLayout.addWidget(self.stlColorEdit)


        self.colorsForm.setLayout(6, QFormLayout.ItemRole.FieldRole, self.stlColorLayout)


        self.colorsLayout.addWidget(self.plotColorsGroup)

        self.tabs.addTab(self.colorsTab, "")
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
        self.fontSizeSpin.setValue(12)

        self.editorForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.fontSizeSpin)

        self.caretLineCheck = QCheckBox(self.editorTab)
        self.caretLineCheck.setObjectName(u"caretLineCheck")

        self.editorForm.setWidget(2, QFormLayout.ItemRole.SpanningRole, self.caretLineCheck)

        self.marginCheck = QCheckBox(self.editorTab)
        self.marginCheck.setObjectName(u"marginCheck")

        self.editorForm.setWidget(3, QFormLayout.ItemRole.SpanningRole, self.marginCheck)

        self.eolCheck = QCheckBox(self.editorTab)
        self.eolCheck.setObjectName(u"eolCheck")

        self.editorForm.setWidget(4, QFormLayout.ItemRole.SpanningRole, self.eolCheck)

        self.whitespaceCheck = QCheckBox(self.editorTab)
        self.whitespaceCheck.setObjectName(u"whitespaceCheck")

        self.editorForm.setWidget(5, QFormLayout.ItemRole.SpanningRole, self.whitespaceCheck)

        self.tabs.addTab(self.editorTab, "")
        self.hotkeysTab = QWidget()
        self.hotkeysTab.setObjectName(u"hotkeysTab")
        self.hotkeysLayout = QVBoxLayout(self.hotkeysTab)
        self.hotkeysLayout.setObjectName(u"hotkeysLayout")
        self.hotkeysTable = QTableWidget(self.hotkeysTab)
        if (self.hotkeysTable.columnCount() < 3):
            self.hotkeysTable.setColumnCount(3)
        __qtablewidgetitem = QTableWidgetItem()
        self.hotkeysTable.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.hotkeysTable.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.hotkeysTable.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        self.hotkeysTable.setObjectName(u"hotkeysTable")
        self.hotkeysTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.hotkeysTable.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.hotkeysTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.hotkeysLayout.addWidget(self.hotkeysTable)

        self.editHotkeyButton = QPushButton(self.hotkeysTab)
        self.editHotkeyButton.setObjectName(u"editHotkeyButton")

        self.hotkeysLayout.addWidget(self.editHotkeyButton)

        self.tabs.addTab(self.hotkeysTab, "")
        self.plotTab = QWidget()
        self.plotTab.setObjectName(u"plotTab")
        self.plotForm = QFormLayout(self.plotTab)
        self.plotForm.setObjectName(u"plotForm")
        self.plotForm.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.lineWidthLabel = QLabel(self.plotTab)
        self.lineWidthLabel.setObjectName(u"lineWidthLabel")

        self.plotForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.lineWidthLabel)

        self.lineWidthSpin = QDoubleSpinBox(self.plotTab)
        self.lineWidthSpin.setObjectName(u"lineWidthSpin")
        self.lineWidthSpin.setDecimals(2)
        self.lineWidthSpin.setMinimum(0.250000000000000)
        self.lineWidthSpin.setMaximum(6.000000000000000)
        self.lineWidthSpin.setSingleStep(0.250000000000000)
        self.lineWidthSpin.setValue(1.500000000000000)

        self.plotForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.lineWidthSpin)

        self.gridStepLabel = QLabel(self.plotTab)
        self.gridStepLabel.setObjectName(u"gridStepLabel")

        self.plotForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.gridStepLabel)

        self.gridStepSpin = QDoubleSpinBox(self.plotTab)
        self.gridStepSpin.setObjectName(u"gridStepSpin")
        self.gridStepSpin.setDecimals(3)
        self.gridStepSpin.setMaximum(1000000.000000000000000)

        self.plotForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.gridStepSpin)

        self.axesCheck = QCheckBox(self.plotTab)
        self.axesCheck.setObjectName(u"axesCheck")

        self.plotForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.axesCheck)

        self.gridCheck = QCheckBox(self.plotTab)
        self.gridCheck.setObjectName(u"gridCheck")

        self.plotForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.gridCheck)

        self.backgroundGradientCheck = QCheckBox(self.plotTab)
        self.backgroundGradientCheck.setObjectName(u"backgroundGradientCheck")

        self.plotForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.backgroundGradientCheck)

        self.showStockCheck = QCheckBox(self.plotTab)
        self.showStockCheck.setObjectName(u"showStockCheck")

        self.plotForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.showStockCheck)

        self.stlWireframeCheck = QCheckBox(self.plotTab)
        self.stlWireframeCheck.setObjectName(u"stlWireframeCheck")

        self.plotForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.stlWireframeCheck)

        self.showRapidCheck = QCheckBox(self.plotTab)
        self.showRapidCheck.setObjectName(u"showRapidCheck")

        self.plotForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.showRapidCheck)

        self.dashedRapidCheck = QCheckBox(self.plotTab)
        self.dashedRapidCheck.setObjectName(u"dashedRapidCheck")

        self.plotForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.dashedRapidCheck)

        self.colorByToolCheck = QCheckBox(self.plotTab)
        self.colorByToolCheck.setObjectName(u"colorByToolCheck")

        self.plotForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.colorByToolCheck)

        self.playbackSpeedLabel = QLabel(self.plotTab)
        self.playbackSpeedLabel.setObjectName(u"playbackSpeedLabel")

        self.plotForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.playbackSpeedLabel)

        self.playbackSpeedLayout = QHBoxLayout()
        self.playbackSpeedLayout.setObjectName(u"playbackSpeedLayout")
        self.playbackSpeedSlider = QSlider(self.plotTab)
        self.playbackSpeedSlider.setObjectName(u"playbackSpeedSlider")
        self.playbackSpeedSlider.setMinimum(1)
        self.playbackSpeedSlider.setMaximum(5)
        self.playbackSpeedSlider.setValue(3)
        self.playbackSpeedSlider.setOrientation(Qt.Orientation.Horizontal)

        self.playbackSpeedLayout.addWidget(self.playbackSpeedSlider)

        self.playbackSpeedValueLabel = QLabel(self.plotTab)
        self.playbackSpeedValueLabel.setObjectName(u"playbackSpeedValueLabel")

        self.playbackSpeedLayout.addWidget(self.playbackSpeedValueLabel)


        self.plotForm.setLayout(6, QFormLayout.ItemRole.FieldRole, self.playbackSpeedLayout)

        self.tabs.addTab(self.plotTab, "")
        self.postprocessorsTab = QWidget()
        self.postprocessorsTab.setObjectName(u"postprocessorsTab")
        self.postprocessorsLayout = QVBoxLayout(self.postprocessorsTab)
        self.postprocessorsLayout.setObjectName(u"postprocessorsLayout")
        self.postprocessorsHelp = QLabel(self.postprocessorsTab)
        self.postprocessorsHelp.setObjectName(u"postprocessorsHelp")
        self.postprocessorsHelp.setWordWrap(True)

        self.postprocessorsLayout.addWidget(self.postprocessorsHelp)

        self.postProfileSplitter = QSplitter(self.postprocessorsTab)
        self.postProfileSplitter.setObjectName(u"postProfileSplitter")
        self.postProfileSplitter.setOrientation(Qt.Orientation.Horizontal)
        self.postProfileSidebar = QWidget(self.postProfileSplitter)
        self.postProfileSidebar.setObjectName(u"postProfileSidebar")
        self.postProfileSidebarLayout = QVBoxLayout(self.postProfileSidebar)
        self.postProfileSidebarLayout.setObjectName(u"postProfileSidebarLayout")
        self.postProfileSidebarLayout.setContentsMargins(0, 0, 0, 0)
        self.postProfileList = QListWidget(self.postProfileSidebar)
        self.postProfileList.setObjectName(u"postProfileList")

        self.postProfileSidebarLayout.addWidget(self.postProfileList)

        self.postProfileActions = QHBoxLayout()
        self.postProfileActions.setObjectName(u"postProfileActions")
        self.newPostProfileButton = QPushButton(self.postProfileSidebar)
        self.newPostProfileButton.setObjectName(u"newPostProfileButton")
        icon = QIcon()
        icon.addFile(u":/resource/icons/add.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.newPostProfileButton.setIcon(icon)
        self.newPostProfileButton.setIconSize(QSize(24, 24))

        self.postProfileActions.addWidget(self.newPostProfileButton)

        self.savePostProfileButton = QPushButton(self.postProfileSidebar)
        self.savePostProfileButton.setObjectName(u"savePostProfileButton")
        icon1 = QIcon()
        icon1.addFile(u":/resource/icons/save.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.savePostProfileButton.setIcon(icon1)
        self.savePostProfileButton.setIconSize(QSize(24, 24))

        self.postProfileActions.addWidget(self.savePostProfileButton)

        self.renamePostProfileButton = QPushButton(self.postProfileSidebar)
        self.renamePostProfileButton.setObjectName(u"renamePostProfileButton")
        icon2 = QIcon()
        icon2.addFile(u":/resource/icons/rename.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.renamePostProfileButton.setIcon(icon2)
        self.renamePostProfileButton.setIconSize(QSize(24, 24))

        self.postProfileActions.addWidget(self.renamePostProfileButton)

        self.removePostProfileButton = QPushButton(self.postProfileSidebar)
        self.removePostProfileButton.setObjectName(u"removePostProfileButton")
        icon3 = QIcon()
        icon3.addFile(u":/resource/icons/trash.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.removePostProfileButton.setIcon(icon3)
        self.removePostProfileButton.setIconSize(QSize(24, 24))

        self.postProfileActions.addWidget(self.removePostProfileButton)


        self.postProfileSidebarLayout.addLayout(self.postProfileActions)

        self.postProfileSplitter.addWidget(self.postProfileSidebar)
        self.postProfileEditorHost = QWidget(self.postProfileSplitter)
        self.postProfileEditorHost.setObjectName(u"postProfileEditorHost")
        self.postProfileEditorLayout = QVBoxLayout(self.postProfileEditorHost)
        self.postProfileEditorLayout.setObjectName(u"postProfileEditorLayout")
        self.postProfileEditorLayout.setContentsMargins(0, 0, 0, 0)
        self.postProfileSplitter.addWidget(self.postProfileEditorHost)

        self.postprocessorsLayout.addWidget(self.postProfileSplitter)

        self.postProfileErrorLabel = QLabel(self.postprocessorsTab)
        self.postProfileErrorLabel.setObjectName(u"postProfileErrorLabel")
        self.postProfileErrorLabel.setWordWrap(True)

        self.postprocessorsLayout.addWidget(self.postProfileErrorLabel)

        self.postprocessorsLayout.setStretch(1, 1)
        self.tabs.addTab(self.postprocessorsTab, "")
        self.rotaryTab = QWidget()
        self.rotaryTab.setObjectName(u"rotaryTab")
        self.rotaryLayout = QVBoxLayout(self.rotaryTab)
        self.rotaryLayout.setObjectName(u"rotaryLayout")
        self.rotaryProfileSplitter = QSplitter(self.rotaryTab)
        self.rotaryProfileSplitter.setObjectName(u"rotaryProfileSplitter")
        self.rotaryProfileSplitter.setOrientation(Qt.Orientation.Horizontal)
        self.rotaryProfileSidebar = QWidget(self.rotaryProfileSplitter)
        self.rotaryProfileSidebar.setObjectName(u"rotaryProfileSidebar")
        self.rotaryProfileSidebarLayout = QVBoxLayout(self.rotaryProfileSidebar)
        self.rotaryProfileSidebarLayout.setObjectName(u"rotaryProfileSidebarLayout")
        self.rotaryProfileSidebarLayout.setContentsMargins(0, 0, 0, 0)
        self.rotaryProfileList = QListWidget(self.rotaryProfileSidebar)
        self.rotaryProfileList.setObjectName(u"rotaryProfileList")

        self.rotaryProfileSidebarLayout.addWidget(self.rotaryProfileList)

        self.rotaryProfileActions = QHBoxLayout()
        self.rotaryProfileActions.setObjectName(u"rotaryProfileActions")
        self.rotaryCopyButton = QPushButton(self.rotaryProfileSidebar)
        self.rotaryCopyButton.setObjectName(u"rotaryCopyButton")
        self.rotaryCopyButton.setIcon(icon)
        self.rotaryCopyButton.setIconSize(QSize(24, 24))

        self.rotaryProfileActions.addWidget(self.rotaryCopyButton)

        self.rotarySaveButton = QPushButton(self.rotaryProfileSidebar)
        self.rotarySaveButton.setObjectName(u"rotarySaveButton")
        self.rotarySaveButton.setIcon(icon1)
        self.rotarySaveButton.setIconSize(QSize(24, 24))

        self.rotaryProfileActions.addWidget(self.rotarySaveButton)

        self.rotaryRenameButton = QPushButton(self.rotaryProfileSidebar)
        self.rotaryRenameButton.setObjectName(u"rotaryRenameButton")
        self.rotaryRenameButton.setIcon(icon2)
        self.rotaryRenameButton.setIconSize(QSize(24, 24))

        self.rotaryProfileActions.addWidget(self.rotaryRenameButton)

        self.rotaryDeleteButton = QPushButton(self.rotaryProfileSidebar)
        self.rotaryDeleteButton.setObjectName(u"rotaryDeleteButton")
        self.rotaryDeleteButton.setIcon(icon3)
        self.rotaryDeleteButton.setIconSize(QSize(24, 24))

        self.rotaryProfileActions.addWidget(self.rotaryDeleteButton)


        self.rotaryProfileSidebarLayout.addLayout(self.rotaryProfileActions)

        self.rotaryProfileSplitter.addWidget(self.rotaryProfileSidebar)
        self.rotaryProfileEditor = QWidget(self.rotaryProfileSplitter)
        self.rotaryProfileEditor.setObjectName(u"rotaryProfileEditor")
        self.rotaryProfileEditorLayout = QVBoxLayout(self.rotaryProfileEditor)
        self.rotaryProfileEditorLayout.setObjectName(u"rotaryProfileEditorLayout")
        self.rotaryProfileEditorLayout.setContentsMargins(9, 9, 9, 9)
        self.rotaryProfileIdLabel = QLabel(self.rotaryProfileEditor)
        self.rotaryProfileIdLabel.setObjectName(u"rotaryProfileIdLabel")

        self.rotaryProfileEditorLayout.addWidget(self.rotaryProfileIdLabel)

        self.rotaryNameForm = QFormLayout()
        self.rotaryNameForm.setObjectName(u"rotaryNameForm")
        self.rotaryNameLabel = QLabel(self.rotaryProfileEditor)
        self.rotaryNameLabel.setObjectName(u"rotaryNameLabel")

        self.rotaryNameForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.rotaryNameLabel)

        self.rotaryNameEdit = QLineEdit(self.rotaryProfileEditor)
        self.rotaryNameEdit.setObjectName(u"rotaryNameEdit")

        self.rotaryNameForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.rotaryNameEdit)

        self.rotaryEnabledCheck = QCheckBox(self.rotaryProfileEditor)
        self.rotaryEnabledCheck.setObjectName(u"rotaryEnabledCheck")

        self.rotaryNameForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.rotaryEnabledCheck)


        self.rotaryProfileEditorLayout.addLayout(self.rotaryNameForm)

        self.rotaryStatusLabel = QLabel(self.rotaryProfileEditor)
        self.rotaryStatusLabel.setObjectName(u"rotaryStatusLabel")
        self.rotaryStatusLabel.setWordWrap(True)

        self.rotaryProfileEditorLayout.addWidget(self.rotaryStatusLabel)

        self.rotaryAxis1Group = QGroupBox(self.rotaryProfileEditor)
        self.rotaryAxis1Group.setObjectName(u"rotaryAxis1Group")
        self.rotaryAxis1Form = QFormLayout(self.rotaryAxis1Group)
        self.rotaryAxis1Form.setObjectName(u"rotaryAxis1Form")
        self.rotaryBranch1Label = QLabel(self.rotaryAxis1Group)
        self.rotaryBranch1Label.setObjectName(u"rotaryBranch1Label")

        self.rotaryAxis1Form.setWidget(0, QFormLayout.ItemRole.LabelRole, self.rotaryBranch1Label)

        self.rotaryBranch1Combo = QComboBox(self.rotaryAxis1Group)
        self.rotaryBranch1Combo.setObjectName(u"rotaryBranch1Combo")

        self.rotaryAxis1Form.setWidget(0, QFormLayout.ItemRole.FieldRole, self.rotaryBranch1Combo)

        self.rotaryAddress1Label = QLabel(self.rotaryAxis1Group)
        self.rotaryAddress1Label.setObjectName(u"rotaryAddress1Label")

        self.rotaryAxis1Form.setWidget(1, QFormLayout.ItemRole.LabelRole, self.rotaryAddress1Label)

        self.rotaryAddress1Combo = QComboBox(self.rotaryAxis1Group)
        self.rotaryAddress1Combo.setObjectName(u"rotaryAddress1Combo")

        self.rotaryAxis1Form.setWidget(1, QFormLayout.ItemRole.FieldRole, self.rotaryAddress1Combo)

        self.rotaryDirection1Label = QLabel(self.rotaryAxis1Group)
        self.rotaryDirection1Label.setObjectName(u"rotaryDirection1Label")

        self.rotaryAxis1Form.setWidget(2, QFormLayout.ItemRole.LabelRole, self.rotaryDirection1Label)

        self.rotaryVector1Layout = QHBoxLayout()
        self.rotaryVector1Layout.setObjectName(u"rotaryVector1Layout")
        self.rotaryX1Label = QLabel(self.rotaryAxis1Group)
        self.rotaryX1Label.setObjectName(u"rotaryX1Label")

        self.rotaryVector1Layout.addWidget(self.rotaryX1Label)

        self.rotaryX1Edit = QLineEdit(self.rotaryAxis1Group)
        self.rotaryX1Edit.setObjectName(u"rotaryX1Edit")

        self.rotaryVector1Layout.addWidget(self.rotaryX1Edit)

        self.rotaryY1Label = QLabel(self.rotaryAxis1Group)
        self.rotaryY1Label.setObjectName(u"rotaryY1Label")

        self.rotaryVector1Layout.addWidget(self.rotaryY1Label)

        self.rotaryY1Edit = QLineEdit(self.rotaryAxis1Group)
        self.rotaryY1Edit.setObjectName(u"rotaryY1Edit")

        self.rotaryVector1Layout.addWidget(self.rotaryY1Edit)

        self.rotaryZ1Label = QLabel(self.rotaryAxis1Group)
        self.rotaryZ1Label.setObjectName(u"rotaryZ1Label")

        self.rotaryVector1Layout.addWidget(self.rotaryZ1Label)

        self.rotaryZ1Edit = QLineEdit(self.rotaryAxis1Group)
        self.rotaryZ1Edit.setObjectName(u"rotaryZ1Edit")

        self.rotaryVector1Layout.addWidget(self.rotaryZ1Edit)

        self.rotaryMin1Label = QLabel(self.rotaryAxis1Group)
        self.rotaryMin1Label.setObjectName(u"rotaryMin1Label")

        self.rotaryVector1Layout.addWidget(self.rotaryMin1Label)

        self.rotaryMin1Edit = QLineEdit(self.rotaryAxis1Group)
        self.rotaryMin1Edit.setObjectName(u"rotaryMin1Edit")

        self.rotaryVector1Layout.addWidget(self.rotaryMin1Edit)

        self.rotaryMax1Label = QLabel(self.rotaryAxis1Group)
        self.rotaryMax1Label.setObjectName(u"rotaryMax1Label")

        self.rotaryVector1Layout.addWidget(self.rotaryMax1Label)

        self.rotaryMax1Edit = QLineEdit(self.rotaryAxis1Group)
        self.rotaryMax1Edit.setObjectName(u"rotaryMax1Edit")

        self.rotaryVector1Layout.addWidget(self.rotaryMax1Edit)


        self.rotaryAxis1Form.setLayout(2, QFormLayout.ItemRole.FieldRole, self.rotaryVector1Layout)


        self.rotaryProfileEditorLayout.addWidget(self.rotaryAxis1Group)

        self.rotaryAxis2Group = QGroupBox(self.rotaryProfileEditor)
        self.rotaryAxis2Group.setObjectName(u"rotaryAxis2Group")
        self.rotaryAxis2Form = QFormLayout(self.rotaryAxis2Group)
        self.rotaryAxis2Form.setObjectName(u"rotaryAxis2Form")
        self.rotaryBranch2Label = QLabel(self.rotaryAxis2Group)
        self.rotaryBranch2Label.setObjectName(u"rotaryBranch2Label")

        self.rotaryAxis2Form.setWidget(0, QFormLayout.ItemRole.LabelRole, self.rotaryBranch2Label)

        self.rotaryBranch2Combo = QComboBox(self.rotaryAxis2Group)
        self.rotaryBranch2Combo.setObjectName(u"rotaryBranch2Combo")

        self.rotaryAxis2Form.setWidget(0, QFormLayout.ItemRole.FieldRole, self.rotaryBranch2Combo)

        self.rotaryAddress2Label = QLabel(self.rotaryAxis2Group)
        self.rotaryAddress2Label.setObjectName(u"rotaryAddress2Label")

        self.rotaryAxis2Form.setWidget(1, QFormLayout.ItemRole.LabelRole, self.rotaryAddress2Label)

        self.rotaryAddress2Combo = QComboBox(self.rotaryAxis2Group)
        self.rotaryAddress2Combo.setObjectName(u"rotaryAddress2Combo")

        self.rotaryAxis2Form.setWidget(1, QFormLayout.ItemRole.FieldRole, self.rotaryAddress2Combo)

        self.rotaryDirection2Label = QLabel(self.rotaryAxis2Group)
        self.rotaryDirection2Label.setObjectName(u"rotaryDirection2Label")

        self.rotaryAxis2Form.setWidget(2, QFormLayout.ItemRole.LabelRole, self.rotaryDirection2Label)

        self.rotaryVector2Layout = QHBoxLayout()
        self.rotaryVector2Layout.setObjectName(u"rotaryVector2Layout")
        self.rotaryX2Label = QLabel(self.rotaryAxis2Group)
        self.rotaryX2Label.setObjectName(u"rotaryX2Label")

        self.rotaryVector2Layout.addWidget(self.rotaryX2Label)

        self.rotaryX2Edit = QLineEdit(self.rotaryAxis2Group)
        self.rotaryX2Edit.setObjectName(u"rotaryX2Edit")

        self.rotaryVector2Layout.addWidget(self.rotaryX2Edit)

        self.rotaryY2Label = QLabel(self.rotaryAxis2Group)
        self.rotaryY2Label.setObjectName(u"rotaryY2Label")

        self.rotaryVector2Layout.addWidget(self.rotaryY2Label)

        self.rotaryY2Edit = QLineEdit(self.rotaryAxis2Group)
        self.rotaryY2Edit.setObjectName(u"rotaryY2Edit")

        self.rotaryVector2Layout.addWidget(self.rotaryY2Edit)

        self.rotaryZ2Label = QLabel(self.rotaryAxis2Group)
        self.rotaryZ2Label.setObjectName(u"rotaryZ2Label")

        self.rotaryVector2Layout.addWidget(self.rotaryZ2Label)

        self.rotaryZ2Edit = QLineEdit(self.rotaryAxis2Group)
        self.rotaryZ2Edit.setObjectName(u"rotaryZ2Edit")

        self.rotaryVector2Layout.addWidget(self.rotaryZ2Edit)

        self.rotaryMin2Label = QLabel(self.rotaryAxis2Group)
        self.rotaryMin2Label.setObjectName(u"rotaryMin2Label")

        self.rotaryVector2Layout.addWidget(self.rotaryMin2Label)

        self.rotaryMin2Edit = QLineEdit(self.rotaryAxis2Group)
        self.rotaryMin2Edit.setObjectName(u"rotaryMin2Edit")

        self.rotaryVector2Layout.addWidget(self.rotaryMin2Edit)

        self.rotaryMax2Label = QLabel(self.rotaryAxis2Group)
        self.rotaryMax2Label.setObjectName(u"rotaryMax2Label")

        self.rotaryVector2Layout.addWidget(self.rotaryMax2Label)

        self.rotaryMax2Edit = QLineEdit(self.rotaryAxis2Group)
        self.rotaryMax2Edit.setObjectName(u"rotaryMax2Edit")

        self.rotaryVector2Layout.addWidget(self.rotaryMax2Edit)


        self.rotaryAxis2Form.setLayout(2, QFormLayout.ItemRole.FieldRole, self.rotaryVector2Layout)


        self.rotaryProfileEditorLayout.addWidget(self.rotaryAxis2Group)

        self.rotaryOrderLabel = QLabel(self.rotaryProfileEditor)
        self.rotaryOrderLabel.setObjectName(u"rotaryOrderLabel")
        self.rotaryOrderLabel.setWordWrap(True)

        self.rotaryProfileEditorLayout.addWidget(self.rotaryOrderLabel)

        self.rotaryEditorSpacer = QSpacerItem(20, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.rotaryProfileEditorLayout.addItem(self.rotaryEditorSpacer)

        self.rotaryProfileSplitter.addWidget(self.rotaryProfileEditor)

        self.rotaryLayout.addWidget(self.rotaryProfileSplitter)

        self.rotaryLayout.setStretch(0, 1)
        self.tabs.addTab(self.rotaryTab, "")
        self.toolDiscoveryTab = QWidget()
        self.toolDiscoveryTab.setObjectName(u"toolDiscoveryTab")
        self.discoveryLayout = QVBoxLayout(self.toolDiscoveryTab)
        self.discoveryLayout.setObjectName(u"discoveryLayout")
        self.discoveryModeLayout = QHBoxLayout()
        self.discoveryModeLayout.setObjectName(u"discoveryModeLayout")
        self.discoveryModeLabel = QLabel(self.toolDiscoveryTab)
        self.discoveryModeLabel.setObjectName(u"discoveryModeLabel")

        self.discoveryModeLayout.addWidget(self.discoveryModeLabel)

        self.discoveryModeCombo = QComboBox(self.toolDiscoveryTab)
        self.discoveryModeCombo.addItem("")
        self.discoveryModeCombo.addItem("")
        self.discoveryModeCombo.setObjectName(u"discoveryModeCombo")
        self.discoveryModeCombo.setMaximumSize(QSize(160, 16777215))

        self.discoveryModeLayout.addWidget(self.discoveryModeCombo)

        self.discoveryRegexCheck = QCheckBox(self.toolDiscoveryTab)
        self.discoveryRegexCheck.setObjectName(u"discoveryRegexCheck")

        self.discoveryModeLayout.addWidget(self.discoveryRegexCheck)

        self.discoveryModeSpacer = QSpacerItem(20, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.discoveryModeLayout.addItem(self.discoveryModeSpacer)


        self.discoveryLayout.addLayout(self.discoveryModeLayout)

        self.discoverySplitter = QSplitter(self.toolDiscoveryTab)
        self.discoverySplitter.setObjectName(u"discoverySplitter")
        self.discoverySplitter.setOrientation(Qt.Orientation.Horizontal)
        self.discoveryTypesPane = QWidget(self.discoverySplitter)
        self.discoveryTypesPane.setObjectName(u"discoveryTypesPane")
        self.discoveryTypesLayout = QVBoxLayout(self.discoveryTypesPane)
        self.discoveryTypesLayout.setObjectName(u"discoveryTypesLayout")
        self.discoveryTypesLayout.setContentsMargins(0, 0, 0, 0)
        self.discoveryTypesLabel = QLabel(self.discoveryTypesPane)
        self.discoveryTypesLabel.setObjectName(u"discoveryTypesLabel")

        self.discoveryTypesLayout.addWidget(self.discoveryTypesLabel)

        self.discoveryTypesList = QListWidget(self.discoveryTypesPane)
        self.discoveryTypesList.setObjectName(u"discoveryTypesList")
        self.discoveryTypesList.setSpacing(3)
        self.discoveryTypesList.setFrameShape(QFrame.Shape.NoFrame)

        self.discoveryTypesLayout.addWidget(self.discoveryTypesList)

        self.discoverySplitter.addWidget(self.discoveryTypesPane)
        self.discoveryEditorPane = QWidget(self.discoverySplitter)
        self.discoveryEditorPane.setObjectName(u"discoveryEditorPane")
        self.discoveryEditorLayout = QVBoxLayout(self.discoveryEditorPane)
        self.discoveryEditorLayout.setObjectName(u"discoveryEditorLayout")
        self.discoveryEditorLayout.setContentsMargins(9, 9, 9, 9)
        self.discoveryNamesLabel = QLabel(self.discoveryEditorPane)
        self.discoveryNamesLabel.setObjectName(u"discoveryNamesLabel")

        self.discoveryEditorLayout.addWidget(self.discoveryNamesLabel)

        self.discoveryFormatLabel = QLabel(self.discoveryEditorPane)
        self.discoveryFormatLabel.setObjectName(u"discoveryFormatLabel")
        self.discoveryFormatLabel.setWordWrap(True)

        self.discoveryEditorLayout.addWidget(self.discoveryFormatLabel)

        self.discoveryNamesEdit = QPlainTextEdit(self.discoveryEditorPane)
        self.discoveryNamesEdit.setObjectName(u"discoveryNamesEdit")
        self.discoveryNamesEdit.setTabChangesFocus(True)

        self.discoveryEditorLayout.addWidget(self.discoveryNamesEdit)

        self.discoveryParametersLabel = QLabel(self.discoveryEditorPane)
        self.discoveryParametersLabel.setObjectName(u"discoveryParametersLabel")

        self.discoveryEditorLayout.addWidget(self.discoveryParametersLabel)

        self.discoveryParameterTable = QTableWidget(self.discoveryEditorPane)
        if (self.discoveryParameterTable.columnCount() < 2):
            self.discoveryParameterTable.setColumnCount(2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.discoveryParameterTable.setHorizontalHeaderItem(0, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.discoveryParameterTable.setHorizontalHeaderItem(1, __qtablewidgetitem4)
        self.discoveryParameterTable.setObjectName(u"discoveryParameterTable")
        self.discoveryParameterTable.setAlternatingRowColors(True)
        self.discoveryParameterTable.setShowGrid(False)
        self.discoveryParameterTable.setFrameShape(QFrame.Shape.NoFrame)
        self.discoveryParameterTable.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked|QAbstractItemView.EditTrigger.SelectedClicked|QAbstractItemView.EditTrigger.EditKeyPressed)

        self.discoveryEditorLayout.addWidget(self.discoveryParameterTable)

        self.discoveryEditorLayout.setStretch(2, 2)
        self.discoveryEditorLayout.setStretch(4, 3)
        self.discoverySplitter.addWidget(self.discoveryEditorPane)

        self.discoveryLayout.addWidget(self.discoverySplitter)

        self.discoveryTestLabel = QLabel(self.toolDiscoveryTab)
        self.discoveryTestLabel.setObjectName(u"discoveryTestLabel")

        self.discoveryLayout.addWidget(self.discoveryTestLabel)

        self.discoveryCommentLayout = QHBoxLayout()
        self.discoveryCommentLayout.setObjectName(u"discoveryCommentLayout")
        self.discoveryCommentLabel = QLabel(self.toolDiscoveryTab)
        self.discoveryCommentLabel.setObjectName(u"discoveryCommentLabel")

        self.discoveryCommentLayout.addWidget(self.discoveryCommentLabel)

        self.discoveryCommentEdit = QLineEdit(self.toolDiscoveryTab)
        self.discoveryCommentEdit.setObjectName(u"discoveryCommentEdit")

        self.discoveryCommentLayout.addWidget(self.discoveryCommentEdit)

        self.discoveryTestButton = QPushButton(self.toolDiscoveryTab)
        self.discoveryTestButton.setObjectName(u"discoveryTestButton")
        self.discoveryTestButton.setMaximumSize(QSize(70, 16777215))

        self.discoveryCommentLayout.addWidget(self.discoveryTestButton)


        self.discoveryLayout.addLayout(self.discoveryCommentLayout)

        self.discoveryResultLabel = QLabel(self.toolDiscoveryTab)
        self.discoveryResultLabel.setObjectName(u"discoveryResultLabel")
        self.discoveryResultLabel.setWordWrap(True)
        self.discoveryResultLabel.setMinimumSize(QSize(0, 24))
        self.discoveryResultLabel.setTextFormat(Qt.TextFormat.RichText)
        self.discoveryResultLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.discoveryLayout.addWidget(self.discoveryResultLabel)

        self.discoveryErrorLabel = QLabel(self.toolDiscoveryTab)
        self.discoveryErrorLabel.setObjectName(u"discoveryErrorLabel")
        self.discoveryErrorLabel.setWordWrap(True)
        self.discoveryErrorLabel.setMinimumSize(QSize(0, 24))

        self.discoveryLayout.addWidget(self.discoveryErrorLabel)

        self.discoveryLayout.setStretch(1, 1)
        self.tabs.addTab(self.toolDiscoveryTab, "")

        self.verticalLayout.addWidget(self.tabs)

        self.buttonBox = QDialogButtonBox(OptionsDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.RestoreDefaults)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(OptionsDlg)
        self.buttonBox.accepted.connect(OptionsDlg.accept)
        self.buttonBox.rejected.connect(OptionsDlg.reject)

        self.toolpanelIconsCombo.setCurrentIndex(1)


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
        self.fileTypeCombo.setItemText(2, QCoreApplication.translate("OptionsDlg", u"iTNC-code", None))

        self.unitsLabel.setText(QCoreApplication.translate("OptionsDlg", u"Default units", None))
        self.unitsCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"Millimeters", None))
        self.unitsCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"Inches", None))

        self.languageLabel.setText(QCoreApplication.translate("OptionsDlg", u"Language", None))
        self.languageCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"English", None))
        self.languageCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"Russian", None))

        self.themeLabel.setText(QCoreApplication.translate("OptionsDlg", u"Theme", None))
        self.themeCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"Light", None))
        self.themeCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"Dark", None))

        self.toolpanelIconsLabel.setText(QCoreApplication.translate("OptionsDlg", u"Toolpanel icons", None))
        self.toolpanelIconsCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"Large 32x32", None))
        self.toolpanelIconsCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"Medium 24x24", None))
        self.toolpanelIconsCombo.setItemText(2, QCoreApplication.translate("OptionsDlg", u"Small 16x16", None))

        self.autoUpdateMaxSegmentsLabel.setText(QCoreApplication.translate("OptionsDlg", u"Auto update max segments", None))
#if QT_CONFIG(tooltip)
        self.autoUpdateMaxSegmentsSpin.setToolTip(QCoreApplication.translate("OptionsDlg", u"Maximum sampled points for automatic refresh only. Manual Update has no hidden render limit.", None))
#endif // QT_CONFIG(tooltip)
        self.maxGeneratedMotionsLabel.setText(QCoreApplication.translate("OptionsDlg", u"Maximum generated motions", None))
#if QT_CONFIG(tooltip)
        self.maxGeneratedMotionsSpin.setToolTip(QCoreApplication.translate("OptionsDlg", u"Maximum total number of motions generated by one CNC execution.", None))
#endif // QT_CONFIG(tooltip)
        self.autoUpdateCheck.setText(QCoreApplication.translate("OptionsDlg", u"Auto update plot while editing", None))
        self.loggingCheck.setText(QCoreApplication.translate("OptionsDlg", u"Enable application log", None))
        self.cimcoLikePickingCheck.setText(QCoreApplication.translate("OptionsDlg", u"Cimco Like Picking", None))
#if QT_CONFIG(tooltip)
        self.cimcoLikePickingCheck.setToolTip(QCoreApplication.translate("OptionsDlg", u"Milling: left-click selects a toolpath movement; drag with the right button to pan. Right-click opens the context menu. When off, use Shift+left-click to select and drag with the left button to pan.", None))
#endif // QT_CONFIG(tooltip)
        self.tabs.setTabText(self.tabs.indexOf(self.generalTab), QCoreApplication.translate("OptionsDlg", u"General", None))
        self.correctionCheck.setText(QCoreApplication.translate("OptionsDlg", u"Cutter compensation", None))
        self.autodetectArcTypeCheck.setText(QCoreApplication.translate("OptionsDlg", u"Autodetect Arc Type", None))
        self.ignoreBlockSkipCheck.setText(QCoreApplication.translate("OptionsDlg", u"Ignore Block Skip", None))
        self.arcSamplingPresetLabel.setText(QCoreApplication.translate("OptionsDlg", u"Arc sampling preset", None))
        self.arcSamplingPresetCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"Exact", None))
        self.arcSamplingPresetCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"Normal", None))
        self.arcSamplingPresetCombo.setItemText(2, QCoreApplication.translate("OptionsDlg", u"Large Program", None))
        self.arcSamplingPresetCombo.setItemText(3, QCoreApplication.translate("OptionsDlg", u"Very Large Program", None))

        self.arcToleranceLabel.setText(QCoreApplication.translate("OptionsDlg", u"Arc tolerance", None))
        self.arcToleranceSpin.setSuffix(QCoreApplication.translate("OptionsDlg", u" mm", None))
        self.maximumCircularRadiusLabel.setText(QCoreApplication.translate("OptionsDlg", u"Maximum circular radius", None))
        self.maximumCircularRadiusSpin.setSuffix(QCoreApplication.translate("OptionsDlg", u" mm", None))
        self.minimumCircularRadiusLabel.setText(QCoreApplication.translate("OptionsDlg", u"Minimum circular radius", None))
        self.minimumCircularRadiusSpin.setSuffix(QCoreApplication.translate("OptionsDlg", u" mm", None))
        self.minimumChordLengthLabel.setText(QCoreApplication.translate("OptionsDlg", u"Minimum chord length", None))
        self.minimumChordLengthSpin.setSuffix(QCoreApplication.translate("OptionsDlg", u" mm", None))
        self.commentStyleLabel.setText(QCoreApplication.translate("OptionsDlg", u"Comment style", None))
        self.commentStyleCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"Parentheses ()", None))
        self.commentStyleCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"Semicolon ;", None))

        self.tabs.setTabText(self.tabs.indexOf(self.cncTab), QCoreApplication.translate("OptionsDlg", u"CNC / Execution", None))
        self.editorColorsGroup.setTitle(QCoreApplication.translate("OptionsDlg", u"Editor", None))
        self.plotColorsGroup.setTitle(QCoreApplication.translate("OptionsDlg", u"Plot", None))
        self.rapidLabel.setText(QCoreApplication.translate("OptionsDlg", u"Rapid move", None))
        self.rapidColorButton.setText("")
        self.linearLabel.setText(QCoreApplication.translate("OptionsDlg", u"Linear move", None))
        self.linearColorButton.setText("")
        self.arcLabel.setText(QCoreApplication.translate("OptionsDlg", u"Circular move", None))
        self.arcColorButton.setText("")
        self.currentLabel.setText(QCoreApplication.translate("OptionsDlg", u"Current segment", None))
        self.currentColorButton.setText("")
        self.toolColorLabel.setText(QCoreApplication.translate("OptionsDlg", u"Milling tool", None))
        self.toolColorButton.setText("")
        self.backgroundLabel.setText(QCoreApplication.translate("OptionsDlg", u"Background", None))
        self.backgroundColorButton.setText("")
        self.stlColorLabel.setText(QCoreApplication.translate("OptionsDlg", u"STL", None))
        self.stlColorButton.setText("")
        self.tabs.setTabText(self.tabs.indexOf(self.colorsTab), QCoreApplication.translate("OptionsDlg", u"Colors", None))
        self.fontLabel.setText(QCoreApplication.translate("OptionsDlg", u"Font family", None))
        self.fontSizeLabel.setText(QCoreApplication.translate("OptionsDlg", u"Font size", None))
        self.caretLineCheck.setText(QCoreApplication.translate("OptionsDlg", u"Highlight current line", None))
        self.marginCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show line numbers", None))
        self.eolCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show EOL", None))
        self.whitespaceCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show whitespace", None))
        self.tabs.setTabText(self.tabs.indexOf(self.editorTab), QCoreApplication.translate("OptionsDlg", u"Editor", None))
        ___qtablewidgetitem = self.hotkeysTable.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("OptionsDlg", u"Command", None))
        ___qtablewidgetitem1 = self.hotkeysTable.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("OptionsDlg", u"Shortcut", None))
        ___qtablewidgetitem2 = self.hotkeysTable.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("OptionsDlg", u"Category", None))
        self.editHotkeyButton.setText(QCoreApplication.translate("OptionsDlg", u"Edit shortcut", None))
        self.tabs.setTabText(self.tabs.indexOf(self.hotkeysTab), QCoreApplication.translate("OptionsDlg", u"Hotkeys", None))
        self.lineWidthLabel.setText(QCoreApplication.translate("OptionsDlg", u"Line width", None))
        self.gridStepLabel.setText(QCoreApplication.translate("OptionsDlg", u"Grid step (0 = adaptive)", None))
        self.axesCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show axes", None))
        self.gridCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show grid", None))
        self.backgroundGradientCheck.setText(QCoreApplication.translate("OptionsDlg", u"Gradient background", None))
        self.showStockCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show Stock", None))
        self.stlWireframeCheck.setText(QCoreApplication.translate("OptionsDlg", u"STL edges only", None))
        self.showRapidCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show rapid moves", None))
        self.dashedRapidCheck.setText(QCoreApplication.translate("OptionsDlg", u"Dashed rapid moves", None))
        self.colorByToolCheck.setText(QCoreApplication.translate("OptionsDlg", u"Color by tool", None))
        self.playbackSpeedLabel.setText(QCoreApplication.translate("OptionsDlg", u"Playback speed", None))
        self.playbackSpeedValueLabel.setText(QCoreApplication.translate("OptionsDlg", u"3 \u2014 100 ms/step", None))
        self.tabs.setTabText(self.tabs.indexOf(self.plotTab), QCoreApplication.translate("OptionsDlg", u"Plot", None))
        self.postprocessorsHelp.setText(QCoreApplication.translate("OptionsDlg", u"Select a profile to view or edit. Built-in profiles are read-only; add a copy to customize it.", None))
#if QT_CONFIG(tooltip)
        self.newPostProfileButton.setToolTip(QCoreApplication.translate("OptionsDlg", u"Add", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.newPostProfileButton.setAccessibleName(QCoreApplication.translate("OptionsDlg", u"Add", None))
#endif // QT_CONFIG(accessibility)
        self.newPostProfileButton.setText("")
#if QT_CONFIG(tooltip)
        self.savePostProfileButton.setToolTip(QCoreApplication.translate("OptionsDlg", u"Save", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.savePostProfileButton.setAccessibleName(QCoreApplication.translate("OptionsDlg", u"Save", None))
#endif // QT_CONFIG(accessibility)
        self.savePostProfileButton.setText("")
#if QT_CONFIG(tooltip)
        self.renamePostProfileButton.setToolTip(QCoreApplication.translate("OptionsDlg", u"Rename", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.renamePostProfileButton.setAccessibleName(QCoreApplication.translate("OptionsDlg", u"Rename", None))
#endif // QT_CONFIG(accessibility)
        self.renamePostProfileButton.setText("")
#if QT_CONFIG(tooltip)
        self.removePostProfileButton.setToolTip(QCoreApplication.translate("OptionsDlg", u"Delete", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.removePostProfileButton.setAccessibleName(QCoreApplication.translate("OptionsDlg", u"Delete", None))
#endif // QT_CONFIG(accessibility)
        self.removePostProfileButton.setText("")
        self.postProfileErrorLabel.setText("")
        self.tabs.setTabText(self.tabs.indexOf(self.postprocessorsTab), QCoreApplication.translate("OptionsDlg", u"Postprocessors", None))
#if QT_CONFIG(tooltip)
        self.rotaryCopyButton.setToolTip(QCoreApplication.translate("OptionsDlg", u"Add", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.rotaryCopyButton.setAccessibleName(QCoreApplication.translate("OptionsDlg", u"Add", None))
#endif // QT_CONFIG(accessibility)
        self.rotaryCopyButton.setText("")
#if QT_CONFIG(tooltip)
        self.rotarySaveButton.setToolTip(QCoreApplication.translate("OptionsDlg", u"Save", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.rotarySaveButton.setAccessibleName(QCoreApplication.translate("OptionsDlg", u"Save", None))
#endif // QT_CONFIG(accessibility)
        self.rotarySaveButton.setText("")
#if QT_CONFIG(tooltip)
        self.rotaryRenameButton.setToolTip(QCoreApplication.translate("OptionsDlg", u"Rename", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.rotaryRenameButton.setAccessibleName(QCoreApplication.translate("OptionsDlg", u"Rename", None))
#endif // QT_CONFIG(accessibility)
        self.rotaryRenameButton.setText("")
#if QT_CONFIG(tooltip)
        self.rotaryDeleteButton.setToolTip(QCoreApplication.translate("OptionsDlg", u"Delete", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.rotaryDeleteButton.setAccessibleName(QCoreApplication.translate("OptionsDlg", u"Delete", None))
#endif // QT_CONFIG(accessibility)
        self.rotaryDeleteButton.setText("")
        self.rotaryProfileIdLabel.setText("")
        self.rotaryNameLabel.setText(QCoreApplication.translate("OptionsDlg", u"Profile name", None))
        self.rotaryEnabledCheck.setText(QCoreApplication.translate("OptionsDlg", u"Enabled", None))
#if QT_CONFIG(tooltip)
        self.rotaryEnabledCheck.setToolTip(QCoreApplication.translate("OptionsDlg", u"Show this profile in Settings / Rotary kinematics. Changes are applied with OK.", None))
#endif // QT_CONFIG(tooltip)
        self.rotaryStatusLabel.setText("")
        self.rotaryAxis1Group.setTitle(QCoreApplication.translate("OptionsDlg", u"Axis 1", None))
        self.rotaryBranch1Label.setText(QCoreApplication.translate("OptionsDlg", u"Table / Head", None))
        self.rotaryAddress1Label.setText(QCoreApplication.translate("OptionsDlg", u"Address", None))
        self.rotaryDirection1Label.setText(QCoreApplication.translate("OptionsDlg", u"Direction", None))
        self.rotaryX1Label.setText(QCoreApplication.translate("OptionsDlg", u"X", None))
        self.rotaryY1Label.setText(QCoreApplication.translate("OptionsDlg", u"Y", None))
        self.rotaryZ1Label.setText(QCoreApplication.translate("OptionsDlg", u"Z", None))
        self.rotaryMin1Label.setText(QCoreApplication.translate("OptionsDlg", u"Min (deg)", None))
        self.rotaryMax1Label.setText(QCoreApplication.translate("OptionsDlg", u"Max (deg)", None))
        self.rotaryAxis2Group.setTitle(QCoreApplication.translate("OptionsDlg", u"Axis 2", None))
        self.rotaryBranch2Label.setText(QCoreApplication.translate("OptionsDlg", u"Table / Head", None))
        self.rotaryAddress2Label.setText(QCoreApplication.translate("OptionsDlg", u"Address", None))
        self.rotaryDirection2Label.setText(QCoreApplication.translate("OptionsDlg", u"Direction", None))
        self.rotaryX2Label.setText(QCoreApplication.translate("OptionsDlg", u"X", None))
        self.rotaryY2Label.setText(QCoreApplication.translate("OptionsDlg", u"Y", None))
        self.rotaryZ2Label.setText(QCoreApplication.translate("OptionsDlg", u"Z", None))
        self.rotaryMin2Label.setText(QCoreApplication.translate("OptionsDlg", u"Min (deg)", None))
        self.rotaryMax2Label.setText(QCoreApplication.translate("OptionsDlg", u"Max (deg)", None))
        self.rotaryOrderLabel.setText(QCoreApplication.translate("OptionsDlg", u"Axis 1 precedes Axis 2 within each branch. Use None to omit an axis. Direction vectors must be nonzero.", None))
        self.tabs.setTabText(self.tabs.indexOf(self.rotaryTab), QCoreApplication.translate("OptionsDlg", u"Rotary Kinematics", None))
        self.discoveryModeLabel.setText(QCoreApplication.translate("OptionsDlg", u"Mode", None))
        self.discoveryModeCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"Milling", None))
        self.discoveryModeCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"Turning", None))

        self.discoveryRegexCheck.setText(QCoreApplication.translate("OptionsDlg", u"Regular expressions", None))
        self.discoveryTypesLabel.setText(QCoreApplication.translate("OptionsDlg", u"Tool types", None))
        self.discoveryNamesLabel.setText(QCoreApplication.translate("OptionsDlg", u"Tool names / Aliases", None))
        self.discoveryFormatLabel.setText("")
        self.discoveryParametersLabel.setText(QCoreApplication.translate("OptionsDlg", u"Parameters", None))
        ___qtablewidgetitem3 = self.discoveryParameterTable.horizontalHeaderItem(0)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("OptionsDlg", u"Parameter", None))
        ___qtablewidgetitem4 = self.discoveryParameterTable.horizontalHeaderItem(1)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("OptionsDlg", u"Recognition labels", None))
        self.discoveryTestLabel.setText(QCoreApplication.translate("OptionsDlg", u"Test Recognition", None))
        self.discoveryCommentLabel.setText(QCoreApplication.translate("OptionsDlg", u"Sample Comment", None))
        self.discoveryCommentEdit.setPlaceholderText(QCoreApplication.translate("OptionsDlg", u"END MILL D10 FL30", None))
        self.discoveryTestButton.setText(QCoreApplication.translate("OptionsDlg", u"Test", None))
        self.discoveryResultLabel.setText("")
        self.discoveryErrorLabel.setText("")
        self.tabs.setTabText(self.tabs.indexOf(self.toolDiscoveryTab), QCoreApplication.translate("OptionsDlg", u"Tool Discovery", None))
    # retranslateUi
