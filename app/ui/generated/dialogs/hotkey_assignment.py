# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'hotkey_assignment.ui'
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
from PyQt6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QSizePolicy, QVBoxLayout,
    QWidget)

class Ui_HotkeyAssignmentDlg(object):
    def setupUi(self, HotkeyAssignmentDlg):
        if not HotkeyAssignmentDlg.objectName():
            HotkeyAssignmentDlg.setObjectName(u"HotkeyAssignmentDlg")
        HotkeyAssignmentDlg.resize(430, 110)
        self.verticalLayout = QVBoxLayout(HotkeyAssignmentDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.commandForm = QFormLayout()
        self.commandForm.setObjectName(u"commandForm")
        self.commandLabel = QLabel(HotkeyAssignmentDlg)
        self.commandLabel.setObjectName(u"commandLabel")

        self.commandForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.commandLabel)

        self.commandEdit = QLineEdit(HotkeyAssignmentDlg)
        self.commandEdit.setObjectName(u"commandEdit")
        self.commandEdit.setReadOnly(True)

        self.commandForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.commandEdit)


        self.verticalLayout.addLayout(self.commandForm)

        self.shortcutLayout = QHBoxLayout()
        self.shortcutLayout.setObjectName(u"shortcutLayout")
        self.ctrlCheck = QCheckBox(HotkeyAssignmentDlg)
        self.ctrlCheck.setObjectName(u"ctrlCheck")

        self.shortcutLayout.addWidget(self.ctrlCheck)

        self.altCheck = QCheckBox(HotkeyAssignmentDlg)
        self.altCheck.setObjectName(u"altCheck")

        self.shortcutLayout.addWidget(self.altCheck)

        self.shiftCheck = QCheckBox(HotkeyAssignmentDlg)
        self.shiftCheck.setObjectName(u"shiftCheck")

        self.shortcutLayout.addWidget(self.shiftCheck)

        self.metaCheck = QCheckBox(HotkeyAssignmentDlg)
        self.metaCheck.setObjectName(u"metaCheck")

        self.shortcutLayout.addWidget(self.metaCheck)

        self.keyCombo = QComboBox(HotkeyAssignmentDlg)
        self.keyCombo.setObjectName(u"keyCombo")

        self.shortcutLayout.addWidget(self.keyCombo)


        self.verticalLayout.addLayout(self.shortcutLayout)

        self.buttonBox = QDialogButtonBox(HotkeyAssignmentDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(HotkeyAssignmentDlg)
        self.buttonBox.accepted.connect(HotkeyAssignmentDlg.accept)
        self.buttonBox.rejected.connect(HotkeyAssignmentDlg.reject)

        QMetaObject.connectSlotsByName(HotkeyAssignmentDlg)
    # setupUi

    def retranslateUi(self, HotkeyAssignmentDlg):
        HotkeyAssignmentDlg.setWindowTitle(QCoreApplication.translate("HotkeyAssignmentDlg", u"Assign shortcut", None))
        self.commandLabel.setText(QCoreApplication.translate("HotkeyAssignmentDlg", u"Command", None))
        self.ctrlCheck.setText(QCoreApplication.translate("HotkeyAssignmentDlg", u"Ctrl", None))
        self.altCheck.setText(QCoreApplication.translate("HotkeyAssignmentDlg", u"Alt", None))
        self.shiftCheck.setText(QCoreApplication.translate("HotkeyAssignmentDlg", u"Shift", None))
        self.metaCheck.setText(QCoreApplication.translate("HotkeyAssignmentDlg", u"Meta", None))
    # retranslateUi
