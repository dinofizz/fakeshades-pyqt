import signal

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QLineEdit, QComboBox
import random
import serial
from serial import SerialException


class SerialWorker(QThread):
    update_matrix_signal = pyqtSignal()
    header = bytes([0xba, 0x5e, 0xba, 0x11])

    def __init__(self, serial_connection, matrix, parent=None):
        QThread.__init__(self, parent)

        self.serial_connection = serial_connection
        self.exiting = False
        self.matrix = matrix

    def __del__(self):
        self.exiting = True
        self.wait()

    def run(self):
        header_position = 0
        received_header = False
        received_count = False
        byte_count = 0
        num_columns = 0
        column = 0
        row = 0
        max_bytes = 0

        while True:
            byte = self.serial_connection.read()

            if received_header is False:
                for i in range(len(self.header)):
                    if bytes([self.header[header_position]]) == byte:
                        header_position += 1
                        if header_position == 4:
                            received_header = True
                            print("RECEIVED HEADER")
                            header_position = 0
                        else:
                            byte = self.serial_connection.read()
                    else:
                        received_header = False
                        header_position = 0
                        break
            elif received_count is False:
                num_columns = byte[0]
                byte = self.serial_connection.read()
                num_rows = byte[0]
                max_bytes = int(num_columns * num_rows / 2)
                received_count = True
                print("Num columns: {0}\nNum rows: {1}\nNum LEDs: {2}\nMax bytes to receive: {3}".format(
                    num_columns, num_rows, (num_columns * num_rows), max_bytes))
            else:
                if column < num_columns:
                    if row > 15:
                        row = 0
                        column += 1

                    brightness_first = byte[0] >> 4
                    brightness_second = byte[0] & 0x0F

                    self.matrix[column][row] = brightness_first
                    print(self.matrix[column][row])

                    row += 1

                    if row > 15:
                        row = 0
                        column += 1

                    self.matrix[column][row] = brightness_second
                    print(self.matrix[column][row])

                    row += 1

                    byte_count += 1

                    if byte_count is max_bytes:
                        column = 0
                        row = 0
                        max_bytes = 0
                        byte_count = 0
                        received_count = False
                        received_header = False
                        self.update_matrix_signal.emit()
                        print("\nEND FRAME\n")


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.resize(970, 360)

        self.thread = None

        self.serial_connection = None
        self.connected = False

        self.matrix = [[0 for i in range(16)] for i in range(48)]

        self.connect_button = QPushButton('Connect')
        self.connect_button.clicked.connect(self.connect_button_clicked)
        self.status_label = QLabel('Disconnected')

        self.serial_port = QLineEdit()
        self.serial_port.setPlaceholderText("Enter serial port to connect to, i.e. /dev/ttyS0")

        self.baud_combo = QComboBox(self)
        self.baud_combo.addItem("9600")     #0
        self.baud_combo.addItem("19200")    #1
        self.baud_combo.addItem("38400")    #2
        self.baud_combo.addItem("57600")    #3
        self.baud_combo.addItem("115200")   #4
        self.baud_combo.setCurrentIndex(3)

        self.statusBar().addWidget(self.serial_port)
        self.statusBar().addWidget(self.baud_combo)
        self.statusBar().addWidget(self.connect_button)
        self.statusBar().addWidget(self.status_label)

    def connect_button_clicked(self):
        self.status_label.setText('Connecting')

        if self.connected:
            self.serial_connection.close()
            self.thread.exiting = True
            self.thread = None
            self.set_serial_status(False)
        else:
            try:
                self.serial_connection = serial.Serial(
                    self.serial_port.text(), baudrate=int(self.baud_combo.currentText()), rtscts=True, dsrdtr=True)
                if self.serial_connection.is_open:
                    self.set_serial_status(True)
                    self.thread = SerialWorker(self.serial_connection, self.matrix)
                    self.thread.update_matrix_signal.connect(self.update_matrix)
                    self.thread.start()
            except SerialException as ex:
                self.status_label.setText(ex.strerror)

    def update_matrix(self):
        self.update()

    def set_serial_status(self, connected):
        if connected:
            self.connected = True
            self.status_label.setText('Connected')
            self.connect_button.setText('Disconnect')
            self.serial_port.setEnabled(False)
        else:
            self.connected = False
            self.status_label.setText('Disconnected')
            self.connect_button.setText('Connect')
            self.serial_port.setEnabled(True)

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)
        self.draw_points(qp)
        qp.end()

    def draw_points(self, qp):
        for column, row in ((column, row) for column in range(48) for row in range(16)):
            qp.setRenderHint(QPainter.Antialiasing, True)

            # QColor accepts (R, G, B, alpha) values.
            # We multiply the 16bit "brightness" value obtained from the serial port by 17
            # to give us a value mapped to a max of 255:
            # 16 bit brightness values: 0 - 15
            # 15 * 17 = 255
            qp.setBrush(QColor(0x00, 0x00, 0x00, (self.matrix[column][row] * 17)))
            qp.drawEllipse(10 + (column * 20), 10 + (row * 20), 10, 10)


def main():
    import sys

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    random.seed()

    app = QApplication(sys.argv)

    # This gets rid of the border around the items in the status bar.
    # But I now see an error in the console "Could not parse application stylesheet"
    app.setStyleSheet("QStatusBar::item { border: 0px solid black }; ")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
