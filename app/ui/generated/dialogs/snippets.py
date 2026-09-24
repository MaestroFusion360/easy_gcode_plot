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

from app.ui.support.snippet_editor import ZoomableSnippetEditor

import app.resources.files_res  # noqa: F401  # Registers Qt resources on import.

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
        self.snippetEditor = ZoomableSnippetEditor(self.splitter)
        self.snippetEditor.setObjectName(u"snippetEditor")
        font = QFont()
        font.setFamilies([u"Courier New"])
        font.setPointSize(9)
        self.snippetEditor.setFont(font)
        self.snippetEditor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.splitter.addWidget(self.snippetEditor)

        self.verticalLayout.addWidget(self.splitter)

        self.buttonsLayout = QHBoxLayout()
        self.buttonsLayout.setObjectName(u"buttonsLayout")
        self.upButton = QPushButton(SnippetsDialog)
        self.upButton.setObjectName(u"upButton")
        icon = QIcon()
        icon.addFile(u":/resource/icons/up.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.upButton.setIcon(icon)
        self.upButton.setIconSize(QSize(24, 24))

        self.buttonsLayout.addWidget(self.upButton)

        self.downButton = QPushButton(SnippetsDialog)
        self.downButton.setObjectName(u"downButton")
        icon1 = QIcon()
        icon1.addFile(u":/resource/icons/down.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.downButton.setIcon(icon1)
        self.downButton.setIconSize(QSize(24, 24))

        self.buttonsLayout.addWidget(self.downButton)

        self.addButton = QPushButton(SnippetsDialog)
        self.addButton.setObjectName(u"addButton")
        icon2 = QIcon()
        icon2.addFile(u":/resource/icons/add.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.addButton.setIcon(icon2)
        self.addButton.setIconSize(QSize(24, 24))

        self.buttonsLayout.addWidget(self.addButton)

        self.saveButton = QPushButton(SnippetsDialog)
        self.saveButton.setObjectName(u"saveButton")
        icon3 = QIcon()
        icon3.addFile(u":/resource/icons/save.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.saveButton.setIcon(icon3)
        self.saveButton.setIconSize(QSize(24, 24))

        self.buttonsLayout.addWidget(self.saveButton)

        self.renameButton = QPushButton(SnippetsDialog)
        self.renameButton.setObjectName(u"renameButton")
        icon4 = QIcon()
        icon4.addFile(u":/resource/icons/rename.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.renameButton.setIcon(icon4)
        self.renameButton.setIconSize(QSize(24, 24))

        self.buttonsLayout.addWidget(self.renameButton)

        self.deleteButton = QPushButton(SnippetsDialog)
        self.deleteButton.setObjectName(u"deleteButton")
        icon5 = QIcon()
        icon5.addFile(u":/resource/icons/trash.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.deleteButton.setIcon(icon5)
        self.deleteButton.setIconSize(QSize(24, 24))

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
#if QT_CONFIG(tooltip)
        self.upButton.setToolTip(QCoreApplication.translate("SnippetsDialog", u"Up", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.upButton.setAccessibleName(QCoreApplication.translate("SnippetsDialog", u"Up", None))
#endif // QT_CONFIG(accessibility)
#if QT_CONFIG(tooltip)
        self.downButton.setToolTip(QCoreApplication.translate("SnippetsDialog", u"Down", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.downButton.setAccessibleName(QCoreApplication.translate("SnippetsDialog", u"Down", None))
#endif // QT_CONFIG(accessibility)
#if QT_CONFIG(tooltip)
        self.addButton.setToolTip(QCoreApplication.translate("SnippetsDialog", u"Add", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.addButton.setAccessibleName(QCoreApplication.translate("SnippetsDialog", u"Add", None))
#endif // QT_CONFIG(accessibility)
#if QT_CONFIG(tooltip)
        self.saveButton.setToolTip(QCoreApplication.translate("SnippetsDialog", u"Save", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.saveButton.setAccessibleName(QCoreApplication.translate("SnippetsDialog", u"Save", None))
#endif // QT_CONFIG(accessibility)
#if QT_CONFIG(tooltip)
        self.renameButton.setToolTip(QCoreApplication.translate("SnippetsDialog", u"Rename", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.renameButton.setAccessibleName(QCoreApplication.translate("SnippetsDialog", u"Rename", None))
#endif // QT_CONFIG(accessibility)
#if QT_CONFIG(tooltip)
        self.deleteButton.setToolTip(QCoreApplication.translate("SnippetsDialog", u"Delete", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.deleteButton.setAccessibleName(QCoreApplication.translate("SnippetsDialog", u"Delete", None))
#endif // QT_CONFIG(accessibility)
        self.insertButton.setText(QCoreApplication.translate("SnippetsDialog", u"Insert", None))
        self.cancelButton.setText(QCoreApplication.translate("SnippetsDialog", u"Cancel", None))
    # retranslateUi
