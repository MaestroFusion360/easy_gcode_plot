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
    QFontComboBox, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QSlider, QSpinBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

class Ui_OptionsDlg(object):
    def setupUi(self, OptionsDlg):
        if not OptionsDlg.objectName():
            OptionsDlg.setObjectName(u"OptionsDlg")
        OptionsDlg.resize(660, 620)
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

        self.generalForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.languageCombo)

        self.themeLabel = QLabel(self.generalTab)
        self.themeLabel.setObjectName(u"themeLabel")

        self.generalForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.themeLabel)

        self.themeCombo = QComboBox(self.generalTab)
        self.themeCombo.addItem("")
        self.themeCombo.addItem("")
        self.themeCombo.setObjectName(u"themeCombo")

        self.generalForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.themeCombo)

        self.loggingCheck = QCheckBox(self.generalTab)
        self.loggingCheck.setObjectName(u"loggingCheck")

        self.generalForm.setWidget(5, QFormLayout.ItemRole.SpanningRole, self.loggingCheck)

        self.autoUpdateCheck = QCheckBox(self.generalTab)
        self.autoUpdateCheck.setObjectName(u"autoUpdateCheck")

        self.generalForm.setWidget(6, QFormLayout.ItemRole.SpanningRole, self.autoUpdateCheck)

        self.autoUpdateMaxSegmentsLabel = QLabel(self.generalTab)
        self.autoUpdateMaxSegmentsLabel.setObjectName(u"autoUpdateMaxSegmentsLabel")

        self.generalForm.setWidget(7, QFormLayout.ItemRole.LabelRole, self.autoUpdateMaxSegmentsLabel)

        self.autoUpdateMaxSegmentsSpin = QSpinBox(self.generalTab)
        self.autoUpdateMaxSegmentsSpin.setObjectName(u"autoUpdateMaxSegmentsSpin")
        self.autoUpdateMaxSegmentsSpin.setMinimum(1000)
        self.autoUpdateMaxSegmentsSpin.setMaximum(2147483647)
        self.autoUpdateMaxSegmentsSpin.setSingleStep(5000)
        self.autoUpdateMaxSegmentsSpin.setValue(20000)

        self.generalForm.setWidget(7, QFormLayout.ItemRole.FieldRole, self.autoUpdateMaxSegmentsSpin)

        self.maxGeneratedMotionsLabel = QLabel(self.generalTab)
        self.maxGeneratedMotionsLabel.setObjectName(u"maxGeneratedMotionsLabel")

        self.generalForm.setWidget(8, QFormLayout.ItemRole.LabelRole, self.maxGeneratedMotionsLabel)

        self.maxGeneratedMotionsSpin = QSpinBox(self.generalTab)
        self.maxGeneratedMotionsSpin.setObjectName(u"maxGeneratedMotionsSpin")
        self.maxGeneratedMotionsSpin.setMinimum(1)
        self.maxGeneratedMotionsSpin.setMaximum(2147483647)
        self.maxGeneratedMotionsSpin.setSingleStep(50000)
        self.maxGeneratedMotionsSpin.setValue(200000)

        self.generalForm.setWidget(8, QFormLayout.ItemRole.FieldRole, self.maxGeneratedMotionsSpin)

        self.toolpanelIconsLabel = QLabel(self.generalTab)
        self.toolpanelIconsLabel.setObjectName(u"toolpanelIconsLabel")

        self.generalForm.setWidget(9, QFormLayout.ItemRole.LabelRole, self.toolpanelIconsLabel)

        self.toolpanelIconsCombo = QComboBox(self.generalTab)
        self.toolpanelIconsCombo.addItem("")
        self.toolpanelIconsCombo.addItem("")
        self.toolpanelIconsCombo.addItem("")
        self.toolpanelIconsCombo.setObjectName(u"toolpanelIconsCombo")

        self.generalForm.setWidget(9, QFormLayout.ItemRole.FieldRole, self.toolpanelIconsCombo)

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
        self.plotTab = QWidget()
        self.plotTab.setObjectName(u"plotTab")
        self.plotForm = QFormLayout(self.plotTab)
        self.plotForm.setObjectName(u"plotForm")
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

        self.plotForm.setWidget(2, QFormLayout.ItemRole.SpanningRole, self.axesCheck)

        self.gridCheck = QCheckBox(self.plotTab)
        self.gridCheck.setObjectName(u"gridCheck")

        self.plotForm.setWidget(3, QFormLayout.ItemRole.SpanningRole, self.gridCheck)

        self.backgroundGradientCheck = QCheckBox(self.plotTab)
        self.backgroundGradientCheck.setObjectName(u"backgroundGradientCheck")

        self.plotForm.setWidget(4, QFormLayout.ItemRole.SpanningRole, self.backgroundGradientCheck)

        self.showStockCheck = QCheckBox(self.plotTab)
        self.showStockCheck.setObjectName(u"showStockCheck")

        self.plotForm.setWidget(5, QFormLayout.ItemRole.SpanningRole, self.showStockCheck)

        self.stlWireframeCheck = QCheckBox(self.plotTab)
        self.stlWireframeCheck.setObjectName(u"stlWireframeCheck")

        self.plotForm.setWidget(6, QFormLayout.ItemRole.SpanningRole, self.stlWireframeCheck)

        self.playbackSpeedLabel = QLabel(self.plotTab)
        self.playbackSpeedLabel.setObjectName(u"playbackSpeedLabel")

        self.plotForm.setWidget(7, QFormLayout.ItemRole.LabelRole, self.playbackSpeedLabel)

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


        self.plotForm.setLayout(7, QFormLayout.ItemRole.FieldRole, self.playbackSpeedLayout)

        self.tabs.addTab(self.plotTab, "")
        self.colorsTab = QWidget()
        self.colorsTab.setObjectName(u"colorsTab")
        self.colorsForm = QFormLayout(self.colorsTab)
        self.colorsForm.setObjectName(u"colorsForm")
        self.rapidLabel = QLabel(self.colorsTab)
        self.rapidLabel.setObjectName(u"rapidLabel")

        self.colorsForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.rapidLabel)

        self.rapidColorLayout = QHBoxLayout()
        self.rapidColorLayout.setObjectName(u"rapidColorLayout")
        self.rapidColorButton = QPushButton(self.colorsTab)
        self.rapidColorButton.setObjectName(u"rapidColorButton")

        self.rapidColorLayout.addWidget(self.rapidColorButton)

        self.rapidColorEdit = QLineEdit(self.colorsTab)
        self.rapidColorEdit.setObjectName(u"rapidColorEdit")
        self.rapidColorEdit.setMaxLength(7)

        self.rapidColorLayout.addWidget(self.rapidColorEdit)


        self.colorsForm.setLayout(0, QFormLayout.ItemRole.FieldRole, self.rapidColorLayout)

        self.linearLabel = QLabel(self.colorsTab)
        self.linearLabel.setObjectName(u"linearLabel")

        self.colorsForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.linearLabel)

        self.linearColorLayout = QHBoxLayout()
        self.linearColorLayout.setObjectName(u"linearColorLayout")
        self.linearColorButton = QPushButton(self.colorsTab)
        self.linearColorButton.setObjectName(u"linearColorButton")

        self.linearColorLayout.addWidget(self.linearColorButton)

        self.linearColorEdit = QLineEdit(self.colorsTab)
        self.linearColorEdit.setObjectName(u"linearColorEdit")
        self.linearColorEdit.setMaxLength(7)

        self.linearColorLayout.addWidget(self.linearColorEdit)


        self.colorsForm.setLayout(1, QFormLayout.ItemRole.FieldRole, self.linearColorLayout)

        self.arcLabel = QLabel(self.colorsTab)
        self.arcLabel.setObjectName(u"arcLabel")

        self.colorsForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.arcLabel)

        self.arcColorLayout = QHBoxLayout()
        self.arcColorLayout.setObjectName(u"arcColorLayout")
        self.arcColorButton = QPushButton(self.colorsTab)
        self.arcColorButton.setObjectName(u"arcColorButton")

        self.arcColorLayout.addWidget(self.arcColorButton)

        self.arcColorEdit = QLineEdit(self.colorsTab)
        self.arcColorEdit.setObjectName(u"arcColorEdit")
        self.arcColorEdit.setMaxLength(7)

        self.arcColorLayout.addWidget(self.arcColorEdit)


        self.colorsForm.setLayout(2, QFormLayout.ItemRole.FieldRole, self.arcColorLayout)

        self.currentLabel = QLabel(self.colorsTab)
        self.currentLabel.setObjectName(u"currentLabel")

        self.colorsForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.currentLabel)

        self.currentColorLayout = QHBoxLayout()
        self.currentColorLayout.setObjectName(u"currentColorLayout")
        self.currentColorButton = QPushButton(self.colorsTab)
        self.currentColorButton.setObjectName(u"currentColorButton")

        self.currentColorLayout.addWidget(self.currentColorButton)

        self.currentColorEdit = QLineEdit(self.colorsTab)
        self.currentColorEdit.setObjectName(u"currentColorEdit")
        self.currentColorEdit.setMaxLength(7)

        self.currentColorLayout.addWidget(self.currentColorEdit)


        self.colorsForm.setLayout(3, QFormLayout.ItemRole.FieldRole, self.currentColorLayout)

        self.toolColorLabel = QLabel(self.colorsTab)
        self.toolColorLabel.setObjectName(u"toolColorLabel")

        self.colorsForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.toolColorLabel)

        self.toolColorLayout = QHBoxLayout()
        self.toolColorLayout.setObjectName(u"toolColorLayout")
        self.toolColorButton = QPushButton(self.colorsTab)
        self.toolColorButton.setObjectName(u"toolColorButton")

        self.toolColorLayout.addWidget(self.toolColorButton)

        self.toolColorEdit = QLineEdit(self.colorsTab)
        self.toolColorEdit.setObjectName(u"toolColorEdit")
        self.toolColorEdit.setMaxLength(7)

        self.toolColorLayout.addWidget(self.toolColorEdit)


        self.colorsForm.setLayout(4, QFormLayout.ItemRole.FieldRole, self.toolColorLayout)

        self.backgroundLabel = QLabel(self.colorsTab)
        self.backgroundLabel.setObjectName(u"backgroundLabel")

        self.colorsForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.backgroundLabel)

        self.backgroundColorLayout = QHBoxLayout()
        self.backgroundColorLayout.setObjectName(u"backgroundColorLayout")
        self.backgroundColorButton = QPushButton(self.colorsTab)
        self.backgroundColorButton.setObjectName(u"backgroundColorButton")

        self.backgroundColorLayout.addWidget(self.backgroundColorButton)

        self.backgroundColorEdit = QLineEdit(self.colorsTab)
        self.backgroundColorEdit.setObjectName(u"backgroundColorEdit")
        self.backgroundColorEdit.setMaxLength(7)

        self.backgroundColorLayout.addWidget(self.backgroundColorEdit)


        self.colorsForm.setLayout(5, QFormLayout.ItemRole.FieldRole, self.backgroundColorLayout)

        self.stlColorLabel = QLabel(self.colorsTab)
        self.stlColorLabel.setObjectName(u"stlColorLabel")

        self.colorsForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.stlColorLabel)

        self.stlColorLayout = QHBoxLayout()
        self.stlColorLayout.setObjectName(u"stlColorLayout")
        self.stlColorButton = QPushButton(self.colorsTab)
        self.stlColorButton.setObjectName(u"stlColorButton")

        self.stlColorLayout.addWidget(self.stlColorButton)

        self.stlColorEdit = QLineEdit(self.colorsTab)
        self.stlColorEdit.setObjectName(u"stlColorEdit")
        self.stlColorEdit.setMaxLength(7)

        self.stlColorLayout.addWidget(self.stlColorEdit)


        self.colorsForm.setLayout(6, QFormLayout.ItemRole.FieldRole, self.stlColorLayout)

        self.tabs.addTab(self.colorsTab, "")
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

        self.unitsLabel.setText(QCoreApplication.translate("OptionsDlg", u"Default units", None))
        self.unitsCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"Millimeters", None))
        self.unitsCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"Inches", None))

        self.languageLabel.setText(QCoreApplication.translate("OptionsDlg", u"Language", None))
        self.languageCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"English", None))
        self.languageCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"Russian", None))

        self.themeLabel.setText(QCoreApplication.translate("OptionsDlg", u"Theme", None))
        self.themeCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"Light", None))
        self.themeCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"Dark", None))

        self.loggingCheck.setText(QCoreApplication.translate("OptionsDlg", u"Enable application log", None))
        self.autoUpdateCheck.setText(QCoreApplication.translate("OptionsDlg", u"Auto update plot while editing", None))
        self.autoUpdateMaxSegmentsLabel.setText(QCoreApplication.translate("OptionsDlg", u"Auto update max segments", None))
#if QT_CONFIG(tooltip)
        self.autoUpdateMaxSegmentsSpin.setToolTip(QCoreApplication.translate("OptionsDlg", u"Maximum sampled points for automatic refresh only. Manual Update has no hidden render limit.", None))
#endif // QT_CONFIG(tooltip)
        self.maxGeneratedMotionsLabel.setText(QCoreApplication.translate("OptionsDlg", u"Maximum generated motions", None))
#if QT_CONFIG(tooltip)
        self.maxGeneratedMotionsSpin.setToolTip(QCoreApplication.translate("OptionsDlg", u"Maximum total number of motions generated by one CNC execution.", None))
#endif // QT_CONFIG(tooltip)
        self.toolpanelIconsLabel.setText(QCoreApplication.translate("OptionsDlg", u"Toolpanel icons", None))
        self.toolpanelIconsCombo.setItemText(0, QCoreApplication.translate("OptionsDlg", u"Large 32x32", None))
        self.toolpanelIconsCombo.setItemText(1, QCoreApplication.translate("OptionsDlg", u"Medium 24x24", None))
        self.toolpanelIconsCombo.setItemText(2, QCoreApplication.translate("OptionsDlg", u"Small 16x16", None))

        self.tabs.setTabText(self.tabs.indexOf(self.generalTab), QCoreApplication.translate("OptionsDlg", u"General", None))
        self.fontLabel.setText(QCoreApplication.translate("OptionsDlg", u"Font family", None))
        self.fontSizeLabel.setText(QCoreApplication.translate("OptionsDlg", u"Font size", None))
        self.caretLineCheck.setText(QCoreApplication.translate("OptionsDlg", u"Highlight current line", None))
        self.marginCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show line numbers", None))
        self.eolCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show EOL", None))
        self.whitespaceCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show whitespace", None))
        self.tabs.setTabText(self.tabs.indexOf(self.editorTab), QCoreApplication.translate("OptionsDlg", u"Editor", None))
        self.correctionCheck.setText(QCoreApplication.translate("OptionsDlg", u"Correction (G41/G42)", None))
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
        self.lineWidthLabel.setText(QCoreApplication.translate("OptionsDlg", u"Line width", None))
        self.gridStepLabel.setText(QCoreApplication.translate("OptionsDlg", u"Grid step (0 = adaptive)", None))
        self.axesCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show axes", None))
        self.gridCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show grid", None))
        self.backgroundGradientCheck.setText(QCoreApplication.translate("OptionsDlg", u"Gradient background", None))
        self.showStockCheck.setText(QCoreApplication.translate("OptionsDlg", u"Show Stock", None))
        self.stlWireframeCheck.setText(QCoreApplication.translate("OptionsDlg", u"STL edges only", None))
        self.playbackSpeedLabel.setText(QCoreApplication.translate("OptionsDlg", u"Playback speed", None))
        self.playbackSpeedValueLabel.setText(QCoreApplication.translate("OptionsDlg", u"3 \u2014 100 ms/step", None))
        self.tabs.setTabText(self.tabs.indexOf(self.plotTab), QCoreApplication.translate("OptionsDlg", u"Plot", None))
        self.rapidLabel.setText(QCoreApplication.translate("OptionsDlg", u"Rapid", None))
        self.rapidColorButton.setText("")
        self.linearLabel.setText(QCoreApplication.translate("OptionsDlg", u"Linear", None))
        self.linearColorButton.setText("")
        self.arcLabel.setText(QCoreApplication.translate("OptionsDlg", u"Arc", None))
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
        ___qtablewidgetitem = self.hotkeysTable.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("OptionsDlg", u"Command", None))
        ___qtablewidgetitem1 = self.hotkeysTable.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("OptionsDlg", u"Shortcut", None))
        ___qtablewidgetitem2 = self.hotkeysTable.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("OptionsDlg", u"Category", None))
        self.editHotkeyButton.setText(QCoreApplication.translate("OptionsDlg", u"Edit shortcut", None))
        self.tabs.setTabText(self.tabs.indexOf(self.hotkeysTab), QCoreApplication.translate("OptionsDlg", u"Hotkeys", None))
    # retranslateUi
