# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'snippets.ui'
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
from PyQt6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QListWidget,
    QListWidgetItem, QPlainTextEdit, QPushButton, QSizePolicy,
    QSpacerItem, QSplitter, QVBoxLayout, QWidget)

class Ui_SnippetsDialog(object):
    def setupUi(self, SnippetsDialog):
        if not SnippetsDialog.objectName():
            SnippetsDialog.setObjectName(u"SnippetsDialog")
        SnippetsDialog.setMinimumSize(QSize(700, 430))
        self.verticalLayout = QVBoxLayout(SnippetsDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.splitter = QSplitter(SnippetsDialog)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.snippetList = QListWidget(self.splitter)
        self.snippetList.setObjectName(u"snippetList")
        self.splitter.addWidget(self.snippetList)
        self.snippetEditor = QPlainTextEdit(self.splitter)
        self.snippetEditor.setObjectName(u"snippetEditor")
        font = QFont()
        font.setFamilies([u"Courier New"])
        font.setPointSize(12)
        self.snippetEditor.setFont(font)
        self.snippetEditor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.splitter.addWidget(self.snippetEditor)

        self.verticalLayout.addWidget(self.splitter)

        self.buttonsLayout = QHBoxLayout()
        self.buttonsLayout.setObjectName(u"buttonsLayout")
        self.upButton = QPushButton(SnippetsDialog)
        self.upButton.setObjectName(u"upButton")

        self.buttonsLayout.addWidget(self.upButton)

        self.downButton = QPushButton(SnippetsDialog)
        self.downButton.setObjectName(u"downButton")

        self.buttonsLayout.addWidget(self.downButton)

        self.addButton = QPushButton(SnippetsDialog)
        self.addButton.setObjectName(u"addButton")

        self.buttonsLayout.addWidget(self.addButton)

        self.saveButton = QPushButton(SnippetsDialog)
        self.saveButton.setObjectName(u"saveButton")

        self.buttonsLayout.addWidget(self.saveButton)

        self.renameButton = QPushButton(SnippetsDialog)
        self.renameButton.setObjectName(u"renameButton")

        self.buttonsLayout.addWidget(self.renameButton)

        self.deleteButton = QPushButton(SnippetsDialog)
        self.deleteButton.setObjectName(u"deleteButton")

        self.buttonsLayout.addWidget(self.deleteButton)

        self.buttonSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.buttonsLayout.addItem(self.buttonSpacer)

        self.insertButton = QPushButton(SnippetsDialog)
        self.insertButton.setObjectName(u"insertButton")

        self.buttonsLayout.addWidget(self.insertButton)

        self.cancelButton = QPushButton(SnippetsDialog)
        self.cancelButton.setObjectName(u"cancelButton")

        self.buttonsLayout.addWidget(self.cancelButton)


        self.verticalLayout.addLayout(self.buttonsLayout)


        self.retranslateUi(SnippetsDialog)

        QMetaObject.connectSlotsByName(SnippetsDialog)
    # setupUi

    def retranslateUi(self, SnippetsDialog):
        SnippetsDialog.setWindowTitle(QCoreApplication.translate("SnippetsDialog", u"Snippets", None))
        self.upButton.setText(QCoreApplication.translate("SnippetsDialog", u"Up", None))
        self.downButton.setText(QCoreApplication.translate("SnippetsDialog", u"Down", None))
        self.addButton.setText(QCoreApplication.translate("SnippetsDialog", u"Add", None))
        self.saveButton.setText(QCoreApplication.translate("SnippetsDialog", u"Save", None))
        self.renameButton.setText(QCoreApplication.translate("SnippetsDialog", u"Rename", None))
        self.deleteButton.setText(QCoreApplication.translate("SnippetsDialog", u"Delete", None))
        self.insertButton.setText(QCoreApplication.translate("SnippetsDialog", u"Insert", None))
        self.cancelButton.setText(QCoreApplication.translate("SnippetsDialog", u"Cancel", None))
    # retranslateUi
