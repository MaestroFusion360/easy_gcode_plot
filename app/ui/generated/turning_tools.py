from PyQt6 import QtCore, QtWidgets


class Ui_TurningToolsDlg(object):
    def setupUi(self, TurningToolsDlg):
        TurningToolsDlg.setObjectName("TurningToolsDlg")
        TurningToolsDlg.resize(760, 520)
        TurningToolsDlg.setMinimumSize(QtCore.QSize(640, 420))
        self.verticalLayout = QtWidgets.QVBoxLayout(TurningToolsDlg)
        self.verticalLayout.setObjectName("verticalLayout")
        self.titleLabel = QtWidgets.QLabel(TurningToolsDlg)
        self.titleLabel.setObjectName("titleLabel")
        self.verticalLayout.addWidget(self.titleLabel)
        self.helpLabel = QtWidgets.QLabel(TurningToolsDlg)
        self.helpLabel.setWordWrap(True)
        self.helpLabel.setObjectName("helpLabel")
        self.verticalLayout.addWidget(self.helpLabel)
        self.toolTable = QtWidgets.QTableWidget(TurningToolsDlg)
        self.toolTable.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.toolTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.toolTable.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.toolTable.setColumnCount(5)
        self.toolTable.setRowCount(0)
        self.toolTable.setObjectName("toolTable")
        for column in range(5):
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
        self.addButton = QtWidgets.QPushButton(TurningToolsDlg)
        self.addButton.setObjectName("addButton")
        self.toolButtonsLayout.addWidget(self.addButton)
        self.editButton = QtWidgets.QPushButton(TurningToolsDlg)
        self.editButton.setObjectName("editButton")
        self.toolButtonsLayout.addWidget(self.editButton)
        self.removeButton = QtWidgets.QPushButton(TurningToolsDlg)
        self.removeButton.setObjectName("removeButton")
        self.toolButtonsLayout.addWidget(self.removeButton)
        self.verticalLayout.addLayout(self.toolButtonsLayout)
        self.buttonBox = QtWidgets.QDialogButtonBox(TurningToolsDlg)
        self.buttonBox.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel | QtWidgets.QDialogButtonBox.StandardButton.Ok
        )
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(TurningToolsDlg)
        self.buttonBox.accepted.connect(TurningToolsDlg.accept)  # type: ignore
        self.buttonBox.rejected.connect(TurningToolsDlg.reject)  # type: ignore
        QtCore.QMetaObject.connectSlotsByName(TurningToolsDlg)

    def retranslateUi(self, TurningToolsDlg):
        _translate = QtCore.QCoreApplication.translate
        TurningToolsDlg.setWindowTitle(_translate("TurningToolsDlg", "Turning Tools"))
        self.titleLabel.setText(_translate("TurningToolsDlg", "Tool Nose Compensation"))
        self.helpLabel.setText(
            _translate(
                "TurningToolsDlg",
                "Turning tools require a nose radius and one of the nine FANUC tip orientations.",
            )
        )
        headers = (
            "Tip orientation",
            "T code",
            "Type",
            "Nose radius, mm",
            "Description",
        )
        for column, text in enumerate(headers):
            self.toolTable.horizontalHeaderItem(column).setText(_translate("TurningToolsDlg", text))
        self.addButton.setText(_translate("TurningToolsDlg", "Add..."))
        self.editButton.setText(_translate("TurningToolsDlg", "Edit..."))
        self.removeButton.setText(_translate("TurningToolsDlg", "Remove"))
