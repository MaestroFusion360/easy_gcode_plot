# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'turning_tools.ui'
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
    QPushButton, QSizePolicy, QSpacerItem, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

class Ui_TurningToolsDlg(object):
    def setupUi(self, TurningToolsDlg):
        if not TurningToolsDlg.objectName():
            TurningToolsDlg.setObjectName(u"TurningToolsDlg")
        TurningToolsDlg.resize(760, 520)
        TurningToolsDlg.setMinimumSize(QSize(640, 420))
        self.verticalLayout = QVBoxLayout(TurningToolsDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.titleLabel = QLabel(TurningToolsDlg)
        self.titleLabel.setObjectName(u"titleLabel")

        self.verticalLayout.addWidget(self.titleLabel)

        self.helpLabel = QLabel(TurningToolsDlg)
        self.helpLabel.setObjectName(u"helpLabel")
        self.helpLabel.setWordWrap(True)

        self.verticalLayout.addWidget(self.helpLabel)

        self.toolTable = QTableWidget(TurningToolsDlg)
        if (self.toolTable.columnCount() < 5):
            self.toolTable.setColumnCount(5)
        __qtablewidgetitem = QTableWidgetItem()
        self.toolTable.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.toolTable.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.toolTable.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.toolTable.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.toolTable.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        self.toolTable.setObjectName(u"toolTable")
        self.toolTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.toolTable.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.toolTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.toolTable.setColumnCount(5)

        self.verticalLayout.addWidget(self.toolTable)

        self.toolButtonsLayout = QHBoxLayout()
        self.toolButtonsLayout.setObjectName(u"toolButtonsLayout")
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.toolButtonsLayout.addItem(self.horizontalSpacer)

        self.addButton = QPushButton(TurningToolsDlg)
        self.addButton.setObjectName(u"addButton")

        self.toolButtonsLayout.addWidget(self.addButton)

        self.editButton = QPushButton(TurningToolsDlg)
        self.editButton.setObjectName(u"editButton")

        self.toolButtonsLayout.addWidget(self.editButton)

        self.removeButton = QPushButton(TurningToolsDlg)
        self.removeButton.setObjectName(u"removeButton")

        self.toolButtonsLayout.addWidget(self.removeButton)


        self.verticalLayout.addLayout(self.toolButtonsLayout)

        self.buttonBox = QDialogButtonBox(TurningToolsDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(TurningToolsDlg)
        self.buttonBox.accepted.connect(TurningToolsDlg.accept)
        self.buttonBox.rejected.connect(TurningToolsDlg.reject)

        QMetaObject.connectSlotsByName(TurningToolsDlg)
    # setupUi

    def retranslateUi(self, TurningToolsDlg):
        TurningToolsDlg.setWindowTitle(QCoreApplication.translate("TurningToolsDlg", u"Turning Tools", None))
        self.titleLabel.setText(QCoreApplication.translate("TurningToolsDlg", u"Tool Nose Compensation", None))
        self.helpLabel.setText(QCoreApplication.translate("TurningToolsDlg", u"Turning tools require a nose radius and one of the nine FANUC tip orientations.", None))
        ___qtablewidgetitem = self.toolTable.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("TurningToolsDlg", u"Tip orientation", None))
        ___qtablewidgetitem1 = self.toolTable.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("TurningToolsDlg", u"T code", None))
        ___qtablewidgetitem2 = self.toolTable.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("TurningToolsDlg", u"Type", None))
        ___qtablewidgetitem3 = self.toolTable.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("TurningToolsDlg", u"Nose radius, mm", None))
        ___qtablewidgetitem4 = self.toolTable.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("TurningToolsDlg", u"Description", None))
        self.addButton.setText(QCoreApplication.translate("TurningToolsDlg", u"Add...", None))
        self.editButton.setText(QCoreApplication.translate("TurningToolsDlg", u"Edit...", None))
        self.removeButton.setText(QCoreApplication.translate("TurningToolsDlg", u"Remove", None))
    # retranslateUi
