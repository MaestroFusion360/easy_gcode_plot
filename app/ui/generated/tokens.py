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
from PyQt6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QDialog,
    QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QSizePolicy, QSpacerItem, QTableView,
    QVBoxLayout, QWidget)

class Ui_TokensDlg(object):
    def setupUi(self, TokensDlg):
        if not TokensDlg.objectName():
            TokensDlg.setObjectName(u"TokensDlg")
        TokensDlg.resize(860, 720)
        TokensDlg.setMinimumSize(QSize(760, 560))
        TokensDlg.setModal(False)
        self.verticalLayout = QVBoxLayout(TokensDlg)
        self.verticalLayout.setSpacing(6)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(8, 8, 8, 8)
        self.headerLayout = QHBoxLayout()
        self.headerLayout.setSpacing(10)
        self.headerLayout.setObjectName(u"headerLayout")
        self.titleLabel = QLabel(TokensDlg)
        self.titleLabel.setObjectName(u"titleLabel")
        font = QFont()
        font.setBold(True)
        self.titleLabel.setFont(font)

        self.headerLayout.addWidget(self.titleLabel)

        self.legendLabel = QLabel(TokensDlg)
        self.legendLabel.setObjectName(u"legendLabel")

        self.headerLayout.addWidget(self.legendLabel)

        self.headerSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.headerLayout.addItem(self.headerSpacer)


        self.verticalLayout.addLayout(self.headerLayout)

        self.tokenTable = QTableView(TokensDlg)
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

        self.verticalLayout.addWidget(self.tokenTable)

        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.setObjectName(u"buttonLayout")
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

        self.buttonBox = QDialogButtonBox(TokensDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Close)

        self.buttonLayout.addWidget(self.buttonBox)


        self.verticalLayout.addLayout(self.buttonLayout)


        self.retranslateUi(TokensDlg)
        self.buttonBox.rejected.connect(TokensDlg.reject)

        QMetaObject.connectSlotsByName(TokensDlg)
    # setupUi

    def retranslateUi(self, TokensDlg):
        TokensDlg.setWindowTitle(QCoreApplication.translate("TokensDlg", u"Tokens", None))
        self.titleLabel.setText(QCoreApplication.translate("TokensDlg", u"Program Token Validation", None))
        self.legendLabel.setText(QCoreApplication.translate("TokensDlg", u"Green: parsed, Red: suspicious line", None))
        self.refreshButton.setText(QCoreApplication.translate("TokensDlg", u"Refresh", None))
        self.exportCsvButton.setText(QCoreApplication.translate("TokensDlg", u"Export CSV", None))
        self.resetColumnsButton.setText(QCoreApplication.translate("TokensDlg", u"Reset Columns", None))
    # retranslateUi
