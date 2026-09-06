# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'about.ui'
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
from PyQt6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QFrame, QHBoxLayout, QLabel, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget)

import app.resources.files_res  # noqa: F401  # Registers Qt resources on import.

class Ui_AboutDlg(object):
    def setupUi(self, AboutDlg):
        if not AboutDlg.objectName():
            AboutDlg.setObjectName(u"AboutDlg")
        AboutDlg.resize(520, 310)
        AboutDlg.setMinimumSize(QSize(520, 310))
        AboutDlg.setMaximumSize(QSize(520, 310))
        self.verticalLayout = QVBoxLayout(AboutDlg)
        self.verticalLayout.setSpacing(10)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(18, 18, 18, 12)
        self.headerLayout = QHBoxLayout()
        self.headerLayout.setSpacing(16)
        self.headerLayout.setObjectName(u"headerLayout")
        self.logoLabel = QLabel(AboutDlg)
        self.logoLabel.setObjectName(u"logoLabel")
        self.logoLabel.setMinimumSize(QSize(72, 72))
        self.logoLabel.setMaximumSize(QSize(72, 72))
        self.logoLabel.setPixmap(QPixmap(u":/resource/icons/logo.png"))
        self.logoLabel.setScaledContents(True)
        self.logoLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.headerLayout.addWidget(self.logoLabel)

        self.titleLayout = QVBoxLayout()
        self.titleLayout.setObjectName(u"titleLayout")
        self.titleLabel = QLabel(AboutDlg)
        self.titleLabel.setObjectName(u"titleLabel")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        self.titleLabel.setFont(font)

        self.titleLayout.addWidget(self.titleLabel)

        self.versionLabel = QLabel(AboutDlg)
        self.versionLabel.setObjectName(u"versionLabel")

        self.titleLayout.addWidget(self.versionLabel)


        self.headerLayout.addLayout(self.titleLayout)


        self.verticalLayout.addLayout(self.headerLayout)

        self.line = QFrame(AboutDlg)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout.addWidget(self.line)

        self.descriptionLabel = QLabel(AboutDlg)
        self.descriptionLabel.setObjectName(u"descriptionLabel")
        self.descriptionLabel.setWordWrap(True)
        self.descriptionLabel.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.verticalLayout.addWidget(self.descriptionLabel)

        self.licenseLabel = QLabel(AboutDlg)
        self.licenseLabel.setObjectName(u"licenseLabel")
        self.licenseLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout.addWidget(self.licenseLabel)

        self.dateLabel = QLabel(AboutDlg)
        self.dateLabel.setObjectName(u"dateLabel")
        self.dateLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout.addWidget(self.dateLabel)

        self.verticalSpacer = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)

        self.buttonBox = QDialogButtonBox(AboutDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Ok)
        self.buttonBox.setCenterButtons(True)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(AboutDlg)
        self.buttonBox.accepted.connect(AboutDlg.accept)

        QMetaObject.connectSlotsByName(AboutDlg)
    # setupUi

    def retranslateUi(self, AboutDlg):
        AboutDlg.setWindowTitle(QCoreApplication.translate("AboutDlg", u"About Easy G-code Plot", None))
        self.titleLabel.setText(QCoreApplication.translate("AboutDlg", u"Easy G-code Plot", None))
        self.versionLabel.setText(QCoreApplication.translate("AboutDlg", u"Version", None))
        self.descriptionLabel.setText(QCoreApplication.translate("AboutDlg", u"Easy G-code Plot is a FANUC/ISO G-code viewer, editor, analyzer and verifier for turning and milling. Version 1.2.0 introduces a shared native Python CNC kernel, authoritative logical Motion Trace, Macro B/control flow, turning cycles, native XYZ milling, trajectory playback/picking and source-aware expanded program export for both machine modes.", None))
        self.licenseLabel.setText(QCoreApplication.translate("AboutDlg", u"Free and open-source software distributed under the MIT License.", None))
        self.dateLabel.setText(QCoreApplication.translate("AboutDlg", u"\u00a9 2025\u20132026 MaestroFusion360", None))
    # retranslateUi
