from PyQt6 import QtCore, QtWidgets


class Ui_MillingToolsDlg(object):
    def setupUi(self, MillingToolsDlg):
        MillingToolsDlg.setObjectName("MillingToolsDlg")
        MillingToolsDlg.resize(860, 540)
        MillingToolsDlg.setMinimumSize(QtCore.QSize(700, 440))
        self.verticalLayout = QtWidgets.QVBoxLayout(MillingToolsDlg)
        self.verticalLayout.setObjectName("verticalLayout")
        self.titleLabel = QtWidgets.QLabel(MillingToolsDlg)
        self.titleLabel.setObjectName("titleLabel")
        self.verticalLayout.addWidget(self.titleLabel)
        self.helpLabel = QtWidgets.QLabel(MillingToolsDlg)
        self.helpLabel.setWordWrap(True)
        self.helpLabel.setObjectName("helpLabel")
        self.verticalLayout.addWidget(self.helpLabel)
        self.toolTable = QtWidgets.QTableWidget(MillingToolsDlg)
        self.toolTable.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.toolTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.toolTable.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.toolTable.setColumnCount(6)
        self.toolTable.setRowCount(0)
        self.toolTable.setObjectName("toolTable")
        for column in range(6):
            self.toolTable.setHorizontalHeaderItem(column, QtWidgets.QTableWidgetItem())
        self.toolTable.horizontalHeader().setStretchLastSection(True)
        self.toolTable.verticalHeader().setVisible(False)
        self.verticalLayout.addWidget(self.toolTable)
        self.toolButtonsLayout = QtWidgets.QHBoxLayout()
        self.toolButtonsLayout.setObjectName("toolButtonsLayout")
        spacerItem = QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum
        )
        self.toolButtonsLayout.addItem(spacerItem)
        self.addButton = QtWidgets.QPushButton(MillingToolsDlg)
        self.addButton.setObjectName("addButton")
        self.toolButtonsLayout.addWidget(self.addButton)
        self.editButton = QtWidgets.QPushButton(MillingToolsDlg)
        self.editButton.setObjectName("editButton")
        self.toolButtonsLayout.addWidget(self.editButton)
        self.removeButton = QtWidgets.QPushButton(MillingToolsDlg)
        self.removeButton.setObjectName("removeButton")
        self.toolButtonsLayout.addWidget(self.removeButton)
        self.verticalLayout.addLayout(self.toolButtonsLayout)
        self.buttonBox = QtWidgets.QDialogButtonBox(MillingToolsDlg)
        self.buttonBox.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel | QtWidgets.QDialogButtonBox.StandardButton.Ok
        )
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(MillingToolsDlg)
        self.buttonBox.accepted.connect(MillingToolsDlg.accept)  # type: ignore
        self.buttonBox.rejected.connect(MillingToolsDlg.reject)  # type: ignore
        QtCore.QMetaObject.connectSlotsByName(MillingToolsDlg)

    def retranslateUi(self, MillingToolsDlg):
        _translate = QtCore.QCoreApplication.translate
        MillingToolsDlg.setWindowTitle(_translate("MillingToolsDlg", "Milling Tools"))
        self.titleLabel.setText(_translate("MillingToolsDlg", "Milling Tool Data"))
        self.helpLabel.setText(
            _translate(
                "MillingToolsDlg",
                "Store milling tool geometry for configuration. These values do not change the rendered trace.",
            )
        )
        headers = (
            "Tool",
            "Type",
            "Diameter, mm",
            "Corner radius, mm",
            "Length, mm",
            "Description",
        )
        for column, text in enumerate(headers):
            self.toolTable.horizontalHeaderItem(column).setText(_translate("MillingToolsDlg", text))
        self.addButton.setText(_translate("MillingToolsDlg", "Add..."))
        self.editButton.setText(_translate("MillingToolsDlg", "Edit..."))
        self.removeButton.setText(_translate("MillingToolsDlg", "Remove"))
