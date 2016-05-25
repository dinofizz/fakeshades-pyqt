import serial

# Edit with serial port to send on
ser = serial.Serial('/dev/pts/7', 57600, rtscts=True, dsrdtr=True)

ser.write(bytes([0xba, 0x5e, 0xba, 0x11]))
ser.write(bytes([2]))
ser.write(bytes([16]))


for i in range(16):
    if (i % 2) == 0:
        byte = i
    else:
        byte = (byte << 4)
        byte = byte | i
        print(byte)
        ser.write(bytes([byte]))

for i in range(16):
    if (i % 2) == 0:
        byte = i
    else:
        byte = (byte << 4)
        byte = byte | i
        print(byte)
        ser.write(bytes([byte]))