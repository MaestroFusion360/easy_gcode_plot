# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'snippets_panel.ui'
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
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QSizePolicy, QToolButton, QVBoxLayout, QWidget)

class Ui_SnippetsPanelForm(object):
    def setupUi(self, SnippetsPanelForm):
        if not SnippetsPanelForm.objectName():
            SnippetsPanelForm.setObjectName(u"SnippetsPanelForm")
        SnippetsPanelForm.setMinimumSize(QSize(260, 0))
        self.rootLayout = QVBoxLayout(SnippetsPanelForm)
        self.rootLayout.setSpacing(5)
        self.rootLayout.setObjectName(u"rootLayout")
        self.rootLayout.setContentsMargins(6, 6, 6, 6)
        self.controllerLabel = QLabel(SnippetsPanelForm)
        self.controllerLabel.setObjectName(u"controllerLabel")

        self.rootLayout.addWidget(self.controllerLabel)

        self.groupCombo = QComboBox(SnippetsPanelForm)
        self.groupCombo.addItem("")
        self.groupCombo.addItem("")
        self.groupCombo.addItem("")
        self.groupCombo.addItem("")
        self.groupCombo.addItem("")
        self.groupCombo.setObjectName(u"groupCombo")

        self.rootLayout.addWidget(self.groupCombo)

        self.searchEdit = QLineEdit(SnippetsPanelForm)
        self.searchEdit.setObjectName(u"searchEdit")
        self.searchEdit.setClearButtonEnabled(True)

        self.rootLayout.addWidget(self.searchEdit)

        self.snippetList = QListWidget(SnippetsPanelForm)
        self.snippetList.setObjectName(u"snippetList")
        self.snippetList.setAlternatingRowColors(False)
        self.snippetList.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.snippetList.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.snippetList.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.rootLayout.addWidget(self.snippetList)

        self.actionsLayout = QHBoxLayout()
        self.actionsLayout.setSpacing(3)
        self.actionsLayout.setObjectName(u"actionsLayout")
        self.insertButton = QToolButton(SnippetsPanelForm)
        self.insertButton.setObjectName(u"insertButton")

        self.actionsLayout.addWidget(self.insertButton)

        self.editButton = QToolButton(SnippetsPanelForm)
        self.editButton.setObjectName(u"editButton")

        self.actionsLayout.addWidget(self.editButton)


        self.rootLayout.addLayout(self.actionsLayout)


        self.retranslateUi(SnippetsPanelForm)

        QMetaObject.connectSlotsByName(SnippetsPanelForm)
    # setupUi

    def retranslateUi(self, SnippetsPanelForm):
        SnippetsPanelForm.setWindowTitle(QCoreApplication.translate("SnippetsPanelForm", u"Snippets", None))
        self.controllerLabel.setText(QCoreApplication.translate("SnippetsPanelForm", u"Fanuc", None))
        self.groupCombo.setItemText(0, QCoreApplication.translate("SnippetsPanelForm", u"All Snippets", None))
        self.groupCombo.setItemText(1, QCoreApplication.translate("SnippetsPanelForm", u"Program", None))
        self.groupCombo.setItemText(2, QCoreApplication.translate("SnippetsPanelForm", u"Motion", None))
        self.groupCombo.setItemText(3, QCoreApplication.translate("SnippetsPanelForm", u"Cycles", None))
        self.groupCombo.setItemText(4, QCoreApplication.translate("SnippetsPanelForm", u"Formulas", None))

#if QT_CONFIG(accessibility)
        self.groupCombo.setAccessibleName(QCoreApplication.translate("SnippetsPanelForm", u"Snippet group", None))
#endif // QT_CONFIG(accessibility)
        self.searchEdit.setPlaceholderText(QCoreApplication.translate("SnippetsPanelForm", u"Find snippet...", None))
#if QT_CONFIG(accessibility)
        self.searchEdit.setAccessibleName(QCoreApplication.translate("SnippetsPanelForm", u"Find snippet", None))
#endif // QT_CONFIG(accessibility)
#if QT_CONFIG(accessibility)
        self.snippetList.setAccessibleName(QCoreApplication.translate("SnippetsPanelForm", u"Snippets", None))
#endif // QT_CONFIG(accessibility)
        self.insertButton.setText(QCoreApplication.translate("SnippetsPanelForm", u"Insert", None))
        self.editButton.setText(QCoreApplication.translate("SnippetsPanelForm", u"Edit Snippets", None))
    # retranslateUi
