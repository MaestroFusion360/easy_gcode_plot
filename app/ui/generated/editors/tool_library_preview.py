# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tool_library_preview.ui'
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
from PyQt6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
    QScrollArea, QSizePolicy, QSpacerItem, QToolButton,
    QVBoxLayout, QWidget)

class Ui_ToolLibraryPreviewPane(object):
    def setupUi(self, ToolLibraryPreviewPane):
        if not ToolLibraryPreviewPane.objectName():
            ToolLibraryPreviewPane.setObjectName(u"ToolLibraryPreviewPane")
        self.verticalLayout = QVBoxLayout(ToolLibraryPreviewPane)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.scrollArea = QScrollArea(ToolLibraryPreviewPane)
        self.scrollArea.setObjectName(u"scrollArea")
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setWidgetResizable(False)
        self.scrollArea.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout.addWidget(self.scrollArea)

        self.controlsLayout = QHBoxLayout()
        self.controlsLayout.setObjectName(u"controlsLayout")
        self.controlsLayout.setContentsMargins(0, 0, 0, 0)
        self.tracePointLabel = QLabel(ToolLibraryPreviewPane)
        self.tracePointLabel.setObjectName(u"tracePointLabel")

        self.controlsLayout.addWidget(self.tracePointLabel)

        self.controlsSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.controlsLayout.addItem(self.controlsSpacer)

        self.zoomOutButton = QToolButton(ToolLibraryPreviewPane)
        self.zoomOutButton.setObjectName(u"zoomOutButton")

        self.controlsLayout.addWidget(self.zoomOutButton)

        self.fitButton = QToolButton(ToolLibraryPreviewPane)
        self.fitButton.setObjectName(u"fitButton")

        self.controlsLayout.addWidget(self.fitButton)

        self.zoomInButton = QToolButton(ToolLibraryPreviewPane)
        self.zoomInButton.setObjectName(u"zoomInButton")

        self.controlsLayout.addWidget(self.zoomInButton)


        self.verticalLayout.addLayout(self.controlsLayout)


        self.retranslateUi(ToolLibraryPreviewPane)

        QMetaObject.connectSlotsByName(ToolLibraryPreviewPane)
    # setupUi

    def retranslateUi(self, ToolLibraryPreviewPane):
        self.tracePointLabel.setText(QCoreApplication.translate("ToolLibraryPreviewPane", u"Red cross: trace point", None))
#if QT_CONFIG(tooltip)
        self.zoomOutButton.setToolTip(QCoreApplication.translate("ToolLibraryPreviewPane", u"Zoom out", None))
#endif // QT_CONFIG(tooltip)
        self.zoomOutButton.setText(QCoreApplication.translate("ToolLibraryPreviewPane", u"\u2212", None))
#if QT_CONFIG(tooltip)
        self.fitButton.setToolTip(QCoreApplication.translate("ToolLibraryPreviewPane", u"Fit preview", None))
#endif // QT_CONFIG(tooltip)
        self.fitButton.setText(QCoreApplication.translate("ToolLibraryPreviewPane", u"Fit", None))
#if QT_CONFIG(tooltip)
        self.zoomInButton.setToolTip(QCoreApplication.translate("ToolLibraryPreviewPane", u"Zoom in", None))
#endif // QT_CONFIG(tooltip)
        self.zoomInButton.setText(QCoreApplication.translate("ToolLibraryPreviewPane", u"+", None))
        pass
    # retranslateUi
