import signal

import serial
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QLineEdit, QComboBox
from serial import SerialException


class SerialWorker(QThread):
    update_matrix_signal = pyqtSignal(list)
    serial_connected = pyqtSignal()
    serial_error_text = pyqtSignal(str)
    header = bytes([0xba, 0x5e, 0xba, 0x11])

    def __init__(self, port, baudrate, parent=None):
        QThread.__init__(self, parent)

        self.port = port
        self.baudrate = baudrate
        self.serial_connection = None
        self.exiting = False
        self.matrix = None

    def stop(self):
        if self.serial_connection is not None:
            self.serial_connection.close()
        self.exiting = True
        self.wait()

    def run(self):
        header_position = 0
        received_header = False
        received_count = False
        byte_count = 0
        column = 0
        row = 0
        max_bytes = 0

        try:
            self.serial_connection = serial.Serial(self.port, baudrate=self.baudrate, rtscts=True, dsrdtr=True)
            if self.serial_connection.is_open:
                self.serial_connected.emit()
            else:
                self.serial_error_text.emit("Error occurred while opening serial port. Try again.")
                self.stop()
                return
        except SerialException as ex:
            self.serial_error_text.emit(ex.strerror)
            self.stop()
            return

        while True:
            try:
                byte = self.serial_connection.read()
                if received_header is False:
                    for i in range(len(self.header)):
                        if bytes([self.header[header_position]]) == byte:
                            header_position += 1
                            if header_position == len(self.header):
                                received_header = True
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
                    self.matrix = [[0 for i in range(num_rows)] for i in range(num_columns)]
                    received_count = True
                else:
                    brightness_first = byte[0] >> 4
                    brightness_second = byte[0] & 0x0F

                    if row > num_rows - 1:
                        row = 0
                        column += 1

                    actual_row = abs(row - (num_rows - 1))
                    self.matrix[column][actual_row] = brightness_first

                    row += 1

                    if row > num_rows - 1:
                        row = 0
                        column += 1

                    actual_row = abs(row - (num_rows - 1))
                    self.matrix[column][actual_row] = brightness_second

                    row += 1

                    byte_count += 1

                    if byte_count == max_bytes:
                        column = 0
                        row = 0
                        max_bytes = 0
                        byte_count = 0
                        received_count = False
                        received_header = False
                        self.update_matrix_signal.emit(self.matrix)
                        self.matrix = None
            except SerialException:
                print("Error reading Serial Port")
                break


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.resize(970, 360)

        self.thread = None

        self.serial_connection = None
        self.connected = False
        self.matrix = None

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
        self.baud_combo.addItem("230400")   #5
        self.baud_combo.setCurrentIndex(5)

        self.statusBar().addWidget(self.serial_port)
        self.statusBar().addWidget(self.baud_combo)
        self.statusBar().addWidget(self.connect_button)
        self.statusBar().addWidget(self.status_label)

    def connect_button_clicked(self):
        self.status_label.setText('Connecting')

        if self.connected:
            self.thread.stop()
            self.set_serial_status(False)
        else:
            self.thread = SerialWorker(self.serial_port.text(), int(self.baud_combo.currentText()))
            self.thread.update_matrix_signal.connect(self.update_matrix)
            self.thread.serial_error_text.connect(self.connect_error)
            self.thread.serial_connected.connect(self.serial_connected)
            self.thread.start()

    def connect_error(self, error_message):
        self.status_label.setText(error_message)

    def serial_connected(self):
        self.set_serial_status(True)

    def update_matrix(self, matrix):
        self.matrix = matrix
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
        if self.matrix is not None:
            qp = QPainter()
            qp.begin(self)
            self.draw_points(qp)
            qp.end()

    def draw_points(self, qp):
        # TODO: variable size display! Use size of matrix.
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

    # To help with quitting the application.
    # http://stackoverflow.com/questions/4938723/what-is-the-correct-way-to-make-my-pyqt-application-quit-when-killed-from-the-co/6072360#6072360
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)

    # This gets rid of the border around the items in the status bar.
    # But I now see an error in the console "Could not parse application stylesheet"
    app.setStyleSheet("QStatusBar::item { border: 0px solid black }; ")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
