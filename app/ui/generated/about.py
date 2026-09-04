from PyQt6 import QtCore, QtGui, QtWidgets


class Ui_AboutDlg(object):
    def setupUi(self, AboutDlg):
        AboutDlg.setObjectName("AboutDlg")
        AboutDlg.resize(520, 310)
        AboutDlg.setMinimumSize(QtCore.QSize(520, 310))
        AboutDlg.setMaximumSize(QtCore.QSize(520, 310))
        self.verticalLayout = QtWidgets.QVBoxLayout(AboutDlg)
        self.verticalLayout.setContentsMargins(18, 18, 18, 12)
        self.verticalLayout.setSpacing(10)
        self.verticalLayout.setObjectName("verticalLayout")
        self.headerLayout = QtWidgets.QHBoxLayout()
        self.headerLayout.setSpacing(16)
        self.headerLayout.setObjectName("headerLayout")
        self.logoLabel = QtWidgets.QLabel(parent=AboutDlg)
        self.logoLabel.setMinimumSize(QtCore.QSize(72, 72))
        self.logoLabel.setMaximumSize(QtCore.QSize(72, 72))
        self.logoLabel.setPixmap(QtGui.QPixmap(":/resource/icons/logo.png"))
        self.logoLabel.setScaledContents(True)
        self.logoLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.logoLabel.setObjectName("logoLabel")
        self.headerLayout.addWidget(self.logoLabel)
        self.titleLayout = QtWidgets.QVBoxLayout()
        self.titleLayout.setObjectName("titleLayout")
        self.titleLabel = QtWidgets.QLabel(parent=AboutDlg)
        font = QtGui.QFont()
        font.setPointSize(16)
        font.setBold(True)
        self.titleLabel.setFont(font)
        self.titleLabel.setObjectName("titleLabel")
        self.titleLayout.addWidget(self.titleLabel)
        self.versionLabel = QtWidgets.QLabel(parent=AboutDlg)
        self.versionLabel.setObjectName("versionLabel")
        self.titleLayout.addWidget(self.versionLabel)
        self.headerLayout.addLayout(self.titleLayout)
        self.verticalLayout.addLayout(self.headerLayout)
        self.line = QtWidgets.QFrame(parent=AboutDlg)
        self.line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.line.setObjectName("line")
        self.verticalLayout.addWidget(self.line)
        self.descriptionLabel = QtWidgets.QLabel(parent=AboutDlg)
        self.descriptionLabel.setWordWrap(True)
        self.descriptionLabel.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.descriptionLabel.setObjectName("descriptionLabel")
        self.verticalLayout.addWidget(self.descriptionLabel)
        self.licenseLabel = QtWidgets.QLabel(parent=AboutDlg)
        self.licenseLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.licenseLabel.setObjectName("licenseLabel")
        self.verticalLayout.addWidget(self.licenseLabel)
        self.dateLabel = QtWidgets.QLabel(parent=AboutDlg)
        self.dateLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.dateLabel.setObjectName("dateLabel")
        self.verticalLayout.addWidget(self.dateLabel)
        spacerItem = QtWidgets.QSpacerItem(
            20,
            10,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.verticalLayout.addItem(spacerItem)
        self.buttonBox = QtWidgets.QDialogButtonBox(parent=AboutDlg)
        self.buttonBox.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.buttonBox.setCenterButtons(True)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(AboutDlg)
        self.buttonBox.accepted.connect(AboutDlg.accept)  # type: ignore
        QtCore.QMetaObject.connectSlotsByName(AboutDlg)

    def retranslateUi(self, AboutDlg):
        _translate = QtCore.QCoreApplication.translate
        AboutDlg.setWindowTitle(_translate("AboutDlg", "About Easy G-code Plot"))
        self.titleLabel.setText(_translate("AboutDlg", "Easy G-code Plot"))
        self.versionLabel.setText(_translate("AboutDlg", "Version"))
        self.descriptionLabel.setText(
            _translate(
                "AboutDlg",
                "Easy G-code Plot is a FANUC/ISO G-code viewer, editor, analyzer and verifier "
                "for turning and milling. Version 1.2.0 introduces a shared native Python CNC "
                "kernel, authoritative logical Motion Trace, Macro B/control flow, turning "
                "cycles, native XYZ milling, trajectory playback/picking and source-aware "
                "expanded program export for both machine modes.",
            )
        )
        self.licenseLabel.setText(
            _translate("AboutDlg", "Free and open-source software distributed under the MIT License.")
        )
        self.dateLabel.setText(_translate("AboutDlg", "© 2025–2026 MaestroFusion360"))
