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
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QPlainTextEdit,
    QPushButton, QSizePolicy, QSpacerItem, QSplitter,
    QVBoxLayout, QWidget)

from app.ui.support.snippet_editor import ZoomableSnippetEditor
from app.ui.support.snippet_preview import PictureLabel

import app.resources.files_res  # noqa: F401  # Registers Qt resources on import.

class Ui_SnippetsDialog(object):
    def setupUi(self, SnippetsDialog):
        if not SnippetsDialog.objectName():
            SnippetsDialog.setObjectName(u"SnippetsDialog")
        SnippetsDialog.resize(1100, 650)
        SnippetsDialog.setMinimumSize(QSize(900, 560))
        self.verticalLayout = QVBoxLayout(SnippetsDialog)
        self.verticalLayout.setSpacing(8)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(10, 10, 10, 10)
        self.languageLayout = QHBoxLayout()
        self.languageLayout.setObjectName(u"languageLayout")
        self.languageLabel = QLabel(SnippetsDialog)
        self.languageLabel.setObjectName(u"languageLabel")

        self.languageLayout.addWidget(self.languageLabel)

        self.languageCombo = QComboBox(SnippetsDialog)
        self.languageCombo.setObjectName(u"languageCombo")
        self.languageCombo.setMinimumSize(QSize(180, 0))
        self.languageCombo.setMaximumSize(QSize(260, 16777215))

        self.languageLayout.addWidget(self.languageCombo)

        self.controllerSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.languageLayout.addItem(self.controllerSpacer)


        self.verticalLayout.addLayout(self.languageLayout)

        self.splitter = QSplitter(SnippetsDialog)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.snippetList = QListWidget(self.splitter)
        self.snippetList.setObjectName(u"snippetList")
        self.snippetList.setMinimumSize(QSize(200, 0))
        self.snippetList.setMaximumSize(QSize(270, 16777215))
        self.splitter.addWidget(self.snippetList)
        self.templatePane = QWidget(self.splitter)
        self.templatePane.setObjectName(u"templatePane")
        self.templateLayout = QVBoxLayout(self.templatePane)
        self.templateLayout.setSpacing(6)
        self.templateLayout.setObjectName(u"templateLayout")
        self.templateLayout.setContentsMargins(4, 0, 0, 0)
        self.pictureLayout = QHBoxLayout()
        self.pictureLayout.setObjectName(u"pictureLayout")
        self.pictureButton = QPushButton(self.templatePane)
        self.pictureButton.setObjectName(u"pictureButton")
        self.pictureButton.setMinimumSize(QSize(90, 28))
        self.pictureButton.setStyleSheet(u"QPushButton#pictureButton {\n"
"    padding-left: 12px;\n"
"    padding-right: 24px;\n"
"}\n"
"QPushButton#pictureButton::menu-indicator {\n"
"    subcontrol-origin: padding;\n"
"    subcontrol-position: center right;\n"
"    right: 8px;\n"
"    width: 10px;\n"
"    height: 10px;\n"
"}")

        self.pictureLayout.addWidget(self.pictureButton)

        self.pictureStatusLabel = QLabel(self.templatePane)
        self.pictureStatusLabel.setObjectName(u"pictureStatusLabel")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pictureStatusLabel.sizePolicy().hasHeightForWidth())
        self.pictureStatusLabel.setSizePolicy(sizePolicy)
        self.pictureStatusLabel.setTextFormat(Qt.TextFormat.PlainText)

        self.pictureLayout.addWidget(self.pictureStatusLabel)


        self.templateLayout.addLayout(self.pictureLayout)

        self.previewSplitter = QSplitter(self.templatePane)
        self.previewSplitter.setObjectName(u"previewSplitter")
        self.previewSplitter.setOrientation(Qt.Orientation.Horizontal)
        self.previewSplitter.setChildrenCollapsible(False)
        self.snippetEditor = ZoomableSnippetEditor(self.previewSplitter)
        self.snippetEditor.setObjectName(u"snippetEditor")
        font = QFont()
        font.setFamilies([u"Courier New"])
        font.setPointSize(9)
        self.snippetEditor.setFont(font)
        self.snippetEditor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.previewSplitter.addWidget(self.snippetEditor)
        self.picturePreview = PictureLabel(self.previewSplitter)
        self.picturePreview.setObjectName(u"picturePreview")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.picturePreview.sizePolicy().hasHeightForWidth())
        self.picturePreview.setSizePolicy(sizePolicy1)
        self.picturePreview.setMinimumSize(QSize(320, 260))
        self.picturePreview.setMaximumSize(QSize(16777215, 16777215))
        self.picturePreview.setStyleSheet(u"QLabel#picturePreview { background: palette(base); border: 1px solid palette(mid); }")
        self.picturePreview.setVisible(False)
        self.previewSplitter.addWidget(self.picturePreview)

        self.templateLayout.addWidget(self.previewSplitter)

        self.templateLayout.setStretch(1, 1)
        self.splitter.addWidget(self.templatePane)

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

        self.updateDefaultsButton = QPushButton(SnippetsDialog)
        self.updateDefaultsButton.setObjectName(u"updateDefaultsButton")

        self.buttonsLayout.addWidget(self.updateDefaultsButton)

        self.insertButton = QPushButton(SnippetsDialog)
        self.insertButton.setObjectName(u"insertButton")

        self.buttonsLayout.addWidget(self.insertButton)


        self.verticalLayout.addLayout(self.buttonsLayout)

#if QT_CONFIG(shortcut)
        self.languageLabel.setBuddy(self.languageCombo)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(SnippetsDialog)

        QMetaObject.connectSlotsByName(SnippetsDialog)
    # setupUi

    def retranslateUi(self, SnippetsDialog):
        SnippetsDialog.setWindowTitle(QCoreApplication.translate("SnippetsDialog", u"Snippets", None))
        self.languageLabel.setText(QCoreApplication.translate("SnippetsDialog", u"Controller", None))
#if QT_CONFIG(tooltip)
        self.pictureButton.setToolTip(QCoreApplication.translate("SnippetsDialog", u"Picture", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.pictureButton.setAccessibleName(QCoreApplication.translate("SnippetsDialog", u"Picture", None))
#endif // QT_CONFIG(accessibility)
        self.pictureButton.setText(QCoreApplication.translate("SnippetsDialog", u"Picture", None))
        self.pictureStatusLabel.setText(QCoreApplication.translate("SnippetsDialog", u"No picture", None))
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
#if QT_CONFIG(tooltip)
        self.updateDefaultsButton.setToolTip(QCoreApplication.translate("SnippetsDialog", u"Restore all standard templates for the selected controller. Custom templates and attached pictures are kept.", None))
#endif // QT_CONFIG(tooltip)
        self.updateDefaultsButton.setText(QCoreApplication.translate("SnippetsDialog", u"Update Defaults", None))
        self.insertButton.setText(QCoreApplication.translate("SnippetsDialog", u"Insert", None))
    # retranslateUi
