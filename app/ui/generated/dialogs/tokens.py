# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tokens.ui'
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
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QSpacerItem, QTabWidget,
    QTableView, QVBoxLayout, QWidget)

class Ui_TokensDlg(object):
    def setupUi(self, TokensDlg):
        if not TokensDlg.objectName():
            TokensDlg.setObjectName(u"TokensDlg")
        TokensDlg.resize(820, 560)
        TokensDlg.setMinimumSize(QSize(680, 420))
        TokensDlg.setModal(False)
        TokensDlg.setWindowFlags(Qt.WindowType.Window|Qt.WindowType.WindowTitleHint|Qt.WindowType.WindowSystemMenuHint|Qt.WindowType.WindowMinimizeButtonHint|Qt.WindowType.WindowMaximizeButtonHint|Qt.WindowType.WindowCloseButtonHint)
        self.verticalLayout = QVBoxLayout(TokensDlg)
        self.verticalLayout.setSpacing(4)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(6, 6, 6, 6)
        self.tabWidget = QTabWidget(TokensDlg)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tokensTab = QWidget()
        self.tokensTab.setObjectName(u"tokensTab")
        self.tokensLayout = QVBoxLayout(self.tokensTab)
        self.tokensLayout.setObjectName(u"tokensLayout")
        self.tokensLayout.setContentsMargins(6, 6, 6, 6)
        self.headerLayout = QHBoxLayout()
        self.headerLayout.setSpacing(6)
        self.headerLayout.setObjectName(u"headerLayout")
        self.filterCombo = QComboBox(self.tokensTab)
        self.filterCombo.addItem("")
        self.filterCombo.addItem("")
        self.filterCombo.addItem("")
        self.filterCombo.setObjectName(u"filterCombo")
        self.filterCombo.setMinimumSize(QSize(120, 0))

        self.headerLayout.addWidget(self.filterCombo)

        self.searchEdit = QLineEdit(self.tokensTab)
        self.searchEdit.setObjectName(u"searchEdit")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.searchEdit.sizePolicy().hasHeightForWidth())
        self.searchEdit.setSizePolicy(sizePolicy)
        self.searchEdit.setClearButtonEnabled(True)

        self.headerLayout.addWidget(self.searchEdit)


        self.tokensLayout.addLayout(self.headerLayout)

        self.tokenTable = QTableView(self.tokensTab)
        self.tokenTable.setObjectName(u"tokenTable")
        self.tokenTable.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tokenTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tokenTable.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tokenTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tokenTable.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.tokenTable.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.tokenTable.setShowGrid(True)
        self.tokenTable.setWordWrap(False)
        self.tokenTable.setSortingEnabled(False)

        self.tokensLayout.addWidget(self.tokenTable)

        self.tabWidget.addTab(self.tokensTab, "")
        self.macroVariablesTab = QWidget()
        self.macroVariablesTab.setObjectName(u"macroVariablesTab")
        self.macroVariablesLayout = QVBoxLayout(self.macroVariablesTab)
        self.macroVariablesLayout.setObjectName(u"macroVariablesLayout")
        self.macroVariablesLayout.setContentsMargins(6, 6, 6, 6)
        self.variablesContextLabel = QLabel(self.macroVariablesTab)
        self.variablesContextLabel.setObjectName(u"variablesContextLabel")
        self.variablesContextLabel.setWordWrap(True)

        self.macroVariablesLayout.addWidget(self.variablesContextLabel)

        self.macroVariablesStatusLabel = QLabel(self.macroVariablesTab)
        self.macroVariablesStatusLabel.setObjectName(u"macroVariablesStatusLabel")
        self.macroVariablesStatusLabel.setWordWrap(True)

        self.macroVariablesLayout.addWidget(self.macroVariablesStatusLabel)

        self.macroVariablesTable = QTableView(self.macroVariablesTab)
        self.macroVariablesTable.setObjectName(u"macroVariablesTable")
        self.macroVariablesTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.macroVariablesTable.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.macroVariablesTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.macroVariablesTable.setSortingEnabled(False)
        self.macroVariablesTable.setWordWrap(False)

        self.macroVariablesLayout.addWidget(self.macroVariablesTable)

        self.tabWidget.addTab(self.macroVariablesTab, "")

        self.verticalLayout.addWidget(self.tabWidget)

        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.setObjectName(u"buttonLayout")
        self.filterCountLabel = QLabel(TokensDlg)
        self.filterCountLabel.setObjectName(u"filterCountLabel")

        self.buttonLayout.addWidget(self.filterCountLabel)

        self.buttonSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.buttonLayout.addItem(self.buttonSpacer)

        self.refreshButton = QPushButton(TokensDlg)
        self.refreshButton.setObjectName(u"refreshButton")

        self.buttonLayout.addWidget(self.refreshButton)

        self.exportCsvButton = QPushButton(TokensDlg)
        self.exportCsvButton.setObjectName(u"exportCsvButton")

        self.buttonLayout.addWidget(self.exportCsvButton)

        self.resetColumnsButton = QPushButton(TokensDlg)
        self.resetColumnsButton.setObjectName(u"resetColumnsButton")

        self.buttonLayout.addWidget(self.resetColumnsButton)


        self.verticalLayout.addLayout(self.buttonLayout)


        self.retranslateUi(TokensDlg)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(TokensDlg)
    # setupUi

    def retranslateUi(self, TokensDlg):
        TokensDlg.setWindowTitle(QCoreApplication.translate("TokensDlg", u"Tokens/Variables", None))
        self.filterCombo.setItemText(0, QCoreApplication.translate("TokensDlg", u"All", None))
        self.filterCombo.setItemText(1, QCoreApplication.translate("TokensDlg", u"Warnings", None))
        self.filterCombo.setItemText(2, QCoreApplication.translate("TokensDlg", u"Errors", None))

        self.searchEdit.setPlaceholderText(QCoreApplication.translate("TokensDlg", u"Search text...", None))
#if QT_CONFIG(tooltip)
        self.searchEdit.setToolTip(QCoreApplication.translate("TokensDlg", u"Search source text, tokens and diagnostics", None))
#endif // QT_CONFIG(tooltip)
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tokensTab), QCoreApplication.translate("TokensDlg", u"Tokens", None))
        self.variablesContextLabel.setText("")
        self.macroVariablesStatusLabel.setText(QCoreApplication.translate("TokensDlg", u"No execution data.", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.macroVariablesTab), QCoreApplication.translate("TokensDlg", u"Variables", None))
        self.filterCountLabel.setText(QCoreApplication.translate("TokensDlg", u"Rows: 0 / 0", None))
        self.refreshButton.setText(QCoreApplication.translate("TokensDlg", u"Refresh", None))
        self.exportCsvButton.setText(QCoreApplication.translate("TokensDlg", u"Export CSV", None))
        self.resetColumnsButton.setText(QCoreApplication.translate("TokensDlg", u"Reset Columns", None))
    # retranslateUi
