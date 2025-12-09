from PyQt5 import QtCore, QtWidgets


class Ui_BlockNumberDlg(object):
    def setupUi(self, BlockNumberDlg):
        BlockNumberDlg.setObjectName("BlockNumberDlg")
        BlockNumberDlg.resize(200, 150)
        BlockNumberDlg.setMinimumSize(QtCore.QSize(200, 150))
        self.verticalLayout = QtWidgets.QVBoxLayout(BlockNumberDlg)
        self.verticalLayout.setObjectName("verticalLayout")
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        self.labelStart = QtWidgets.QLabel(BlockNumberDlg)
        self.labelStart.setObjectName("labelStart")
        self.gridLayout.addWidget(self.labelStart, 0, 0, 1, 1)
        self.labelInterval = QtWidgets.QLabel(BlockNumberDlg)
        self.labelInterval.setObjectName("labelInterval")
        self.gridLayout.addWidget(self.labelInterval, 1, 0, 1, 1)
        self.labelSpacing = QtWidgets.QLabel(BlockNumberDlg)
        self.labelSpacing.setObjectName("labelSpacing")
        self.gridLayout.addWidget(self.labelSpacing, 2, 0, 1, 1)
        self.spacingCmbBox = QtWidgets.QComboBox(BlockNumberDlg)
        self.spacingCmbBox.setObjectName("spacingCmbBox")
        self.spacingCmbBox.addItem("")
        self.spacingCmbBox.addItem("")
        self.gridLayout.addWidget(self.spacingCmbBox, 2, 1, 1, 1)
        self.startSpinBox = QtWidgets.QSpinBox(BlockNumberDlg)
        self.startSpinBox.setMinimum(1)
        self.startSpinBox.setMaximum(99999)
        self.startSpinBox.setObjectName("startSpinBox")
        self.gridLayout.addWidget(self.startSpinBox, 0, 1, 1, 1)
        self.intervSpinBox = QtWidgets.QSpinBox(BlockNumberDlg)
        self.intervSpinBox.setMinimum(1)
        self.intervSpinBox.setMaximum(99999)
        self.intervSpinBox.setObjectName("intervSpinBox")
        self.gridLayout.addWidget(self.intervSpinBox, 1, 1, 1, 1)
        self.verticalLayout.addLayout(self.gridLayout)
        self.buttonBox = QtWidgets.QDialogButtonBox(BlockNumberDlg)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(BlockNumberDlg)
        self.buttonBox.accepted.connect(BlockNumberDlg.accept) # type: ignore
        self.buttonBox.rejected.connect(BlockNumberDlg.reject) # type: ignore
        QtCore.QMetaObject.connectSlotsByName(BlockNumberDlg)

    def retranslateUi(self, BlockNumberDlg):
        _translate = QtCore.QCoreApplication.translate
        BlockNumberDlg.setWindowTitle(_translate("BlockNumberDlg", "Block Numbers"))
        self.labelStart.setText(_translate("BlockNumberDlg", "Start"))
        self.labelInterval.setText(_translate("BlockNumberDlg", "Interval"))
        self.labelSpacing.setText(_translate("BlockNumberDlg", "Spacing"))
        self.spacingCmbBox.setItemText(0, _translate("BlockNumberDlg", "No"))
        self.spacingCmbBox.setItemText(1, _translate("BlockNumberDlg", "Yes"))
