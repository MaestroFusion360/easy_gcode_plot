from PyQt6 import QtCore, QtWidgets


class Ui_WcsDlg(object):
    def setupUi(self, WcsDlg):
        WcsDlg.setObjectName("WcsDlg")
        WcsDlg.resize(520, 430)
        WcsDlg.setMinimumSize(QtCore.QSize(520, 430))
        self.verticalLayout = QtWidgets.QVBoxLayout(WcsDlg)
        self.verticalLayout.setObjectName("verticalLayout")
        self.titleLabel = QtWidgets.QLabel(WcsDlg)
        self.titleLabel.setObjectName("titleLabel")
        self.verticalLayout.addWidget(self.titleLabel)
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        self.nameHeader = QtWidgets.QLabel(WcsDlg)
        self.nameHeader.setObjectName("nameHeader")
        self.gridLayout.addWidget(self.nameHeader, 0, 0, 1, 1)
        self.xHeader = QtWidgets.QLabel(WcsDlg)
        self.xHeader.setObjectName("xHeader")
        self.gridLayout.addWidget(self.xHeader, 0, 1, 1, 1)
        self.yHeader = QtWidgets.QLabel(WcsDlg)
        self.yHeader.setObjectName("yHeader")
        self.gridLayout.addWidget(self.yHeader, 0, 2, 1, 1)
        self.zHeader = QtWidgets.QLabel(WcsDlg)
        self.zHeader.setObjectName("zHeader")
        self.gridLayout.addWidget(self.zHeader, 0, 3, 1, 1)

        self._offsetSpinBoxes = {}
        labels = ("G54", "G55", "G56", "G57", "G58", "G59", "Home (G28)")
        names = ("g54", "g55", "g56", "g57", "g58", "g59", "home")
        for row, (label_text, name) in enumerate(zip(labels, names), start=1):
            label = QtWidgets.QLabel(WcsDlg)
            label.setObjectName(f"{name}Label")
            setattr(self, f"{name}Label", label)
            self.gridLayout.addWidget(label, row, 0, 1, 1)

            axis_spins = []
            for column, axis in enumerate(("X", "Y", "Z"), start=1):
                spin = QtWidgets.QDoubleSpinBox(WcsDlg)
                spin.setDecimals(3)
                spin.setMinimum(-999999.999)
                spin.setMaximum(999999.999)
                spin.setSingleStep(0.001)
                spin.setObjectName(f"{name}{axis}")
                setattr(self, f"{name}{axis}", spin)
                self.gridLayout.addWidget(spin, row, column, 1, 1)
                axis_spins.append(spin)

            self._offsetSpinBoxes[name] = tuple(axis_spins)

        self.verticalLayout.addLayout(self.gridLayout)
        self.homeConfiguredCheck = QtWidgets.QCheckBox(WcsDlg)
        self.homeConfiguredCheck.setObjectName("homeConfiguredCheck")
        self.verticalLayout.addWidget(self.homeConfiguredCheck)
        spacerItem = QtWidgets.QSpacerItem(
            20, 40, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding
        )
        self.verticalLayout.addItem(spacerItem)
        self.buttonBox = QtWidgets.QDialogButtonBox(WcsDlg)
        self.buttonBox.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel | QtWidgets.QDialogButtonBox.StandardButton.Ok
        )
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(WcsDlg)
        self.buttonBox.accepted.connect(WcsDlg.accept)  # type: ignore
        self.buttonBox.rejected.connect(WcsDlg.reject)  # type: ignore
        QtCore.QMetaObject.connectSlotsByName(WcsDlg)

    def retranslateUi(self, WcsDlg):
        _translate = QtCore.QCoreApplication.translate
        WcsDlg.setWindowTitle(_translate("WcsDlg", "WCS"))
        self.titleLabel.setText(_translate("WcsDlg", "Coordinate Offsets"))
        self.nameHeader.setText(_translate("WcsDlg", "Name"))
        self.xHeader.setText(_translate("WcsDlg", "X"))
        self.yHeader.setText(_translate("WcsDlg", "Y"))
        self.zHeader.setText(_translate("WcsDlg", "Z"))
        self.g54Label.setText(_translate("WcsDlg", "G54"))
        self.g55Label.setText(_translate("WcsDlg", "G55"))
        self.g56Label.setText(_translate("WcsDlg", "G56"))
        self.g57Label.setText(_translate("WcsDlg", "G57"))
        self.g58Label.setText(_translate("WcsDlg", "G58"))
        self.g59Label.setText(_translate("WcsDlg", "G59"))
        self.homeLabel.setText(_translate("WcsDlg", "Home (G28)"))
        self.homeConfiguredCheck.setText(
            _translate("WcsDlg", "Use configured G28 home for machine-space rapid checks")
        )
