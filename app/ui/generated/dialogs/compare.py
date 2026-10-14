# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'compare.ui'
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
    QDialogButtonBox, QHBoxLayout, QLabel, QPlainTextEdit,
    QSizePolicy, QSplitter, QToolButton, QVBoxLayout,
    QWidget)

import app.resources.files_res  # noqa: F401  # Registers Qt resources on import.

class Ui_CompareDialog(object):
    def setupUi(self, CompareDialog):
        if not CompareDialog.objectName():
            CompareDialog.setObjectName(u"CompareDialog")
        CompareDialog.resize(1100, 650)
        CompareDialog.setMinimumSize(QSize(700, 360))
        self.verticalLayout = QVBoxLayout(CompareDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.splitter = QSplitter(CompareDialog)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.leftPanel = QWidget(self.splitter)
        self.leftPanel.setObjectName(u"leftPanel")
        self.leftLayout = QVBoxLayout(self.leftPanel)
        self.leftLayout.setObjectName(u"leftLayout")
        self.leftLayout.setContentsMargins(0, 0, 0, 0)
        self.leftHeader = QHBoxLayout()
        self.leftHeader.setObjectName(u"leftHeader")
        self.leftLabel = QLabel(self.leftPanel)
        self.leftLabel.setObjectName(u"leftLabel")

        self.leftHeader.addWidget(self.leftLabel)

        self.leftCombo = QComboBox(self.leftPanel)
        self.leftCombo.setObjectName(u"leftCombo")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.leftCombo.sizePolicy().hasHeightForWidth())
        self.leftCombo.setSizePolicy(sizePolicy)
        self.leftCombo.setMinimumContentsLength(12)
        self.leftCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)

        self.leftHeader.addWidget(self.leftCombo)

        self.leftOpenButton = QToolButton(self.leftPanel)
        self.leftOpenButton.setObjectName(u"leftOpenButton")
        icon = QIcon()
        icon.addFile(u":/resource/icons/open.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.leftOpenButton.setIcon(icon)

        self.leftHeader.addWidget(self.leftOpenButton)


        self.leftLayout.addLayout(self.leftHeader)

        self.leftEditor = QPlainTextEdit(self.leftPanel)
        self.leftEditor.setObjectName(u"leftEditor")
        self.leftEditor.setReadOnly(True)
        self.leftEditor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.leftEditor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.leftEditor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self.leftLayout.addWidget(self.leftEditor)

        self.splitter.addWidget(self.leftPanel)
        self.rightPanel = QWidget(self.splitter)
        self.rightPanel.setObjectName(u"rightPanel")
        self.rightLayout = QVBoxLayout(self.rightPanel)
        self.rightLayout.setObjectName(u"rightLayout")
        self.rightLayout.setContentsMargins(0, 0, 0, 0)
        self.rightHeader = QHBoxLayout()
        self.rightHeader.setObjectName(u"rightHeader")
        self.rightLabel = QLabel(self.rightPanel)
        self.rightLabel.setObjectName(u"rightLabel")

        self.rightHeader.addWidget(self.rightLabel)

        self.rightCombo = QComboBox(self.rightPanel)
        self.rightCombo.setObjectName(u"rightCombo")
        sizePolicy.setHeightForWidth(self.rightCombo.sizePolicy().hasHeightForWidth())
        self.rightCombo.setSizePolicy(sizePolicy)
        self.rightCombo.setMinimumContentsLength(12)
        self.rightCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)

        self.rightHeader.addWidget(self.rightCombo)

        self.rightOpenButton = QToolButton(self.rightPanel)
        self.rightOpenButton.setObjectName(u"rightOpenButton")
        self.rightOpenButton.setIcon(icon)

        self.rightHeader.addWidget(self.rightOpenButton)


        self.rightLayout.addLayout(self.rightHeader)

        self.rightEditor = QPlainTextEdit(self.rightPanel)
        self.rightEditor.setObjectName(u"rightEditor")
        self.rightEditor.setReadOnly(True)
        self.rightEditor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.rightEditor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.rightEditor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self.rightLayout.addWidget(self.rightEditor)

        self.splitter.addWidget(self.rightPanel)

        self.verticalLayout.addWidget(self.splitter)

        self.footerLayout = QHBoxLayout()
        self.footerLayout.setObjectName(u"footerLayout")
        self.changedLabel = QLabel(CompareDialog)
        self.changedLabel.setObjectName(u"changedLabel")

        self.footerLayout.addWidget(self.changedLabel)

        self.addedLabel = QLabel(CompareDialog)
        self.addedLabel.setObjectName(u"addedLabel")

        self.footerLayout.addWidget(self.addedLabel)

        self.removedLabel = QLabel(CompareDialog)
        self.removedLabel.setObjectName(u"removedLabel")

        self.footerLayout.addWidget(self.removedLabel)

        self.statusLabel = QLabel(CompareDialog)
        self.statusLabel.setObjectName(u"statusLabel")
        self.statusLabel.setWordWrap(True)

        self.footerLayout.addWidget(self.statusLabel)

        self.refreshButton = QToolButton(CompareDialog)
        self.refreshButton.setObjectName(u"refreshButton")
        icon1 = QIcon()
        icon1.addFile(u":/resource/icons/refresh.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.refreshButton.setIcon(icon1)
        self.refreshButton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        self.footerLayout.addWidget(self.refreshButton)

        self.buttonBox = QDialogButtonBox(CompareDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Close)
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.buttonBox.sizePolicy().hasHeightForWidth())
        self.buttonBox.setSizePolicy(sizePolicy1)

        self.footerLayout.addWidget(self.buttonBox)

        self.footerLayout.setStretch(3, 1)

        self.verticalLayout.addLayout(self.footerLayout)

#if QT_CONFIG(shortcut)
        self.leftLabel.setBuddy(self.leftCombo)
        self.rightLabel.setBuddy(self.rightCombo)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(CompareDialog)

        QMetaObject.connectSlotsByName(CompareDialog)
    # setupUi

    def retranslateUi(self, CompareDialog):
        CompareDialog.setWindowTitle(QCoreApplication.translate("CompareDialog", u"Compare", None))
        self.leftLabel.setText(QCoreApplication.translate("CompareDialog", u"File A", None))
        self.leftCombo.setPlaceholderText(QCoreApplication.translate("CompareDialog", u"Select a document or open a file", None))
#if QT_CONFIG(accessibility)
        self.leftCombo.setAccessibleName(QCoreApplication.translate("CompareDialog", u"File A", None))
#endif // QT_CONFIG(accessibility)
#if QT_CONFIG(tooltip)
        self.leftOpenButton.setToolTip(QCoreApplication.translate("CompareDialog", u"Open NC program", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.leftOpenButton.setAccessibleName(QCoreApplication.translate("CompareDialog", u"Open file A", None))
#endif // QT_CONFIG(accessibility)
#if QT_CONFIG(accessibility)
        self.leftEditor.setAccessibleName(QCoreApplication.translate("CompareDialog", u"Text of file A", None))
#endif // QT_CONFIG(accessibility)
        self.rightLabel.setText(QCoreApplication.translate("CompareDialog", u"File B", None))
        self.rightCombo.setPlaceholderText(QCoreApplication.translate("CompareDialog", u"Select a document or open a file", None))
#if QT_CONFIG(accessibility)
        self.rightCombo.setAccessibleName(QCoreApplication.translate("CompareDialog", u"File B", None))
#endif // QT_CONFIG(accessibility)
#if QT_CONFIG(tooltip)
        self.rightOpenButton.setToolTip(QCoreApplication.translate("CompareDialog", u"Open NC program", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.rightOpenButton.setAccessibleName(QCoreApplication.translate("CompareDialog", u"Open file B", None))
#endif // QT_CONFIG(accessibility)
#if QT_CONFIG(accessibility)
        self.rightEditor.setAccessibleName(QCoreApplication.translate("CompareDialog", u"Text of file B", None))
#endif // QT_CONFIG(accessibility)
        self.changedLabel.setText(QCoreApplication.translate("CompareDialog", u"Changed", None))
        self.addedLabel.setText(QCoreApplication.translate("CompareDialog", u"Added", None))
        self.removedLabel.setText(QCoreApplication.translate("CompareDialog", u"Removed", None))
        self.statusLabel.setText(QCoreApplication.translate("CompareDialog", u"Select two sources to compare.", None))
        self.refreshButton.setText(QCoreApplication.translate("CompareDialog", u"Refresh", None))
#if QT_CONFIG(tooltip)
        self.refreshButton.setToolTip(QCoreApplication.translate("CompareDialog", u"Refresh comparison (reload disk sources)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.refreshButton.setAccessibleName(QCoreApplication.translate("CompareDialog", u"Refresh", None))
#endif // QT_CONFIG(accessibility)
    # retranslateUi
