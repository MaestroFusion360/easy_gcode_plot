# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tool_library.ui'
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
from PyQt6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QDialog,
    QDialogButtonBox, QGroupBox, QHBoxLayout, QHeaderView,
    QPushButton, QSizePolicy, QSpacerItem, QSplitter,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget)

from app.ui.plot.tool_library_preview import ToolLibraryPreviewPane

import app.resources.files_res  # noqa: F401  # Registers Qt resources on import.

class Ui_ToolLibraryDialog(object):
    def setupUi(self, ToolLibraryDialog):
        if not ToolLibraryDialog.objectName():
            ToolLibraryDialog.setObjectName(u"ToolLibraryDialog")
        ToolLibraryDialog.resize(940, 620)
        self.verticalLayout = QVBoxLayout(ToolLibraryDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.tabs = QTabWidget(ToolLibraryDialog)
        self.tabs.setObjectName(u"tabs")
        self.millingTab = QWidget()
        self.millingTab.setObjectName(u"millingTab")
        self.millingTabLayout = QHBoxLayout(self.millingTab)
        self.millingTabLayout.setObjectName(u"millingTabLayout")
        self.millingSplitter = QSplitter(self.millingTab)
        self.millingSplitter.setObjectName(u"millingSplitter")
        self.millingSplitter.setOrientation(Qt.Orientation.Horizontal)
        self.millingSplitter.setChildrenCollapsible(True)
        self.millingTablesWidget = QWidget(self.millingSplitter)
        self.millingTablesWidget.setObjectName(u"millingTablesWidget")
        self.millingTablesLayout = QVBoxLayout(self.millingTablesWidget)
        self.millingTablesLayout.setObjectName(u"millingTablesLayout")
        self.millingTablesLayout.setContentsMargins(0, 0, 0, 0)
        self.millingProgramGroup = QGroupBox(self.millingTablesWidget)
        self.millingProgramGroup.setObjectName(u"millingProgramGroup")
        self.millingProgramGroup.setFlat(True)
        self.millingProgramLayout = QVBoxLayout(self.millingProgramGroup)
        self.millingProgramLayout.setObjectName(u"millingProgramLayout")
        self.millingProgramTable = QTableWidget(self.millingProgramGroup)
        if (self.millingProgramTable.columnCount() < 4):
            self.millingProgramTable.setColumnCount(4)
        __qtablewidgetitem = QTableWidgetItem()
        self.millingProgramTable.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.millingProgramTable.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.millingProgramTable.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.millingProgramTable.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        self.millingProgramTable.setObjectName(u"millingProgramTable")
        self.millingProgramTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.millingProgramTable.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.millingProgramTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.millingProgramTable.setColumnCount(4)

        self.millingProgramLayout.addWidget(self.millingProgramTable)

        self.millingProgramButtonsLayout = QHBoxLayout()
        self.millingProgramButtonsLayout.setObjectName(u"millingProgramButtonsLayout")
        self.millingEditProgramButton = QPushButton(self.millingProgramGroup)
        self.millingEditProgramButton.setObjectName(u"millingEditProgramButton")
        icon = QIcon()
        icon.addFile(u":/resource/icons/edit.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.millingEditProgramButton.setIcon(icon)
        self.millingEditProgramButton.setIconSize(QSize(16, 16))

        self.millingProgramButtonsLayout.addWidget(self.millingEditProgramButton)

        self.millingAssignButton = QPushButton(self.millingProgramGroup)
        self.millingAssignButton.setObjectName(u"millingAssignButton")
        icon1 = QIcon()
        icon1.addFile(u":/resource/icons/assign-from-library.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.millingAssignButton.setIcon(icon1)
        self.millingAssignButton.setIconSize(QSize(16, 16))

        self.millingProgramButtonsLayout.addWidget(self.millingAssignButton)

        self.millingSaveButton = QPushButton(self.millingProgramGroup)
        self.millingSaveButton.setObjectName(u"millingSaveButton")
        icon2 = QIcon()
        icon2.addFile(u":/resource/icons/save.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.millingSaveButton.setIcon(icon2)
        self.millingSaveButton.setIconSize(QSize(16, 16))

        self.millingProgramButtonsLayout.addWidget(self.millingSaveButton)

        self.millingProgramSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.millingProgramButtonsLayout.addItem(self.millingProgramSpacer)


        self.millingProgramLayout.addLayout(self.millingProgramButtonsLayout)


        self.millingTablesLayout.addWidget(self.millingProgramGroup)

        self.millingLibraryGroup = QGroupBox(self.millingTablesWidget)
        self.millingLibraryGroup.setObjectName(u"millingLibraryGroup")
        self.millingLibraryGroup.setFlat(True)
        self.millingLibraryLayout = QVBoxLayout(self.millingLibraryGroup)
        self.millingLibraryLayout.setObjectName(u"millingLibraryLayout")
        self.millingLibraryTable = QTableWidget(self.millingLibraryGroup)
        if (self.millingLibraryTable.columnCount() < 4):
            self.millingLibraryTable.setColumnCount(4)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.millingLibraryTable.setHorizontalHeaderItem(0, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.millingLibraryTable.setHorizontalHeaderItem(1, __qtablewidgetitem5)
        __qtablewidgetitem6 = QTableWidgetItem()
        self.millingLibraryTable.setHorizontalHeaderItem(2, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        self.millingLibraryTable.setHorizontalHeaderItem(3, __qtablewidgetitem7)
        self.millingLibraryTable.setObjectName(u"millingLibraryTable")
        self.millingLibraryTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.millingLibraryTable.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.millingLibraryTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.millingLibraryTable.setColumnCount(4)

        self.millingLibraryLayout.addWidget(self.millingLibraryTable)

        self.millingLibraryButtonsLayout = QHBoxLayout()
        self.millingLibraryButtonsLayout.setObjectName(u"millingLibraryButtonsLayout")
        self.millingAddLibraryButton = QPushButton(self.millingLibraryGroup)
        self.millingAddLibraryButton.setObjectName(u"millingAddLibraryButton")
        icon3 = QIcon()
        icon3.addFile(u":/resource/icons/add.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.millingAddLibraryButton.setIcon(icon3)
        self.millingAddLibraryButton.setIconSize(QSize(16, 16))

        self.millingLibraryButtonsLayout.addWidget(self.millingAddLibraryButton)

        self.millingEditLibraryButton = QPushButton(self.millingLibraryGroup)
        self.millingEditLibraryButton.setObjectName(u"millingEditLibraryButton")
        self.millingEditLibraryButton.setIcon(icon)
        self.millingEditLibraryButton.setIconSize(QSize(16, 16))

        self.millingLibraryButtonsLayout.addWidget(self.millingEditLibraryButton)

        self.millingDuplicateLibraryButton = QPushButton(self.millingLibraryGroup)
        self.millingDuplicateLibraryButton.setObjectName(u"millingDuplicateLibraryButton")
        icon4 = QIcon()
        icon4.addFile(u":/resource/icons/copy.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.millingDuplicateLibraryButton.setIcon(icon4)
        self.millingDuplicateLibraryButton.setIconSize(QSize(16, 16))

        self.millingLibraryButtonsLayout.addWidget(self.millingDuplicateLibraryButton)

        self.millingExportLibraryButton = QPushButton(self.millingLibraryGroup)
        self.millingExportLibraryButton.setObjectName(u"millingExportLibraryButton")
        icon5 = QIcon()
        icon5.addFile(u":/resource/icons/export.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.millingExportLibraryButton.setIcon(icon5)
        self.millingExportLibraryButton.setIconSize(QSize(16, 16))

        self.millingLibraryButtonsLayout.addWidget(self.millingExportLibraryButton)

        self.millingRemoveLibraryButton = QPushButton(self.millingLibraryGroup)
        self.millingRemoveLibraryButton.setObjectName(u"millingRemoveLibraryButton")
        icon6 = QIcon()
        icon6.addFile(u":/resource/icons/trash.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.millingRemoveLibraryButton.setIcon(icon6)
        self.millingRemoveLibraryButton.setIconSize(QSize(16, 16))

        self.millingLibraryButtonsLayout.addWidget(self.millingRemoveLibraryButton)

        self.millingLibrarySpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.millingLibraryButtonsLayout.addItem(self.millingLibrarySpacer)


        self.millingLibraryLayout.addLayout(self.millingLibraryButtonsLayout)


        self.millingTablesLayout.addWidget(self.millingLibraryGroup)

        self.millingSplitter.addWidget(self.millingTablesWidget)
        self.millingPreviewPane = ToolLibraryPreviewPane(self.millingSplitter)
        self.millingPreviewPane.setObjectName(u"millingPreviewPane")
        self.millingSplitter.addWidget(self.millingPreviewPane)

        self.millingTabLayout.addWidget(self.millingSplitter)

        self.tabs.addTab(self.millingTab, "")
        self.turningTab = QWidget()
        self.turningTab.setObjectName(u"turningTab")
        self.turningTabLayout = QHBoxLayout(self.turningTab)
        self.turningTabLayout.setObjectName(u"turningTabLayout")
        self.turningSplitter = QSplitter(self.turningTab)
        self.turningSplitter.setObjectName(u"turningSplitter")
        self.turningSplitter.setOrientation(Qt.Orientation.Horizontal)
        self.turningSplitter.setChildrenCollapsible(True)
        self.turningTablesWidget = QWidget(self.turningSplitter)
        self.turningTablesWidget.setObjectName(u"turningTablesWidget")
        self.turningTablesLayout = QVBoxLayout(self.turningTablesWidget)
        self.turningTablesLayout.setObjectName(u"turningTablesLayout")
        self.turningTablesLayout.setContentsMargins(0, 0, 0, 0)
        self.turningProgramGroup = QGroupBox(self.turningTablesWidget)
        self.turningProgramGroup.setObjectName(u"turningProgramGroup")
        self.turningProgramGroup.setFlat(True)
        self.turningProgramLayout = QVBoxLayout(self.turningProgramGroup)
        self.turningProgramLayout.setObjectName(u"turningProgramLayout")
        self.turningProgramTable = QTableWidget(self.turningProgramGroup)
        if (self.turningProgramTable.columnCount() < 4):
            self.turningProgramTable.setColumnCount(4)
        __qtablewidgetitem8 = QTableWidgetItem()
        self.turningProgramTable.setHorizontalHeaderItem(0, __qtablewidgetitem8)
        __qtablewidgetitem9 = QTableWidgetItem()
        self.turningProgramTable.setHorizontalHeaderItem(1, __qtablewidgetitem9)
        __qtablewidgetitem10 = QTableWidgetItem()
        self.turningProgramTable.setHorizontalHeaderItem(2, __qtablewidgetitem10)
        __qtablewidgetitem11 = QTableWidgetItem()
        self.turningProgramTable.setHorizontalHeaderItem(3, __qtablewidgetitem11)
        self.turningProgramTable.setObjectName(u"turningProgramTable")
        self.turningProgramTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.turningProgramTable.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.turningProgramTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.turningProgramTable.setColumnCount(4)

        self.turningProgramLayout.addWidget(self.turningProgramTable)

        self.turningProgramButtonsLayout = QHBoxLayout()
        self.turningProgramButtonsLayout.setObjectName(u"turningProgramButtonsLayout")
        self.turningEditProgramButton = QPushButton(self.turningProgramGroup)
        self.turningEditProgramButton.setObjectName(u"turningEditProgramButton")
        self.turningEditProgramButton.setIcon(icon)
        self.turningEditProgramButton.setIconSize(QSize(16, 16))

        self.turningProgramButtonsLayout.addWidget(self.turningEditProgramButton)

        self.turningAssignButton = QPushButton(self.turningProgramGroup)
        self.turningAssignButton.setObjectName(u"turningAssignButton")
        self.turningAssignButton.setIcon(icon1)
        self.turningAssignButton.setIconSize(QSize(16, 16))

        self.turningProgramButtonsLayout.addWidget(self.turningAssignButton)

        self.turningSaveButton = QPushButton(self.turningProgramGroup)
        self.turningSaveButton.setObjectName(u"turningSaveButton")
        self.turningSaveButton.setIcon(icon2)
        self.turningSaveButton.setIconSize(QSize(16, 16))

        self.turningProgramButtonsLayout.addWidget(self.turningSaveButton)

        self.turningProgramSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.turningProgramButtonsLayout.addItem(self.turningProgramSpacer)


        self.turningProgramLayout.addLayout(self.turningProgramButtonsLayout)


        self.turningTablesLayout.addWidget(self.turningProgramGroup)

        self.turningLibraryGroup = QGroupBox(self.turningTablesWidget)
        self.turningLibraryGroup.setObjectName(u"turningLibraryGroup")
        self.turningLibraryGroup.setFlat(True)
        self.turningLibraryLayout = QVBoxLayout(self.turningLibraryGroup)
        self.turningLibraryLayout.setObjectName(u"turningLibraryLayout")
        self.turningLibraryTable = QTableWidget(self.turningLibraryGroup)
        if (self.turningLibraryTable.columnCount() < 4):
            self.turningLibraryTable.setColumnCount(4)
        __qtablewidgetitem12 = QTableWidgetItem()
        self.turningLibraryTable.setHorizontalHeaderItem(0, __qtablewidgetitem12)
        __qtablewidgetitem13 = QTableWidgetItem()
        self.turningLibraryTable.setHorizontalHeaderItem(1, __qtablewidgetitem13)
        __qtablewidgetitem14 = QTableWidgetItem()
        self.turningLibraryTable.setHorizontalHeaderItem(2, __qtablewidgetitem14)
        __qtablewidgetitem15 = QTableWidgetItem()
        self.turningLibraryTable.setHorizontalHeaderItem(3, __qtablewidgetitem15)
        self.turningLibraryTable.setObjectName(u"turningLibraryTable")
        self.turningLibraryTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.turningLibraryTable.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.turningLibraryTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.turningLibraryTable.setColumnCount(4)

        self.turningLibraryLayout.addWidget(self.turningLibraryTable)

        self.turningLibraryButtonsLayout = QHBoxLayout()
        self.turningLibraryButtonsLayout.setObjectName(u"turningLibraryButtonsLayout")
        self.turningAddLibraryButton = QPushButton(self.turningLibraryGroup)
        self.turningAddLibraryButton.setObjectName(u"turningAddLibraryButton")
        self.turningAddLibraryButton.setIcon(icon3)
        self.turningAddLibraryButton.setIconSize(QSize(16, 16))

        self.turningLibraryButtonsLayout.addWidget(self.turningAddLibraryButton)

        self.turningEditLibraryButton = QPushButton(self.turningLibraryGroup)
        self.turningEditLibraryButton.setObjectName(u"turningEditLibraryButton")
        self.turningEditLibraryButton.setIcon(icon)
        self.turningEditLibraryButton.setIconSize(QSize(16, 16))

        self.turningLibraryButtonsLayout.addWidget(self.turningEditLibraryButton)

        self.turningDuplicateLibraryButton = QPushButton(self.turningLibraryGroup)
        self.turningDuplicateLibraryButton.setObjectName(u"turningDuplicateLibraryButton")
        self.turningDuplicateLibraryButton.setIcon(icon4)
        self.turningDuplicateLibraryButton.setIconSize(QSize(16, 16))

        self.turningLibraryButtonsLayout.addWidget(self.turningDuplicateLibraryButton)

        self.turningExportLibraryButton = QPushButton(self.turningLibraryGroup)
        self.turningExportLibraryButton.setObjectName(u"turningExportLibraryButton")
        self.turningExportLibraryButton.setIcon(icon5)
        self.turningExportLibraryButton.setIconSize(QSize(16, 16))

        self.turningLibraryButtonsLayout.addWidget(self.turningExportLibraryButton)

        self.turningRemoveLibraryButton = QPushButton(self.turningLibraryGroup)
        self.turningRemoveLibraryButton.setObjectName(u"turningRemoveLibraryButton")
        self.turningRemoveLibraryButton.setIcon(icon6)
        self.turningRemoveLibraryButton.setIconSize(QSize(16, 16))

        self.turningLibraryButtonsLayout.addWidget(self.turningRemoveLibraryButton)

        self.turningLibrarySpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.turningLibraryButtonsLayout.addItem(self.turningLibrarySpacer)


        self.turningLibraryLayout.addLayout(self.turningLibraryButtonsLayout)


        self.turningTablesLayout.addWidget(self.turningLibraryGroup)

        self.turningSplitter.addWidget(self.turningTablesWidget)
        self.turningPreviewPane = ToolLibraryPreviewPane(self.turningSplitter)
        self.turningPreviewPane.setObjectName(u"turningPreviewPane")
        self.turningSplitter.addWidget(self.turningPreviewPane)

        self.turningTabLayout.addWidget(self.turningSplitter)

        self.tabs.addTab(self.turningTab, "")

        self.verticalLayout.addWidget(self.tabs)

        self.buttonBox = QDialogButtonBox(ToolLibraryDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(ToolLibraryDialog)

        QMetaObject.connectSlotsByName(ToolLibraryDialog)
    # setupUi

    def retranslateUi(self, ToolLibraryDialog):
        ToolLibraryDialog.setWindowTitle(QCoreApplication.translate("ToolLibraryDialog", u"Tool Library", None))
        self.millingProgramGroup.setTitle(QCoreApplication.translate("ToolLibraryDialog", u"Current Program", None))
        ___qtablewidgetitem = self.millingProgramTable.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("ToolLibraryDialog", u"T code", None))
        ___qtablewidgetitem1 = self.millingProgramTable.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("ToolLibraryDialog", u"Type", None))
        ___qtablewidgetitem2 = self.millingProgramTable.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("ToolLibraryDialog", u"Geometry", None))
        ___qtablewidgetitem3 = self.millingProgramTable.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("ToolLibraryDialog", u"Description", None))
        self.millingEditProgramButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Edit Geometry", None))
#if QT_CONFIG(tooltip)
        self.millingEditProgramButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Edit Geometry", None))
#endif // QT_CONFIG(tooltip)
        self.millingAssignButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Assign from Library", None))
#if QT_CONFIG(tooltip)
        self.millingAssignButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Assign from Library", None))
#endif // QT_CONFIG(tooltip)
        self.millingSaveButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Save to Library", None))
#if QT_CONFIG(tooltip)
        self.millingSaveButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Save to Library", None))
#endif // QT_CONFIG(tooltip)
        self.millingLibraryGroup.setTitle(QCoreApplication.translate("ToolLibraryDialog", u"Saved Library", None))
        ___qtablewidgetitem4 = self.millingLibraryTable.horizontalHeaderItem(0)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("ToolLibraryDialog", u"Library ID", None))
        ___qtablewidgetitem5 = self.millingLibraryTable.horizontalHeaderItem(1)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("ToolLibraryDialog", u"Type", None))
        ___qtablewidgetitem6 = self.millingLibraryTable.horizontalHeaderItem(2)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("ToolLibraryDialog", u"Geometry", None))
        ___qtablewidgetitem7 = self.millingLibraryTable.horizontalHeaderItem(3)
        ___qtablewidgetitem7.setText(QCoreApplication.translate("ToolLibraryDialog", u"Description", None))
        self.millingAddLibraryButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Add", None))
#if QT_CONFIG(tooltip)
        self.millingAddLibraryButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Add", None))
#endif // QT_CONFIG(tooltip)
        self.millingEditLibraryButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Edit", None))
#if QT_CONFIG(tooltip)
        self.millingEditLibraryButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Edit", None))
#endif // QT_CONFIG(tooltip)
        self.millingDuplicateLibraryButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Duplicate", None))
#if QT_CONFIG(tooltip)
        self.millingDuplicateLibraryButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Duplicate", None))
#endif // QT_CONFIG(tooltip)
        self.millingExportLibraryButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Export", None))
#if QT_CONFIG(tooltip)
        self.millingExportLibraryButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Export", None))
#endif // QT_CONFIG(tooltip)
        self.millingRemoveLibraryButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Remove", None))
#if QT_CONFIG(tooltip)
        self.millingRemoveLibraryButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Remove", None))
#endif // QT_CONFIG(tooltip)
        self.tabs.setTabText(self.tabs.indexOf(self.millingTab), QCoreApplication.translate("ToolLibraryDialog", u"Milling", None))
        self.turningProgramGroup.setTitle(QCoreApplication.translate("ToolLibraryDialog", u"Current Program", None))
        ___qtablewidgetitem8 = self.turningProgramTable.horizontalHeaderItem(0)
        ___qtablewidgetitem8.setText(QCoreApplication.translate("ToolLibraryDialog", u"T code", None))
        ___qtablewidgetitem9 = self.turningProgramTable.horizontalHeaderItem(1)
        ___qtablewidgetitem9.setText(QCoreApplication.translate("ToolLibraryDialog", u"Type", None))
        ___qtablewidgetitem10 = self.turningProgramTable.horizontalHeaderItem(2)
        ___qtablewidgetitem10.setText(QCoreApplication.translate("ToolLibraryDialog", u"Geometry", None))
        ___qtablewidgetitem11 = self.turningProgramTable.horizontalHeaderItem(3)
        ___qtablewidgetitem11.setText(QCoreApplication.translate("ToolLibraryDialog", u"Description", None))
        self.turningEditProgramButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Edit Geometry", None))
#if QT_CONFIG(tooltip)
        self.turningEditProgramButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Edit Geometry", None))
#endif // QT_CONFIG(tooltip)
        self.turningAssignButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Assign from Library", None))
#if QT_CONFIG(tooltip)
        self.turningAssignButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Assign from Library", None))
#endif // QT_CONFIG(tooltip)
        self.turningSaveButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Save to Library", None))
#if QT_CONFIG(tooltip)
        self.turningSaveButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Save to Library", None))
#endif // QT_CONFIG(tooltip)
        self.turningLibraryGroup.setTitle(QCoreApplication.translate("ToolLibraryDialog", u"Saved Library", None))
        ___qtablewidgetitem12 = self.turningLibraryTable.horizontalHeaderItem(0)
        ___qtablewidgetitem12.setText(QCoreApplication.translate("ToolLibraryDialog", u"Library ID", None))
        ___qtablewidgetitem13 = self.turningLibraryTable.horizontalHeaderItem(1)
        ___qtablewidgetitem13.setText(QCoreApplication.translate("ToolLibraryDialog", u"Type", None))
        ___qtablewidgetitem14 = self.turningLibraryTable.horizontalHeaderItem(2)
        ___qtablewidgetitem14.setText(QCoreApplication.translate("ToolLibraryDialog", u"Geometry", None))
        ___qtablewidgetitem15 = self.turningLibraryTable.horizontalHeaderItem(3)
        ___qtablewidgetitem15.setText(QCoreApplication.translate("ToolLibraryDialog", u"Description", None))
        self.turningAddLibraryButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Add", None))
#if QT_CONFIG(tooltip)
        self.turningAddLibraryButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Add", None))
#endif // QT_CONFIG(tooltip)
        self.turningEditLibraryButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Edit", None))
#if QT_CONFIG(tooltip)
        self.turningEditLibraryButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Edit", None))
#endif // QT_CONFIG(tooltip)
        self.turningDuplicateLibraryButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Duplicate", None))
#if QT_CONFIG(tooltip)
        self.turningDuplicateLibraryButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Duplicate", None))
#endif // QT_CONFIG(tooltip)
        self.turningExportLibraryButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Export", None))
#if QT_CONFIG(tooltip)
        self.turningExportLibraryButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Export", None))
#endif // QT_CONFIG(tooltip)
        self.turningRemoveLibraryButton.setText(QCoreApplication.translate("ToolLibraryDialog", u"Remove", None))
#if QT_CONFIG(tooltip)
        self.turningRemoveLibraryButton.setToolTip(QCoreApplication.translate("ToolLibraryDialog", u"Remove", None))
#endif // QT_CONFIG(tooltip)
        self.tabs.setTabText(self.tabs.indexOf(self.turningTab), QCoreApplication.translate("ToolLibraryDialog", u"Turning", None))
    # retranslateUi
