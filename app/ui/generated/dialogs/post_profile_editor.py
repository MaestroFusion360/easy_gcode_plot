# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'post_profile_editor.ui'
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
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QScrollArea, QSizePolicy, QSpacerItem,
    QTabWidget, QVBoxLayout, QWidget)

class Ui_PostProfileEditorDlg(object):
    def setupUi(self, PostProfileEditorDlg):
        if not PostProfileEditorDlg.objectName():
            PostProfileEditorDlg.setObjectName(u"PostProfileEditorDlg")
        PostProfileEditorDlg.resize(720, 440)
        PostProfileEditorDlg.setMinimumSize(QSize(560, 340))
        self.verticalLayout = QVBoxLayout(PostProfileEditorDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.tabs = QTabWidget(PostProfileEditorDlg)
        self.tabs.setObjectName(u"tabs")
        self.sourceTab = QWidget()
        self.sourceTab.setObjectName(u"sourceTab")
        self.sourceForm = QFormLayout(self.sourceTab)
        self.sourceForm.setObjectName(u"sourceForm")
        self.sourceForm.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.sourceForm.setFormAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
        self.sourceForm.setVerticalSpacing(4)
        self.nameEditLabel = QLabel(self.sourceTab)
        self.nameEditLabel.setObjectName(u"nameEditLabel")

        self.sourceForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.nameEditLabel)

        self.nameEdit = QLineEdit(self.sourceTab)
        self.nameEdit.setObjectName(u"nameEdit")
        self.nameEdit.setMaximumSize(QSize(320, 16777215))

        self.sourceForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.nameEdit)

        self.machineComboLabel = QLabel(self.sourceTab)
        self.machineComboLabel.setObjectName(u"machineComboLabel")

        self.sourceForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.machineComboLabel)

        self.machineCombo = QComboBox(self.sourceTab)
        self.machineCombo.addItem("")
        self.machineCombo.addItem("")
        self.machineCombo.setObjectName(u"machineCombo")
        self.machineCombo.setMaximumSize(QSize(180, 16777215))
        self.machineCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.machineCombo.setMinimumContentsLength(16)

        self.sourceForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.machineCombo)

        self.extensionEditLabel = QLabel(self.sourceTab)
        self.extensionEditLabel.setObjectName(u"extensionEditLabel")

        self.sourceForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.extensionEditLabel)

        self.extensionEdit = QLineEdit(self.sourceTab)
        self.extensionEdit.setObjectName(u"extensionEdit")
        self.extensionEdit.setMaximumSize(QSize(180, 16777215))

        self.sourceForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.extensionEdit)

        self.idLabelLabel = QLabel(self.sourceTab)
        self.idLabelLabel.setObjectName(u"idLabelLabel")

        self.sourceForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.idLabelLabel)

        self.idLabel = QLabel(self.sourceTab)
        self.idLabel.setObjectName(u"idLabel")

        self.sourceForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.idLabel)

        self.axesLayoutLabel = QLabel(self.sourceTab)
        self.axesLayoutLabel.setObjectName(u"axesLayoutLabel")

        self.sourceForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.axesLayoutLabel)

        self.axesLayout = QHBoxLayout()
        self.axesLayout.setObjectName(u"axesLayout")
        self.axisXCheck = QCheckBox(self.sourceTab)
        self.axisXCheck.setObjectName(u"axisXCheck")

        self.axesLayout.addWidget(self.axisXCheck)

        self.axisYCheck = QCheckBox(self.sourceTab)
        self.axisYCheck.setObjectName(u"axisYCheck")

        self.axesLayout.addWidget(self.axisYCheck)

        self.axisZCheck = QCheckBox(self.sourceTab)
        self.axisZCheck.setObjectName(u"axisZCheck")

        self.axesLayout.addWidget(self.axisZCheck)

        self.axisACheck = QCheckBox(self.sourceTab)
        self.axisACheck.setObjectName(u"axisACheck")

        self.axesLayout.addWidget(self.axisACheck)

        self.axisBCheck = QCheckBox(self.sourceTab)
        self.axisBCheck.setObjectName(u"axisBCheck")

        self.axesLayout.addWidget(self.axisBCheck)

        self.axisCCheck = QCheckBox(self.sourceTab)
        self.axisCCheck.setObjectName(u"axisCCheck")

        self.axesLayout.addWidget(self.axisCCheck)


        self.sourceForm.setLayout(4, QFormLayout.ItemRole.FieldRole, self.axesLayout)

        self.tabs.addTab(self.sourceTab, "")
        self.outputTab = QWidget()
        self.outputTab.setObjectName(u"outputTab")
        self.outputForm = QFormLayout(self.outputTab)
        self.outputForm.setObjectName(u"outputForm")
        self.outputForm.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.outputForm.setFormAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
        self.outputForm.setVerticalSpacing(4)
        self.unitsLabel = QLabel(self.outputTab)
        self.unitsLabel.setObjectName(u"unitsLabel")

        self.outputForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.unitsLabel)

        self.units = QComboBox(self.outputTab)
        self.units.addItem("")
        self.units.addItem("")
        self.units.setObjectName(u"units")
        self.units.setMaximumSize(QSize(180, 16777215))
        self.units.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.units.setMinimumContentsLength(16)

        self.outputForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.units)

        self.coordinatesLabel = QLabel(self.outputTab)
        self.coordinatesLabel.setObjectName(u"coordinatesLabel")

        self.outputForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.coordinatesLabel)

        self.coordinates = QComboBox(self.outputTab)
        self.coordinates.addItem("")
        self.coordinates.addItem("")
        self.coordinates.setObjectName(u"coordinates")
        self.coordinates.setMaximumSize(QSize(180, 16777215))
        self.coordinates.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.coordinates.setMinimumContentsLength(16)

        self.outputForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.coordinates)

        self.arcsLabel = QLabel(self.outputTab)
        self.arcsLabel.setObjectName(u"arcsLabel")

        self.outputForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.arcsLabel)

        self.arcs = QComboBox(self.outputTab)
        self.arcs.addItem("")
        self.arcs.addItem("")
        self.arcs.addItem("")
        self.arcs.addItem("")
        self.arcs.setObjectName(u"arcs")
        self.arcs.setMaximumSize(QSize(320, 16777215))
        self.arcs.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.arcs.setMinimumContentsLength(16)

        self.outputForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.arcs)

        self.multiTurn = QCheckBox(self.outputTab)
        self.multiTurn.setObjectName(u"multiTurn")

        self.outputForm.setWidget(3, QFormLayout.ItemRole.SpanningRole, self.multiTurn)

        self.centerSplitLabel = QLabel(self.outputTab)
        self.centerSplitLabel.setObjectName(u"centerSplitLabel")

        self.outputForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.centerSplitLabel)

        self.centerSplit = QComboBox(self.outputTab)
        self.centerSplit.addItem("")
        self.centerSplit.addItem("")
        self.centerSplit.addItem("")
        self.centerSplit.addItem("")
        self.centerSplit.addItem("")
        self.centerSplit.addItem("")
        self.centerSplit.setObjectName(u"centerSplit")
        self.centerSplit.setMaximumSize(QSize(90, 16777215))
        self.centerSplit.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.centerSplit.setMinimumContentsLength(6)

        self.outputForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.centerSplit)

        self.radiusSplitLabel = QLabel(self.outputTab)
        self.radiusSplitLabel.setObjectName(u"radiusSplitLabel")

        self.outputForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.radiusSplitLabel)

        self.radiusSplit = QComboBox(self.outputTab)
        self.radiusSplit.addItem("")
        self.radiusSplit.addItem("")
        self.radiusSplit.addItem("")
        self.radiusSplit.addItem("")
        self.radiusSplit.addItem("")
        self.radiusSplit.addItem("")
        self.radiusSplit.setObjectName(u"radiusSplit")
        self.radiusSplit.setMaximumSize(QSize(90, 16777215))
        self.radiusSplit.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.radiusSplit.setMinimumContentsLength(6)

        self.outputForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.radiusSplit)

        self.tabs.addTab(self.outputTab, "")
        self.formatTab = QWidget()
        self.formatTab.setObjectName(u"formatTab")
        self.formatForm = QFormLayout(self.formatTab)
        self.formatForm.setObjectName(u"formatForm")
        self.formatForm.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.formatForm.setFormAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
        self.formatForm.setVerticalSpacing(4)
        self.precisionLabel = QLabel(self.formatTab)
        self.precisionLabel.setObjectName(u"precisionLabel")

        self.formatForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.precisionLabel)

        self.precision = QComboBox(self.formatTab)
        self.precision.addItem("")
        self.precision.addItem("")
        self.precision.addItem("")
        self.precision.addItem("")
        self.precision.addItem("")
        self.precision.addItem("")
        self.precision.addItem("")
        self.precision.addItem("")
        self.precision.addItem("")
        self.precision.addItem("")
        self.precision.addItem("")
        self.precision.addItem("")
        self.precision.addItem("")
        self.precision.setObjectName(u"precision")
        self.precision.setMaximumSize(QSize(90, 16777215))
        self.precision.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.precision.setMinimumContentsLength(6)

        self.formatForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.precision)

        self.spaces = QCheckBox(self.formatTab)
        self.spaces.setObjectName(u"spaces")

        self.formatForm.setWidget(1, QFormLayout.ItemRole.SpanningRole, self.spaces)

        self.leadingZero = QCheckBox(self.formatTab)
        self.leadingZero.setObjectName(u"leadingZero")

        self.formatForm.setWidget(2, QFormLayout.ItemRole.SpanningRole, self.leadingZero)

        self.forceDecimal = QCheckBox(self.formatTab)
        self.forceDecimal.setObjectName(u"forceDecimal")

        self.formatForm.setWidget(3, QFormLayout.ItemRole.SpanningRole, self.forceDecimal)

        self.plusSign = QCheckBox(self.formatTab)
        self.plusSign.setObjectName(u"plusSign")

        self.formatForm.setWidget(4, QFormLayout.ItemRole.SpanningRole, self.plusSign)

        self.tabs.addTab(self.formatTab, "")
        self.sequencingTab = QWidget()
        self.sequencingTab.setObjectName(u"sequencingTab")
        self.sequencingLayout = QVBoxLayout(self.sequencingTab)
        self.sequencingLayout.setObjectName(u"sequencingLayout")
        self.sequencingHint = QLabel(self.sequencingTab)
        self.sequencingHint.setObjectName(u"sequencingHint")

        self.sequencingLayout.addWidget(self.sequencingHint)

        self.addressOrder = QWidget(self.sequencingTab)
        self.addressOrder.setObjectName(u"addressOrder")
        self.addressOrder.setMinimumSize(QSize(0, 120))
        self.addressOrder.setMaximumSize(QSize(16777215, 156))

        self.sequencingLayout.addWidget(self.addressOrder)

        self.selectedAddressLabel = QLabel(self.sequencingTab)
        self.selectedAddressLabel.setObjectName(u"selectedAddressLabel")

        self.sequencingLayout.addWidget(self.selectedAddressLabel)

        self.sequencingForm = QFormLayout()
        self.sequencingForm.setObjectName(u"sequencingForm")
        self.sequencingForm.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.sequencingForm.setFormAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
        self.sequencingForm.setVerticalSpacing(4)
        self.addressPrecisionLabel = QLabel(self.sequencingTab)
        self.addressPrecisionLabel.setObjectName(u"addressPrecisionLabel")

        self.sequencingForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.addressPrecisionLabel)

        self.addressPrecision = QComboBox(self.sequencingTab)
        self.addressPrecision.addItem("")
        self.addressPrecision.addItem("")
        self.addressPrecision.addItem("")
        self.addressPrecision.addItem("")
        self.addressPrecision.addItem("")
        self.addressPrecision.addItem("")
        self.addressPrecision.addItem("")
        self.addressPrecision.addItem("")
        self.addressPrecision.addItem("")
        self.addressPrecision.addItem("")
        self.addressPrecision.addItem("")
        self.addressPrecision.addItem("")
        self.addressPrecision.addItem("")
        self.addressPrecision.addItem("")
        self.addressPrecision.setObjectName(u"addressPrecision")
        self.addressPrecision.setMaximumSize(QSize(210, 16777215))
        self.addressPrecision.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.addressPrecision.setMinimumContentsLength(16)

        self.sequencingForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.addressPrecision)

        self.addressSignLabel = QLabel(self.sequencingTab)
        self.addressSignLabel.setObjectName(u"addressSignLabel")

        self.sequencingForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.addressSignLabel)

        self.addressSign = QComboBox(self.sequencingTab)
        self.addressSign.addItem("")
        self.addressSign.addItem("")
        self.addressSign.addItem("")
        self.addressSign.addItem("")
        self.addressSign.setObjectName(u"addressSign")
        self.addressSign.setMaximumSize(QSize(210, 16777215))
        self.addressSign.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.addressSign.setMinimumContentsLength(16)

        self.sequencingForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.addressSign)

        self.addressRequiredLabel = QLabel(self.sequencingTab)
        self.addressRequiredLabel.setObjectName(u"addressRequiredLabel")

        self.sequencingForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.addressRequiredLabel)

        self.addressRequired = QComboBox(self.sequencingTab)
        self.addressRequired.addItem("")
        self.addressRequired.addItem("")
        self.addressRequired.setObjectName(u"addressRequired")
        self.addressRequired.setMaximumSize(QSize(210, 16777215))
        self.addressRequired.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.addressRequired.setMinimumContentsLength(16)

        self.sequencingForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.addressRequired)


        self.sequencingLayout.addLayout(self.sequencingForm)

        self.sequencingSpacer = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.sequencingLayout.addItem(self.sequencingSpacer)

        self.tabs.addTab(self.sequencingTab, "")
        self.motionsTab = QWidget()
        self.motionsTab.setObjectName(u"motionsTab")
        self.motionsTabLayout = QVBoxLayout(self.motionsTab)
        self.motionsTabLayout.setObjectName(u"motionsTabLayout")
        self.motionsTabScroll = QScrollArea(self.motionsTab)
        self.motionsTabScroll.setObjectName(u"motionsTabScroll")
        self.motionsTabScroll.setFrameShape(QFrame.Shape.NoFrame)
        self.motionsTabScroll.setWidgetResizable(True)
        self.motionsTabContents = QWidget()
        self.motionsTabContents.setObjectName(u"motionsTabContents")
        self.motionsTabContents.setGeometry(QRect(0, 0, 640, 430))
        self.motionsForm = QFormLayout(self.motionsTabContents)
        self.motionsForm.setObjectName(u"motionsForm")
        self.motionsForm.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.motionsForm.setFormAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
        self.motionsForm.setVerticalSpacing(4)
        self.rapidMoveEditLabel = QLabel(self.motionsTabContents)
        self.rapidMoveEditLabel.setObjectName(u"rapidMoveEditLabel")

        self.motionsForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.rapidMoveEditLabel)

        self.rapidMoveEdit = QLineEdit(self.motionsTabContents)
        self.rapidMoveEdit.setObjectName(u"rapidMoveEdit")
        self.rapidMoveEdit.setMaximumSize(QSize(320, 16777215))

        self.motionsForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.rapidMoveEdit)

        self.linearMoveEditLabel = QLabel(self.motionsTabContents)
        self.linearMoveEditLabel.setObjectName(u"linearMoveEditLabel")

        self.motionsForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.linearMoveEditLabel)

        self.linearMoveEdit = QLineEdit(self.motionsTabContents)
        self.linearMoveEdit.setObjectName(u"linearMoveEdit")
        self.linearMoveEdit.setMaximumSize(QSize(320, 16777215))

        self.motionsForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.linearMoveEdit)

        self.circularMoveCWEditLabel = QLabel(self.motionsTabContents)
        self.circularMoveCWEditLabel.setObjectName(u"circularMoveCWEditLabel")

        self.motionsForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.circularMoveCWEditLabel)

        self.circularMoveCWEdit = QLineEdit(self.motionsTabContents)
        self.circularMoveCWEdit.setObjectName(u"circularMoveCWEdit")
        self.circularMoveCWEdit.setMaximumSize(QSize(320, 16777215))

        self.motionsForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.circularMoveCWEdit)

        self.circularMoveCCWEditLabel = QLabel(self.motionsTabContents)
        self.circularMoveCCWEditLabel.setObjectName(u"circularMoveCCWEditLabel")

        self.motionsForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.circularMoveCCWEditLabel)

        self.circularMoveCCWEdit = QLineEdit(self.motionsTabContents)
        self.circularMoveCCWEdit.setObjectName(u"circularMoveCCWEdit")
        self.circularMoveCCWEdit.setMaximumSize(QSize(320, 16777215))

        self.motionsForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.circularMoveCCWEdit)

        self.planeXYEditLabel = QLabel(self.motionsTabContents)
        self.planeXYEditLabel.setObjectName(u"planeXYEditLabel")

        self.motionsForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.planeXYEditLabel)

        self.planeXYEdit = QLineEdit(self.motionsTabContents)
        self.planeXYEdit.setObjectName(u"planeXYEdit")
        self.planeXYEdit.setMaximumSize(QSize(320, 16777215))

        self.motionsForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.planeXYEdit)

        self.planeXZEditLabel = QLabel(self.motionsTabContents)
        self.planeXZEditLabel.setObjectName(u"planeXZEditLabel")

        self.motionsForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.planeXZEditLabel)

        self.planeXZEdit = QLineEdit(self.motionsTabContents)
        self.planeXZEdit.setObjectName(u"planeXZEdit")
        self.planeXZEdit.setMaximumSize(QSize(320, 16777215))

        self.motionsForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.planeXZEdit)

        self.planeYZEditLabel = QLabel(self.motionsTabContents)
        self.planeYZEditLabel.setObjectName(u"planeYZEditLabel")

        self.motionsForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.planeYZEditLabel)

        self.planeYZEdit = QLineEdit(self.motionsTabContents)
        self.planeYZEdit.setObjectName(u"planeYZEdit")
        self.planeYZEdit.setMaximumSize(QSize(320, 16777215))

        self.motionsForm.setWidget(6, QFormLayout.ItemRole.FieldRole, self.planeYZEdit)

        self.threadMoveEditLabel = QLabel(self.motionsTabContents)
        self.threadMoveEditLabel.setObjectName(u"threadMoveEditLabel")

        self.motionsForm.setWidget(7, QFormLayout.ItemRole.LabelRole, self.threadMoveEditLabel)

        self.threadMoveEdit = QLineEdit(self.motionsTabContents)
        self.threadMoveEdit.setObjectName(u"threadMoveEdit")
        self.threadMoveEdit.setMaximumSize(QSize(320, 16777215))

        self.motionsForm.setWidget(7, QFormLayout.ItemRole.FieldRole, self.threadMoveEdit)

        self.absoluteEditLabel = QLabel(self.motionsTabContents)
        self.absoluteEditLabel.setObjectName(u"absoluteEditLabel")

        self.motionsForm.setWidget(8, QFormLayout.ItemRole.LabelRole, self.absoluteEditLabel)

        self.absoluteEdit = QLineEdit(self.motionsTabContents)
        self.absoluteEdit.setObjectName(u"absoluteEdit")
        self.absoluteEdit.setMaximumSize(QSize(320, 16777215))

        self.motionsForm.setWidget(8, QFormLayout.ItemRole.FieldRole, self.absoluteEdit)

        self.incrementalEditLabel = QLabel(self.motionsTabContents)
        self.incrementalEditLabel.setObjectName(u"incrementalEditLabel")

        self.motionsForm.setWidget(9, QFormLayout.ItemRole.LabelRole, self.incrementalEditLabel)

        self.incrementalEdit = QLineEdit(self.motionsTabContents)
        self.incrementalEdit.setObjectName(u"incrementalEdit")
        self.incrementalEdit.setMaximumSize(QSize(320, 16777215))

        self.motionsForm.setWidget(9, QFormLayout.ItemRole.FieldRole, self.incrementalEdit)

        self.referenceRapidEditLabel = QLabel(self.motionsTabContents)
        self.referenceRapidEditLabel.setObjectName(u"referenceRapidEditLabel")

        self.motionsForm.setWidget(10, QFormLayout.ItemRole.LabelRole, self.referenceRapidEditLabel)

        self.referenceRapidEdit = QLineEdit(self.motionsTabContents)
        self.referenceRapidEdit.setObjectName(u"referenceRapidEdit")
        self.referenceRapidEdit.setMaximumSize(QSize(320, 16777215))

        self.motionsForm.setWidget(10, QFormLayout.ItemRole.FieldRole, self.referenceRapidEdit)

        self.referenceLinearEditLabel = QLabel(self.motionsTabContents)
        self.referenceLinearEditLabel.setObjectName(u"referenceLinearEditLabel")

        self.motionsForm.setWidget(11, QFormLayout.ItemRole.LabelRole, self.referenceLinearEditLabel)

        self.referenceLinearEdit = QLineEdit(self.motionsTabContents)
        self.referenceLinearEdit.setObjectName(u"referenceLinearEdit")
        self.referenceLinearEdit.setMaximumSize(QSize(320, 16777215))

        self.motionsForm.setWidget(11, QFormLayout.ItemRole.FieldRole, self.referenceLinearEdit)

        self.motionsTabScroll.setWidget(self.motionsTabContents)

        self.motionsTabLayout.addWidget(self.motionsTabScroll)

        self.tabs.addTab(self.motionsTab, "")
        self.homeTab = QWidget()
        self.homeTab.setObjectName(u"homeTab")
        self.homeTabLayout = QVBoxLayout(self.homeTab)
        self.homeTabLayout.setObjectName(u"homeTabLayout")
        self.homeTabScroll = QScrollArea(self.homeTab)
        self.homeTabScroll.setObjectName(u"homeTabScroll")
        self.homeTabScroll.setFrameShape(QFrame.Shape.NoFrame)
        self.homeTabScroll.setWidgetResizable(True)
        self.homeTabContents = QWidget()
        self.homeTabContents.setObjectName(u"homeTabContents")
        self.homeTabContents.setGeometry(QRect(0, 0, 640, 360))
        self.homeForm = QFormLayout(self.homeTabContents)
        self.homeForm.setObjectName(u"homeForm")
        self.homeForm.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.homeForm.setFormAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
        self.homeForm.setVerticalSpacing(4)
        self.homeG28AllEditLabel = QLabel(self.homeTabContents)
        self.homeG28AllEditLabel.setObjectName(u"homeG28AllEditLabel")

        self.homeForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.homeG28AllEditLabel)

        self.homeG28AllEdit = QLineEdit(self.homeTabContents)
        self.homeG28AllEdit.setObjectName(u"homeG28AllEdit")
        self.homeG28AllEdit.setMaximumSize(QSize(320, 16777215))

        self.homeForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.homeG28AllEdit)

        self.homeG28XEditLabel = QLabel(self.homeTabContents)
        self.homeG28XEditLabel.setObjectName(u"homeG28XEditLabel")

        self.homeForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.homeG28XEditLabel)

        self.homeG28XEdit = QLineEdit(self.homeTabContents)
        self.homeG28XEdit.setObjectName(u"homeG28XEdit")
        self.homeG28XEdit.setMaximumSize(QSize(320, 16777215))

        self.homeForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.homeG28XEdit)

        self.homeG28YEditLabel = QLabel(self.homeTabContents)
        self.homeG28YEditLabel.setObjectName(u"homeG28YEditLabel")

        self.homeForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.homeG28YEditLabel)

        self.homeG28YEdit = QLineEdit(self.homeTabContents)
        self.homeG28YEdit.setObjectName(u"homeG28YEdit")
        self.homeG28YEdit.setMaximumSize(QSize(320, 16777215))

        self.homeForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.homeG28YEdit)

        self.homeG28ZEditLabel = QLabel(self.homeTabContents)
        self.homeG28ZEditLabel.setObjectName(u"homeG28ZEditLabel")

        self.homeForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.homeG28ZEditLabel)

        self.homeG28ZEdit = QLineEdit(self.homeTabContents)
        self.homeG28ZEdit.setObjectName(u"homeG28ZEdit")
        self.homeG28ZEdit.setMaximumSize(QSize(320, 16777215))

        self.homeForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.homeG28ZEdit)

        self.homeG53AllEditLabel = QLabel(self.homeTabContents)
        self.homeG53AllEditLabel.setObjectName(u"homeG53AllEditLabel")

        self.homeForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.homeG53AllEditLabel)

        self.homeG53AllEdit = QLineEdit(self.homeTabContents)
        self.homeG53AllEdit.setObjectName(u"homeG53AllEdit")
        self.homeG53AllEdit.setMaximumSize(QSize(320, 16777215))

        self.homeForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.homeG53AllEdit)

        self.homeG53XEditLabel = QLabel(self.homeTabContents)
        self.homeG53XEditLabel.setObjectName(u"homeG53XEditLabel")

        self.homeForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.homeG53XEditLabel)

        self.homeG53XEdit = QLineEdit(self.homeTabContents)
        self.homeG53XEdit.setObjectName(u"homeG53XEdit")
        self.homeG53XEdit.setMaximumSize(QSize(320, 16777215))

        self.homeForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.homeG53XEdit)

        self.homeG53YEditLabel = QLabel(self.homeTabContents)
        self.homeG53YEditLabel.setObjectName(u"homeG53YEditLabel")

        self.homeForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.homeG53YEditLabel)

        self.homeG53YEdit = QLineEdit(self.homeTabContents)
        self.homeG53YEdit.setObjectName(u"homeG53YEdit")
        self.homeG53YEdit.setMaximumSize(QSize(320, 16777215))

        self.homeForm.setWidget(6, QFormLayout.ItemRole.FieldRole, self.homeG53YEdit)

        self.homeG53ZEditLabel = QLabel(self.homeTabContents)
        self.homeG53ZEditLabel.setObjectName(u"homeG53ZEditLabel")

        self.homeForm.setWidget(7, QFormLayout.ItemRole.LabelRole, self.homeG53ZEditLabel)

        self.homeG53ZEdit = QLineEdit(self.homeTabContents)
        self.homeG53ZEdit.setObjectName(u"homeG53ZEdit")
        self.homeG53ZEdit.setMaximumSize(QSize(320, 16777215))

        self.homeForm.setWidget(7, QFormLayout.ItemRole.FieldRole, self.homeG53ZEdit)

        self.homeTabScroll.setWidget(self.homeTabContents)

        self.homeTabLayout.addWidget(self.homeTabScroll)

        self.tabs.addTab(self.homeTab, "")
        self.cyclesTab = QWidget()
        self.cyclesTab.setObjectName(u"cyclesTab")
        self.cyclesTabLayout = QVBoxLayout(self.cyclesTab)
        self.cyclesTabLayout.setObjectName(u"cyclesTabLayout")
        self.cyclesTabScroll = QScrollArea(self.cyclesTab)
        self.cyclesTabScroll.setObjectName(u"cyclesTabScroll")
        self.cyclesTabScroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cyclesTabScroll.setWidgetResizable(True)
        self.cyclesTabContents = QWidget()
        self.cyclesTabContents.setObjectName(u"cyclesTabContents")
        self.cyclesTabContents.setGeometry(QRect(0, 0, 640, 700))
        self.cyclesForm = QFormLayout(self.cyclesTabContents)
        self.cyclesForm.setObjectName(u"cyclesForm")
        self.cyclesForm.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.cyclesForm.setFormAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
        self.cyclesForm.setVerticalSpacing(4)
        self.cyclesSyntaxComboLabel = QLabel(self.cyclesTabContents)
        self.cyclesSyntaxComboLabel.setObjectName(u"cyclesSyntaxComboLabel")

        self.cyclesForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.cyclesSyntaxComboLabel)

        self.cyclesSyntaxCombo = QComboBox(self.cyclesTabContents)
        self.cyclesSyntaxCombo.addItem("")
        self.cyclesSyntaxCombo.addItem("")
        self.cyclesSyntaxCombo.setObjectName(u"cyclesSyntaxCombo")
        self.cyclesSyntaxCombo.setMaximumSize(QSize(320, 16777215))
        self.cyclesSyntaxCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.cyclesSyntaxCombo.setMinimumContentsLength(16)

        self.cyclesForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.cyclesSyntaxCombo)

        self.cyclesCancelEditLabel = QLabel(self.cyclesTabContents)
        self.cyclesCancelEditLabel.setObjectName(u"cyclesCancelEditLabel")

        self.cyclesForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.cyclesCancelEditLabel)

        self.cyclesCancelEdit = QLineEdit(self.cyclesTabContents)
        self.cyclesCancelEdit.setObjectName(u"cyclesCancelEdit")
        self.cyclesCancelEdit.setMaximumSize(QSize(320, 16777215))

        self.cyclesForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.cyclesCancelEdit)

        self.cyclesReturnInitialEditLabel = QLabel(self.cyclesTabContents)
        self.cyclesReturnInitialEditLabel.setObjectName(u"cyclesReturnInitialEditLabel")

        self.cyclesForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.cyclesReturnInitialEditLabel)

        self.cyclesReturnInitialEdit = QLineEdit(self.cyclesTabContents)
        self.cyclesReturnInitialEdit.setObjectName(u"cyclesReturnInitialEdit")
        self.cyclesReturnInitialEdit.setMaximumSize(QSize(320, 16777215))

        self.cyclesForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.cyclesReturnInitialEdit)

        self.cyclesReturnSafetyEditLabel = QLabel(self.cyclesTabContents)
        self.cyclesReturnSafetyEditLabel.setObjectName(u"cyclesReturnSafetyEditLabel")

        self.cyclesForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.cyclesReturnSafetyEditLabel)

        self.cyclesReturnSafetyEdit = QLineEdit(self.cyclesTabContents)
        self.cyclesReturnSafetyEdit.setObjectName(u"cyclesReturnSafetyEdit")
        self.cyclesReturnSafetyEdit.setMaximumSize(QSize(320, 16777215))

        self.cyclesForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.cyclesReturnSafetyEdit)

        self.cyclesRigidTapEditLabel = QLabel(self.cyclesTabContents)
        self.cyclesRigidTapEditLabel.setObjectName(u"cyclesRigidTapEditLabel")

        self.cyclesForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.cyclesRigidTapEditLabel)

        self.cyclesRigidTapEdit = QLineEdit(self.cyclesTabContents)
        self.cyclesRigidTapEdit.setObjectName(u"cyclesRigidTapEdit")
        self.cyclesRigidTapEdit.setMaximumSize(QSize(320, 16777215))

        self.cyclesForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.cyclesRigidTapEdit)

        self.cyclesDrillEditLabel = QLabel(self.cyclesTabContents)
        self.cyclesDrillEditLabel.setObjectName(u"cyclesDrillEditLabel")

        self.cyclesForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.cyclesDrillEditLabel)

        self.cyclesDrillEdit = QPlainTextEdit(self.cyclesTabContents)
        self.cyclesDrillEdit.setObjectName(u"cyclesDrillEdit")
        self.cyclesDrillEdit.setMaximumSize(QSize(320, 48))
        self.cyclesDrillEdit.setMinimumSize(QSize(0, 36))

        self.cyclesForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.cyclesDrillEdit)

        self.cyclesDrillDwellEditLabel = QLabel(self.cyclesTabContents)
        self.cyclesDrillDwellEditLabel.setObjectName(u"cyclesDrillDwellEditLabel")

        self.cyclesForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.cyclesDrillDwellEditLabel)

        self.cyclesDrillDwellEdit = QPlainTextEdit(self.cyclesTabContents)
        self.cyclesDrillDwellEdit.setObjectName(u"cyclesDrillDwellEdit")
        self.cyclesDrillDwellEdit.setMaximumSize(QSize(320, 48))
        self.cyclesDrillDwellEdit.setMinimumSize(QSize(0, 36))

        self.cyclesForm.setWidget(6, QFormLayout.ItemRole.FieldRole, self.cyclesDrillDwellEdit)

        self.cyclesPeckDrillEditLabel = QLabel(self.cyclesTabContents)
        self.cyclesPeckDrillEditLabel.setObjectName(u"cyclesPeckDrillEditLabel")

        self.cyclesForm.setWidget(7, QFormLayout.ItemRole.LabelRole, self.cyclesPeckDrillEditLabel)

        self.cyclesPeckDrillEdit = QPlainTextEdit(self.cyclesTabContents)
        self.cyclesPeckDrillEdit.setObjectName(u"cyclesPeckDrillEdit")
        self.cyclesPeckDrillEdit.setMaximumSize(QSize(320, 48))
        self.cyclesPeckDrillEdit.setMinimumSize(QSize(0, 36))

        self.cyclesForm.setWidget(7, QFormLayout.ItemRole.FieldRole, self.cyclesPeckDrillEdit)

        self.cyclesHighSpeedPeckEditLabel = QLabel(self.cyclesTabContents)
        self.cyclesHighSpeedPeckEditLabel.setObjectName(u"cyclesHighSpeedPeckEditLabel")

        self.cyclesForm.setWidget(8, QFormLayout.ItemRole.LabelRole, self.cyclesHighSpeedPeckEditLabel)

        self.cyclesHighSpeedPeckEdit = QPlainTextEdit(self.cyclesTabContents)
        self.cyclesHighSpeedPeckEdit.setObjectName(u"cyclesHighSpeedPeckEdit")
        self.cyclesHighSpeedPeckEdit.setMaximumSize(QSize(320, 48))
        self.cyclesHighSpeedPeckEdit.setMinimumSize(QSize(0, 36))

        self.cyclesForm.setWidget(8, QFormLayout.ItemRole.FieldRole, self.cyclesHighSpeedPeckEdit)

        self.cyclesTapEditLabel = QLabel(self.cyclesTabContents)
        self.cyclesTapEditLabel.setObjectName(u"cyclesTapEditLabel")

        self.cyclesForm.setWidget(9, QFormLayout.ItemRole.LabelRole, self.cyclesTapEditLabel)

        self.cyclesTapEdit = QPlainTextEdit(self.cyclesTabContents)
        self.cyclesTapEdit.setObjectName(u"cyclesTapEdit")
        self.cyclesTapEdit.setMaximumSize(QSize(320, 48))
        self.cyclesTapEdit.setMinimumSize(QSize(0, 36))

        self.cyclesForm.setWidget(9, QFormLayout.ItemRole.FieldRole, self.cyclesTapEdit)

        self.cyclesBoreFeedEditLabel = QLabel(self.cyclesTabContents)
        self.cyclesBoreFeedEditLabel.setObjectName(u"cyclesBoreFeedEditLabel")

        self.cyclesForm.setWidget(10, QFormLayout.ItemRole.LabelRole, self.cyclesBoreFeedEditLabel)

        self.cyclesBoreFeedEdit = QPlainTextEdit(self.cyclesTabContents)
        self.cyclesBoreFeedEdit.setObjectName(u"cyclesBoreFeedEdit")
        self.cyclesBoreFeedEdit.setMaximumSize(QSize(320, 48))
        self.cyclesBoreFeedEdit.setMinimumSize(QSize(0, 36))

        self.cyclesForm.setWidget(10, QFormLayout.ItemRole.FieldRole, self.cyclesBoreFeedEdit)

        self.cyclesBoreStopEditLabel = QLabel(self.cyclesTabContents)
        self.cyclesBoreStopEditLabel.setObjectName(u"cyclesBoreStopEditLabel")

        self.cyclesForm.setWidget(11, QFormLayout.ItemRole.LabelRole, self.cyclesBoreStopEditLabel)

        self.cyclesBoreStopEdit = QPlainTextEdit(self.cyclesTabContents)
        self.cyclesBoreStopEdit.setObjectName(u"cyclesBoreStopEdit")
        self.cyclesBoreStopEdit.setMaximumSize(QSize(320, 48))
        self.cyclesBoreStopEdit.setMinimumSize(QSize(0, 36))

        self.cyclesForm.setWidget(11, QFormLayout.ItemRole.FieldRole, self.cyclesBoreStopEdit)

        self.nativeCycleCallEditLabel = QLabel(self.cyclesTabContents)
        self.nativeCycleCallEditLabel.setObjectName(u"nativeCycleCallEditLabel")

        self.cyclesForm.setWidget(12, QFormLayout.ItemRole.LabelRole, self.nativeCycleCallEditLabel)

        self.nativeCycleCallEdit = QLineEdit(self.cyclesTabContents)
        self.nativeCycleCallEdit.setObjectName(u"nativeCycleCallEdit")

        self.cyclesForm.setWidget(12, QFormLayout.ItemRole.FieldRole, self.nativeCycleCallEdit)

        self.nativeDwellDefinitionEditLabel = QLabel(self.cyclesTabContents)
        self.nativeDwellDefinitionEditLabel.setObjectName(u"nativeDwellDefinitionEditLabel")

        self.cyclesForm.setWidget(13, QFormLayout.ItemRole.LabelRole, self.nativeDwellDefinitionEditLabel)

        self.nativeDwellDefinitionEdit = QLineEdit(self.cyclesTabContents)
        self.nativeDwellDefinitionEdit.setObjectName(u"nativeDwellDefinitionEdit")

        self.cyclesForm.setWidget(13, QFormLayout.ItemRole.FieldRole, self.nativeDwellDefinitionEdit)

        self.cyclesTabScroll.setWidget(self.cyclesTabContents)

        self.cyclesTabLayout.addWidget(self.cyclesTabScroll)

        self.tabs.addTab(self.cyclesTab, "")
        self.commandsTab = QWidget()
        self.commandsTab.setObjectName(u"commandsTab")
        self.commandsTabLayout = QVBoxLayout(self.commandsTab)
        self.commandsTabLayout.setObjectName(u"commandsTabLayout")
        self.commandsTabScroll = QScrollArea(self.commandsTab)
        self.commandsTabScroll.setObjectName(u"commandsTabScroll")
        self.commandsTabScroll.setFrameShape(QFrame.Shape.NoFrame)
        self.commandsTabScroll.setWidgetResizable(True)
        self.commandsTabContents = QWidget()
        self.commandsTabContents.setObjectName(u"commandsTabContents")
        self.commandsTabContents.setGeometry(QRect(0, 0, 640, 560))
        self.commandsForm = QFormLayout(self.commandsTabContents)
        self.commandsForm.setObjectName(u"commandsForm")
        self.commandsForm.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.commandsForm.setFormAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
        self.commandsForm.setVerticalSpacing(4)
        self.toolChangeEditLabel = QLabel(self.commandsTabContents)
        self.toolChangeEditLabel.setObjectName(u"toolChangeEditLabel")

        self.commandsForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.toolChangeEditLabel)

        self.toolChangeEdit = QLineEdit(self.commandsTabContents)
        self.toolChangeEdit.setObjectName(u"toolChangeEdit")
        self.toolChangeEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.toolChangeEdit)

        self.spindleCWEditLabel = QLabel(self.commandsTabContents)
        self.spindleCWEditLabel.setObjectName(u"spindleCWEditLabel")

        self.commandsForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.spindleCWEditLabel)

        self.spindleCWEdit = QLineEdit(self.commandsTabContents)
        self.spindleCWEdit.setObjectName(u"spindleCWEdit")
        self.spindleCWEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.spindleCWEdit)

        self.spindleCCWEditLabel = QLabel(self.commandsTabContents)
        self.spindleCCWEditLabel.setObjectName(u"spindleCCWEditLabel")

        self.commandsForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.spindleCCWEditLabel)

        self.spindleCCWEdit = QLineEdit(self.commandsTabContents)
        self.spindleCCWEdit.setObjectName(u"spindleCCWEdit")
        self.spindleCCWEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.spindleCCWEdit)

        self.spindleStopEditLabel = QLabel(self.commandsTabContents)
        self.spindleStopEditLabel.setObjectName(u"spindleStopEditLabel")

        self.commandsForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.spindleStopEditLabel)

        self.spindleStopEdit = QLineEdit(self.commandsTabContents)
        self.spindleStopEdit.setObjectName(u"spindleStopEdit")
        self.spindleStopEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.spindleStopEdit)

        self.spindleCSSOnEditLabel = QLabel(self.commandsTabContents)
        self.spindleCSSOnEditLabel.setObjectName(u"spindleCSSOnEditLabel")

        self.commandsForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.spindleCSSOnEditLabel)

        self.spindleCSSOnEdit = QLineEdit(self.commandsTabContents)
        self.spindleCSSOnEdit.setObjectName(u"spindleCSSOnEdit")
        self.spindleCSSOnEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.spindleCSSOnEdit)

        self.spindleCSSOffEditLabel = QLabel(self.commandsTabContents)
        self.spindleCSSOffEditLabel.setObjectName(u"spindleCSSOffEditLabel")

        self.commandsForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.spindleCSSOffEditLabel)

        self.spindleCSSOffEdit = QLineEdit(self.commandsTabContents)
        self.spindleCSSOffEdit.setObjectName(u"spindleCSSOffEdit")
        self.spindleCSSOffEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.spindleCSSOffEdit)

        self.spindleMaxSpeedEditLabel = QLabel(self.commandsTabContents)
        self.spindleMaxSpeedEditLabel.setObjectName(u"spindleMaxSpeedEditLabel")

        self.commandsForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.spindleMaxSpeedEditLabel)

        self.spindleMaxSpeedEdit = QLineEdit(self.commandsTabContents)
        self.spindleMaxSpeedEdit.setObjectName(u"spindleMaxSpeedEdit")
        self.spindleMaxSpeedEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(6, QFormLayout.ItemRole.FieldRole, self.spindleMaxSpeedEdit)

        self.coolantMistEditLabel = QLabel(self.commandsTabContents)
        self.coolantMistEditLabel.setObjectName(u"coolantMistEditLabel")

        self.commandsForm.setWidget(7, QFormLayout.ItemRole.LabelRole, self.coolantMistEditLabel)

        self.coolantMistEdit = QLineEdit(self.commandsTabContents)
        self.coolantMistEdit.setObjectName(u"coolantMistEdit")
        self.coolantMistEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(7, QFormLayout.ItemRole.FieldRole, self.coolantMistEdit)

        self.coolantFloodEditLabel = QLabel(self.commandsTabContents)
        self.coolantFloodEditLabel.setObjectName(u"coolantFloodEditLabel")

        self.commandsForm.setWidget(8, QFormLayout.ItemRole.LabelRole, self.coolantFloodEditLabel)

        self.coolantFloodEdit = QLineEdit(self.commandsTabContents)
        self.coolantFloodEdit.setObjectName(u"coolantFloodEdit")
        self.coolantFloodEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(8, QFormLayout.ItemRole.FieldRole, self.coolantFloodEdit)

        self.coolantOffEditLabel = QLabel(self.commandsTabContents)
        self.coolantOffEditLabel.setObjectName(u"coolantOffEditLabel")

        self.commandsForm.setWidget(9, QFormLayout.ItemRole.LabelRole, self.coolantOffEditLabel)

        self.coolantOffEdit = QLineEdit(self.commandsTabContents)
        self.coolantOffEdit.setObjectName(u"coolantOffEdit")
        self.coolantOffEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(9, QFormLayout.ItemRole.FieldRole, self.coolantOffEdit)

        self.feedPerMinuteEditLabel = QLabel(self.commandsTabContents)
        self.feedPerMinuteEditLabel.setObjectName(u"feedPerMinuteEditLabel")

        self.commandsForm.setWidget(10, QFormLayout.ItemRole.LabelRole, self.feedPerMinuteEditLabel)

        self.feedPerMinuteEdit = QLineEdit(self.commandsTabContents)
        self.feedPerMinuteEdit.setObjectName(u"feedPerMinuteEdit")
        self.feedPerMinuteEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(10, QFormLayout.ItemRole.FieldRole, self.feedPerMinuteEdit)

        self.feedPerRevEditLabel = QLabel(self.commandsTabContents)
        self.feedPerRevEditLabel.setObjectName(u"feedPerRevEditLabel")

        self.commandsForm.setWidget(11, QFormLayout.ItemRole.LabelRole, self.feedPerRevEditLabel)

        self.feedPerRevEdit = QLineEdit(self.commandsTabContents)
        self.feedPerRevEdit.setObjectName(u"feedPerRevEdit")
        self.feedPerRevEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(11, QFormLayout.ItemRole.FieldRole, self.feedPerRevEdit)

        self.feedInverseTimeEditLabel = QLabel(self.commandsTabContents)
        self.feedInverseTimeEditLabel.setObjectName(u"feedInverseTimeEditLabel")

        self.commandsForm.setWidget(12, QFormLayout.ItemRole.LabelRole, self.feedInverseTimeEditLabel)

        self.feedInverseTimeEdit = QLineEdit(self.commandsTabContents)
        self.feedInverseTimeEdit.setObjectName(u"feedInverseTimeEdit")
        self.feedInverseTimeEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(12, QFormLayout.ItemRole.FieldRole, self.feedInverseTimeEdit)

        self.unitsInchEditLabel = QLabel(self.commandsTabContents)
        self.unitsInchEditLabel.setObjectName(u"unitsInchEditLabel")

        self.commandsForm.setWidget(13, QFormLayout.ItemRole.LabelRole, self.unitsInchEditLabel)

        self.unitsInchEdit = QLineEdit(self.commandsTabContents)
        self.unitsInchEdit.setObjectName(u"unitsInchEdit")
        self.unitsInchEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(13, QFormLayout.ItemRole.FieldRole, self.unitsInchEdit)

        self.unitsMetricEditLabel = QLabel(self.commandsTabContents)
        self.unitsMetricEditLabel.setObjectName(u"unitsMetricEditLabel")

        self.commandsForm.setWidget(14, QFormLayout.ItemRole.LabelRole, self.unitsMetricEditLabel)

        self.unitsMetricEdit = QLineEdit(self.commandsTabContents)
        self.unitsMetricEdit.setObjectName(u"unitsMetricEdit")
        self.unitsMetricEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(14, QFormLayout.ItemRole.FieldRole, self.unitsMetricEdit)

        self.dwellCommandEditLabel = QLabel(self.commandsTabContents)
        self.dwellCommandEditLabel.setObjectName(u"dwellCommandEditLabel")

        self.commandsForm.setWidget(15, QFormLayout.ItemRole.LabelRole, self.dwellCommandEditLabel)

        self.dwellCommandEdit = QLineEdit(self.commandsTabContents)
        self.dwellCommandEdit.setObjectName(u"dwellCommandEdit")
        self.dwellCommandEdit.setMaximumSize(QSize(320, 16777215))

        self.commandsForm.setWidget(15, QFormLayout.ItemRole.FieldRole, self.dwellCommandEdit)

        self.dwellAddressComboLabel = QLabel(self.commandsTabContents)
        self.dwellAddressComboLabel.setObjectName(u"dwellAddressComboLabel")

        self.commandsForm.setWidget(16, QFormLayout.ItemRole.LabelRole, self.dwellAddressComboLabel)

        self.dwellAddressCombo = QComboBox(self.commandsTabContents)
        self.dwellAddressCombo.addItem("")
        self.dwellAddressCombo.addItem("")
        self.dwellAddressCombo.addItem("")
        self.dwellAddressCombo.setObjectName(u"dwellAddressCombo")
        self.dwellAddressCombo.setMaximumSize(QSize(320, 16777215))
        self.dwellAddressCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.dwellAddressCombo.setMinimumContentsLength(16)

        self.commandsForm.setWidget(16, QFormLayout.ItemRole.FieldRole, self.dwellAddressCombo)

        self.dwellScaleEditLabel = QLabel(self.commandsTabContents)
        self.dwellScaleEditLabel.setObjectName(u"dwellScaleEditLabel")

        self.commandsForm.setWidget(17, QFormLayout.ItemRole.LabelRole, self.dwellScaleEditLabel)

        self.dwellScaleEdit = QLineEdit(self.commandsTabContents)
        self.dwellScaleEdit.setObjectName(u"dwellScaleEdit")
        self.dwellScaleEdit.setMaximumSize(QSize(90, 16777215))

        self.commandsForm.setWidget(17, QFormLayout.ItemRole.FieldRole, self.dwellScaleEdit)

        self.commandsTabScroll.setWidget(self.commandsTabContents)

        self.commandsTabLayout.addWidget(self.commandsTabScroll)

        self.tabs.addTab(self.commandsTab, "")
        self.programTab = QWidget()
        self.programTab.setObjectName(u"programTab")
        self.programTabLayout = QVBoxLayout(self.programTab)
        self.programTabLayout.setObjectName(u"programTabLayout")
        self.programTabScroll = QScrollArea(self.programTab)
        self.programTabScroll.setObjectName(u"programTabScroll")
        self.programTabScroll.setFrameShape(QFrame.Shape.NoFrame)
        self.programTabScroll.setWidgetResizable(True)
        self.programTabContents = QWidget()
        self.programTabContents.setObjectName(u"programTabContents")
        self.programTabContents.setGeometry(QRect(0, 0, 640, 520))
        self.programForm = QFormLayout(self.programTabContents)
        self.programForm.setObjectName(u"programForm")
        self.programForm.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.programForm.setFormAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
        self.programForm.setVerticalSpacing(4)
        self.programStartEditLabel = QLabel(self.programTabContents)
        self.programStartEditLabel.setObjectName(u"programStartEditLabel")

        self.programForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.programStartEditLabel)

        self.programStartEdit = QPlainTextEdit(self.programTabContents)
        self.programStartEdit.setObjectName(u"programStartEdit")
        self.programStartEdit.setMinimumSize(QSize(0, 72))
        self.programStartEdit.setMaximumSize(QSize(16777215, 120))

        self.programForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.programStartEdit)

        self.programModeComboLabel = QLabel(self.programTabContents)
        self.programModeComboLabel.setObjectName(u"programModeComboLabel")

        self.programForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.programModeComboLabel)

        self.programModeCombo = QComboBox(self.programTabContents)
        self.programModeCombo.addItem("")
        self.programModeCombo.addItem("")
        self.programModeCombo.setObjectName(u"programModeCombo")
        self.programModeCombo.setMaximumSize(QSize(320, 16777215))
        self.programModeCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.programModeCombo.setMinimumContentsLength(16)

        self.programForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.programModeCombo)

        self.programStopEditLabel = QLabel(self.programTabContents)
        self.programStopEditLabel.setObjectName(u"programStopEditLabel")

        self.programForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.programStopEditLabel)

        self.programStopEdit = QLineEdit(self.programTabContents)
        self.programStopEdit.setObjectName(u"programStopEdit")
        self.programStopEdit.setMaximumSize(QSize(320, 16777215))

        self.programForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.programStopEdit)

        self.programOptionalStopEditLabel = QLabel(self.programTabContents)
        self.programOptionalStopEditLabel.setObjectName(u"programOptionalStopEditLabel")

        self.programForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.programOptionalStopEditLabel)

        self.programOptionalStopEdit = QLineEdit(self.programTabContents)
        self.programOptionalStopEdit.setObjectName(u"programOptionalStopEdit")
        self.programOptionalStopEdit.setMaximumSize(QSize(320, 16777215))

        self.programForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.programOptionalStopEdit)

        self.programEndEditLabel = QLabel(self.programTabContents)
        self.programEndEditLabel.setObjectName(u"programEndEditLabel")

        self.programForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.programEndEditLabel)

        self.programEndEdit = QPlainTextEdit(self.programTabContents)
        self.programEndEdit.setObjectName(u"programEndEdit")
        self.programEndEdit.setMinimumSize(QSize(0, 72))
        self.programEndEdit.setMaximumSize(QSize(16777215, 120))

        self.programForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.programEndEdit)

        self.commentTemplateEditLabel = QLabel(self.programTabContents)
        self.commentTemplateEditLabel.setObjectName(u"commentTemplateEditLabel")

        self.programForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.commentTemplateEditLabel)

        self.commentTemplateEdit = QLineEdit(self.programTabContents)
        self.commentTemplateEdit.setObjectName(u"commentTemplateEdit")
        self.commentTemplateEdit.setMaximumSize(QSize(320, 16777215))

        self.programForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.commentTemplateEdit)

        self.preambleEditLabel = QLabel(self.programTabContents)
        self.preambleEditLabel.setObjectName(u"preambleEditLabel")

        self.programForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.preambleEditLabel)

        self.preambleEdit = QPlainTextEdit(self.programTabContents)
        self.preambleEdit.setObjectName(u"preambleEdit")
        self.preambleEdit.setMaximumSize(QSize(320, 48))
        self.preambleEdit.setMinimumSize(QSize(0, 36))

        self.programForm.setWidget(6, QFormLayout.ItemRole.FieldRole, self.preambleEdit)

        self.safetyEditLabel = QLabel(self.programTabContents)
        self.safetyEditLabel.setObjectName(u"safetyEditLabel")

        self.programForm.setWidget(7, QFormLayout.ItemRole.LabelRole, self.safetyEditLabel)

        self.safetyEdit = QPlainTextEdit(self.programTabContents)
        self.safetyEdit.setObjectName(u"safetyEdit")
        self.safetyEdit.setMaximumSize(QSize(320, 48))
        self.safetyEdit.setMinimumSize(QSize(0, 36))

        self.programForm.setWidget(7, QFormLayout.ItemRole.FieldRole, self.safetyEdit)

        self.programTabScroll.setWidget(self.programTabContents)

        self.programTabLayout.addWidget(self.programTabScroll)

        self.tabs.addTab(self.programTab, "")
        self.supportsTab = QWidget()
        self.supportsTab.setObjectName(u"supportsTab")
        self.supportsTabLayout = QVBoxLayout(self.supportsTab)
        self.supportsTabLayout.setObjectName(u"supportsTabLayout")
        self.supportsTabScroll = QScrollArea(self.supportsTab)
        self.supportsTabScroll.setObjectName(u"supportsTabScroll")
        self.supportsTabScroll.setFrameShape(QFrame.Shape.NoFrame)
        self.supportsTabScroll.setWidgetResizable(True)
        self.supportsTabContents = QWidget()
        self.supportsTabContents.setObjectName(u"supportsTabContents")
        self.supportsTabContents.setGeometry(QRect(0, 0, 640, 300))
        self.supportsForm = QFormLayout(self.supportsTabContents)
        self.supportsForm.setObjectName(u"supportsForm")
        self.supportsForm.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.supportsForm.setFormAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
        self.supportsForm.setVerticalSpacing(4)
        self.inverseTimeCheck = QCheckBox(self.supportsTabContents)
        self.inverseTimeCheck.setObjectName(u"inverseTimeCheck")

        self.supportsForm.setWidget(0, QFormLayout.ItemRole.SpanningRole, self.inverseTimeCheck)

        self.supportsMultiTurnArcsCheck = QCheckBox(self.supportsTabContents)
        self.supportsMultiTurnArcsCheck.setObjectName(u"supportsMultiTurnArcsCheck")

        self.supportsForm.setWidget(1, QFormLayout.ItemRole.SpanningRole, self.supportsMultiTurnArcsCheck)

        self.absoluteArcCentersCheck = QCheckBox(self.supportsTabContents)
        self.absoluteArcCentersCheck.setObjectName(u"absoluteArcCentersCheck")

        self.supportsForm.setWidget(2, QFormLayout.ItemRole.SpanningRole, self.absoluteArcCentersCheck)

        self.tcpCheck = QCheckBox(self.supportsTabContents)
        self.tcpCheck.setObjectName(u"tcpCheck")

        self.supportsForm.setWidget(3, QFormLayout.ItemRole.SpanningRole, self.tcpCheck)

        self.tcpOnEditLabel = QLabel(self.supportsTabContents)
        self.tcpOnEditLabel.setObjectName(u"tcpOnEditLabel")

        self.supportsForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.tcpOnEditLabel)

        self.tcpOnEdit = QLineEdit(self.supportsTabContents)
        self.tcpOnEdit.setObjectName(u"tcpOnEdit")
        self.tcpOnEdit.setMaximumSize(QSize(320, 16777215))

        self.supportsForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.tcpOnEdit)

        self.tcpOffEditLabel = QLabel(self.supportsTabContents)
        self.tcpOffEditLabel.setObjectName(u"tcpOffEditLabel")

        self.supportsForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.tcpOffEditLabel)

        self.tcpOffEdit = QLineEdit(self.supportsTabContents)
        self.tcpOffEdit.setObjectName(u"tcpOffEdit")
        self.tcpOffEdit.setMaximumSize(QSize(320, 16777215))

        self.supportsForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.tcpOffEdit)

        self.supportsTabScroll.setWidget(self.supportsTabContents)

        self.supportsTabLayout.addWidget(self.supportsTabScroll)

        self.tabs.addTab(self.supportsTab, "")

        self.verticalLayout.addWidget(self.tabs)


        self.retranslateUi(PostProfileEditorDlg)

        QMetaObject.connectSlotsByName(PostProfileEditorDlg)
    # setupUi

    def retranslateUi(self, PostProfileEditorDlg):
        PostProfileEditorDlg.setWindowTitle(QCoreApplication.translate("PostProfileEditorDlg", u"Postprocessor editor", None))
        self.nameEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Name", None))
        self.machineComboLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Machine", None))
        self.machineCombo.setItemText(0, QCoreApplication.translate("PostProfileEditorDlg", u"mill", None))
        self.machineCombo.setItemText(1, QCoreApplication.translate("PostProfileEditorDlg", u"lathe", None))

        self.extensionEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"File extension", None))
        self.idLabelLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Controller id", None))
        self.axesLayoutLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Supported axes", None))
        self.axisXCheck.setText(QCoreApplication.translate("PostProfileEditorDlg", u"X", None))
        self.axisYCheck.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Y", None))
        self.axisZCheck.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Z", None))
        self.axisACheck.setText(QCoreApplication.translate("PostProfileEditorDlg", u"A", None))
        self.axisBCheck.setText(QCoreApplication.translate("PostProfileEditorDlg", u"B", None))
        self.axisCCheck.setText(QCoreApplication.translate("PostProfileEditorDlg", u"C", None))
        self.tabs.setTabText(self.tabs.indexOf(self.sourceTab), QCoreApplication.translate("PostProfileEditorDlg", u"Source", None))
        self.unitsLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Units", None))
        self.units.setItemText(0, QCoreApplication.translate("PostProfileEditorDlg", u"Millimeters", None))
        self.units.setItemText(1, QCoreApplication.translate("PostProfileEditorDlg", u"Inches", None))

        self.coordinatesLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Position output", None))
        self.coordinates.setItemText(0, QCoreApplication.translate("PostProfileEditorDlg", u"Absolute coordinates", None))
        self.coordinates.setItemText(1, QCoreApplication.translate("PostProfileEditorDlg", u"Incremental coordinates", None))

        self.arcsLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Arc output", None))
        self.arcs.setItemText(0, QCoreApplication.translate("PostProfileEditorDlg", u"Center offsets from the start point (IJK)", None))
        self.arcs.setItemText(1, QCoreApplication.translate("PostProfileEditorDlg", u"Absolute center coordinates (IJK)", None))
        self.arcs.setItemText(2, QCoreApplication.translate("PostProfileEditorDlg", u"Radius (R / CR)", None))
        self.arcs.setItemText(3, QCoreApplication.translate("PostProfileEditorDlg", u"Linear segments", None))

        self.multiTurn.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Keep arcs spanning multiple revolutions", None))
        self.centerSplitLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Maximum sweep per center arc", None))
        self.centerSplit.setItemText(0, QCoreApplication.translate("PostProfileEditorDlg", u"30\u00b0", None))
        self.centerSplit.setItemText(1, QCoreApplication.translate("PostProfileEditorDlg", u"45\u00b0", None))
        self.centerSplit.setItemText(2, QCoreApplication.translate("PostProfileEditorDlg", u"90\u00b0", None))
        self.centerSplit.setItemText(3, QCoreApplication.translate("PostProfileEditorDlg", u"120\u00b0", None))
        self.centerSplit.setItemText(4, QCoreApplication.translate("PostProfileEditorDlg", u"180\u00b0", None))
        self.centerSplit.setItemText(5, QCoreApplication.translate("PostProfileEditorDlg", u"360\u00b0", None))

        self.radiusSplitLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Maximum sweep per radius arc", None))
        self.radiusSplit.setItemText(0, QCoreApplication.translate("PostProfileEditorDlg", u"30\u00b0", None))
        self.radiusSplit.setItemText(1, QCoreApplication.translate("PostProfileEditorDlg", u"45\u00b0", None))
        self.radiusSplit.setItemText(2, QCoreApplication.translate("PostProfileEditorDlg", u"90\u00b0", None))
        self.radiusSplit.setItemText(3, QCoreApplication.translate("PostProfileEditorDlg", u"120\u00b0", None))
        self.radiusSplit.setItemText(4, QCoreApplication.translate("PostProfileEditorDlg", u"180\u00b0", None))
        self.radiusSplit.setItemText(5, QCoreApplication.translate("PostProfileEditorDlg", u"360\u00b0", None))

        self.tabs.setTabText(self.tabs.indexOf(self.outputTab), QCoreApplication.translate("PostProfileEditorDlg", u"Output", None))
        self.precisionLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Maximum decimal places", None))
        self.precision.setItemText(0, QCoreApplication.translate("PostProfileEditorDlg", u"0", None))
        self.precision.setItemText(1, QCoreApplication.translate("PostProfileEditorDlg", u"1", None))
        self.precision.setItemText(2, QCoreApplication.translate("PostProfileEditorDlg", u"2", None))
        self.precision.setItemText(3, QCoreApplication.translate("PostProfileEditorDlg", u"3", None))
        self.precision.setItemText(4, QCoreApplication.translate("PostProfileEditorDlg", u"4", None))
        self.precision.setItemText(5, QCoreApplication.translate("PostProfileEditorDlg", u"5", None))
        self.precision.setItemText(6, QCoreApplication.translate("PostProfileEditorDlg", u"6", None))
        self.precision.setItemText(7, QCoreApplication.translate("PostProfileEditorDlg", u"7", None))
        self.precision.setItemText(8, QCoreApplication.translate("PostProfileEditorDlg", u"8", None))
        self.precision.setItemText(9, QCoreApplication.translate("PostProfileEditorDlg", u"9", None))
        self.precision.setItemText(10, QCoreApplication.translate("PostProfileEditorDlg", u"10", None))
        self.precision.setItemText(11, QCoreApplication.translate("PostProfileEditorDlg", u"11", None))
        self.precision.setItemText(12, QCoreApplication.translate("PostProfileEditorDlg", u"12", None))

        self.spaces.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Separate words with spaces", None))
        self.leadingZero.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Leading zero in G codes (G01)", None))
        self.forceDecimal.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Decimal point for whole numbers (X1.)", None))
        self.plusSign.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Plus sign for positive numbers (X+1)", None))
        self.tabs.setTabText(self.tabs.indexOf(self.formatTab), QCoreApplication.translate("PostProfileEditorDlg", u"Format", None))
        self.sequencingHint.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Drag addresses to change their order. Select an address to edit its settings.", None))
        self.selectedAddressLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Address settings", None))
        self.addressPrecisionLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Decimal places", None))
        self.addressPrecision.setItemText(0, QCoreApplication.translate("PostProfileEditorDlg", u"Use general precision", None))
        self.addressPrecision.setItemText(1, QCoreApplication.translate("PostProfileEditorDlg", u"0", None))
        self.addressPrecision.setItemText(2, QCoreApplication.translate("PostProfileEditorDlg", u"1", None))
        self.addressPrecision.setItemText(3, QCoreApplication.translate("PostProfileEditorDlg", u"2", None))
        self.addressPrecision.setItemText(4, QCoreApplication.translate("PostProfileEditorDlg", u"3", None))
        self.addressPrecision.setItemText(5, QCoreApplication.translate("PostProfileEditorDlg", u"4", None))
        self.addressPrecision.setItemText(6, QCoreApplication.translate("PostProfileEditorDlg", u"5", None))
        self.addressPrecision.setItemText(7, QCoreApplication.translate("PostProfileEditorDlg", u"6", None))
        self.addressPrecision.setItemText(8, QCoreApplication.translate("PostProfileEditorDlg", u"7", None))
        self.addressPrecision.setItemText(9, QCoreApplication.translate("PostProfileEditorDlg", u"8", None))
        self.addressPrecision.setItemText(10, QCoreApplication.translate("PostProfileEditorDlg", u"9", None))
        self.addressPrecision.setItemText(11, QCoreApplication.translate("PostProfileEditorDlg", u"10", None))
        self.addressPrecision.setItemText(12, QCoreApplication.translate("PostProfileEditorDlg", u"11", None))
        self.addressPrecision.setItemText(13, QCoreApplication.translate("PostProfileEditorDlg", u"12", None))

        self.addressSignLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Sign", None))
        self.addressSign.setItemText(0, QCoreApplication.translate("PostProfileEditorDlg", u"Use general sign", None))
        self.addressSign.setItemText(1, QCoreApplication.translate("PostProfileEditorDlg", u"Negative only", None))
        self.addressSign.setItemText(2, QCoreApplication.translate("PostProfileEditorDlg", u"Always show sign", None))
        self.addressSign.setItemText(3, QCoreApplication.translate("PostProfileEditorDlg", u"No plus sign", None))

        self.addressRequiredLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Output", None))
        self.addressRequired.setItemText(0, QCoreApplication.translate("PostProfileEditorDlg", u"When needed", None))
        self.addressRequired.setItemText(1, QCoreApplication.translate("PostProfileEditorDlg", u"Every applicable block", None))

        self.tabs.setTabText(self.tabs.indexOf(self.sequencingTab), QCoreApplication.translate("PostProfileEditorDlg", u"Sequencing", None))
        self.rapidMoveEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Rapid move", None))
        self.linearMoveEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Linear move", None))
        self.circularMoveCWEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Circular CW", None))
        self.circularMoveCCWEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Circular CCW", None))
        self.planeXYEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Plane XY", None))
        self.planeXZEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Plane XZ", None))
        self.planeYZEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Plane YZ", None))
        self.threadMoveEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Thread move", None))
        self.absoluteEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Absolute command", None))
        self.incrementalEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Incremental command", None))
        self.referenceRapidEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Reference rapid", None))
        self.referenceLinearEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Reference linear", None))
        self.tabs.setTabText(self.tabs.indexOf(self.motionsTab), QCoreApplication.translate("PostProfileEditorDlg", u"Motions", None))
        self.homeG28AllEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"G28 all axes", None))
        self.homeG28XEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"G28 X", None))
        self.homeG28YEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"G28 Y", None))
        self.homeG28ZEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"G28 Z", None))
        self.homeG53AllEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"G53 all axes", None))
        self.homeG53XEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"G53 X", None))
        self.homeG53YEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"G53 Y", None))
        self.homeG53ZEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"G53 Z", None))
        self.tabs.setTabText(self.tabs.indexOf(self.homeTab), QCoreApplication.translate("PostProfileEditorDlg", u"Home", None))
        self.cyclesSyntaxComboLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Syntax", None))
        self.cyclesSyntaxCombo.setItemText(0, QCoreApplication.translate("PostProfileEditorDlg", u"iso", None))
        self.cyclesSyntaxCombo.setItemText(1, QCoreApplication.translate("PostProfileEditorDlg", u"native", None))

        self.cyclesCancelEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Cancel", None))
        self.cyclesReturnInitialEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Return initial", None))
        self.cyclesReturnSafetyEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Return safety", None))
        self.cyclesRigidTapEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Rigid tap", None))
        self.cyclesDrillEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Drill", None))
        self.cyclesDrillDwellEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Drill dwell", None))
        self.cyclesPeckDrillEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Peck drill", None))
        self.cyclesHighSpeedPeckEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"High-speed peck", None))
        self.cyclesTapEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Tap", None))
        self.cyclesBoreFeedEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Bore feed", None))
        self.cyclesBoreStopEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Bore stop", None))
        self.nativeCycleCallEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Cycle call", None))
        self.nativeDwellDefinitionEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Dwell definition", None))
        self.tabs.setTabText(self.tabs.indexOf(self.cyclesTab), QCoreApplication.translate("PostProfileEditorDlg", u"Cycles", None))
        self.toolChangeEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Tool change", None))
        self.spindleCWEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Spindle CW", None))
        self.spindleCCWEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Spindle CCW", None))
        self.spindleStopEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Spindle stop", None))
        self.spindleCSSOnEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"CSS on", None))
        self.spindleCSSOffEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"CSS off", None))
        self.spindleMaxSpeedEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Max speed", None))
        self.coolantMistEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Coolant mist", None))
        self.coolantFloodEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Coolant flood", None))
        self.coolantOffEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Coolant off", None))
        self.feedPerMinuteEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Feed per minute", None))
        self.feedPerRevEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Feed per revolution", None))
        self.feedInverseTimeEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Inverse time feed", None))
        self.unitsInchEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Inch command", None))
        self.unitsMetricEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Metric command", None))
        self.dwellCommandEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Dwell command", None))
        self.dwellAddressComboLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Dwell address", None))
        self.dwellAddressCombo.setItemText(0, QCoreApplication.translate("PostProfileEditorDlg", u"P", None))
        self.dwellAddressCombo.setItemText(1, QCoreApplication.translate("PostProfileEditorDlg", u"F", None))
        self.dwellAddressCombo.setItemText(2, QCoreApplication.translate("PostProfileEditorDlg", u"X", None))

        self.dwellScaleEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Dwell scale", None))
        self.tabs.setTabText(self.tabs.indexOf(self.commandsTab), QCoreApplication.translate("PostProfileEditorDlg", u"Commands", None))
        self.programStartEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Start program template", None))
        self.programModeComboLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Mode", None))
        self.programModeCombo.setItemText(0, QCoreApplication.translate("PostProfileEditorDlg", u"G290", None))
        self.programModeCombo.setItemText(1, QCoreApplication.translate("PostProfileEditorDlg", u"G291", None))

        self.programStopEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Stop", None))
        self.programOptionalStopEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Optional stop", None))
        self.programEndEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"End program template", None))
        self.commentTemplateEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Comment template", None))
        self.preambleEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Preamble lines", None))
        self.safetyEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Safety lines", None))
        self.tabs.setTabText(self.tabs.indexOf(self.programTab), QCoreApplication.translate("PostProfileEditorDlg", u"Program", None))
        self.inverseTimeCheck.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Allow G93 inverse-time feed", None))
        self.supportsMultiTurnArcsCheck.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Allow arcs over 360\u00b0", None))
        self.absoluteArcCentersCheck.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Allow absolute IJK centers", None))
        self.tcpCheck.setText(QCoreApplication.translate("PostProfileEditorDlg", u"Allow TCP output", None))
        self.tcpOnEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"TCP on", None))
        self.tcpOffEditLabel.setText(QCoreApplication.translate("PostProfileEditorDlg", u"TCP off", None))
        self.tabs.setTabText(self.tabs.indexOf(self.supportsTab), QCoreApplication.translate("PostProfileEditorDlg", u"Supports", None))
    # retranslateUi
