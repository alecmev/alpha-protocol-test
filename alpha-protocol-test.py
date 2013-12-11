import collections
import struct
import time
from tkinter import *
from tkinter.ttk import *

import serial
from serial.tools.list_ports import comports

class MainFrame(Frame):
    ACK = 0x00
    NAK = 0x01
    SOP = 0xE1
    EOP = 0xE2
    ESC = 0xFF
    POS = 0x1E
    POE = 0x1D
    speeds = [9600, 19200, 38400, 57600, 115200]

    initialized = False
    com = None
    row = 0
    newSpeed = None
    newSlave = None

    def addWidget(self, widget):
        widget.grid(column=1, row=self.row, sticky=(W, E), pady=3)
        self.row += 1

    def addPair(self, widget, text):
        label = Label(self, text=text)
        label.grid(column=0, row=self.row, sticky=(N, S, E), padx=6, pady=3)
        self.addWidget(widget)

    def addEntry(self, text, validator):
        var = StringVar()
        entry = Entry(
            self, textvariable=var, validate='all',
            validatecommand=(self.register(validator), '%P')
        )
        self.addPair(entry, text)
        entry.bind('<Control-Key-a>', self.selectAll)
        entry.bind('<Control-Key-A>', self.selectAll)
        return var

    def addCheckbutton(self, text):
        var = IntVar()
        config = Checkbutton(self, variable=var, takefocus=False)
        self.addPair(config, text)
        return var

    def addButton(self, text, command):
        button = Button(self, text=text, command=command)
        self.addWidget(button)
        return button

    def addSpacer(self):
        spacer = Frame(self, height=12)
        spacer.grid(column=0, row=self.row, columnspan=2, sticky=(W, E), pady=3)
        self.row += 1

    def updatePorts(self):
        self.after(100, self.updatePorts)
        self.comPortPrev = self.comPort.get()
        ports = []
        for port in comports():
            ports.append(port[0])

        self.comPort['values'] = ports
        if self.comPortPrev in ports:
            self.comPort.current(ports.index(self.comPortPrev))
        elif len(ports) > 0:
            self.comPort.current(0)

    def selectAll(self, event):
        event.widget.selection_range(0, END)
        return 'break'

    def validateIntRange(self, text, a, b):
        try:
            num = int(text.strip())
            return num >= a and num <= b
        except:
            return False

    def validateComSlave(self, text):
        self.comSlaveValid = self.validateIntRange(text, 0, 65535)
        return True

    def validateSlave(self, text):
        self.slaveValid = self.validateIntRange(text, 0, 65535)
        return True

    def validateTon(self, text):
        self.tonValid = self.validateIntRange(text, 1, 255)
        return True

    def validateToff(self, text):
        self.toffValid = self.validateIntRange(text, 1, 255)
        return True

    def validateSequence(self, text):
        try:
            self.sequenceBytes = bytes.fromhex(text)
            self.sequenceValid = True
        except ValueError:
            self.sequenceValid = False

        return True

    def verifyCom(self):
        return self.comPort.get() and self.comSlaveValid

    def comPortChanged(self, name, index, mode):
        if not self.comPortPrev == self.comPortVar.get():
            self.connect()

    def comSpeedChanged(self, name, index, mode):
        self.connect()

    def connect(self):
        if not self.initialized:
            return

        self.disconnect()
        port = self.comPortVar.get()
        if not port:
            return

        self.com = serial.Serial(
            '\\\\.\\' + port, self.comSpeedVar.get(), timeout=0, writeTimeout=0
        )
        self.after(100, self.listen)

    def disconnect(self):
        if not self.com == None:
            self.com.close()
            self.com = None

    def crc(self, data):
        res = 0
        for byte in data:
            tmp = (res ^ byte) & 0o17
            res = (res >> 4) ^ (tmp * 0o10201)
            tmp = (res ^ (byte >> 4)) & 0o17
            res = (res >> 4) ^ (tmp * 0o10201)

        return res

    def checkNew(self):
        new = False
        if not None == self.newSpeed:
            self.comSpeed.current(self.newSpeed)
            self.newSpeed = None
            new = True

        if not None == self.newSlave:
            self.comSlaveVar.set(self.newSlave)
            self.newSlave = None

        return new

    def listenRes(self, text, slave=None):
        if not self.checkNew():
            self.connect()

        self.updateStatus(text)
        if not None == slave:
            self.updateLastSlave(slave)

    def listen(self):
        if self.com == None:
            return

        data = self.readByte()
        if data == None:
            if not self.checkNew():
                self.after(100, self.listen)
            return
        if not data == self.SOP:
            return self.listenRes('FIRST BYTE WAS NOT SOP')

        lengthBytes = self.readTwo()
        if lengthBytes == None:
            return self.listenRes('FAILED TO READ PACKET LENGTH')
        length = struct.unpack_from('<H', lengthBytes)[0]

        slaveBytes = self.readTwo()
        if slaveBytes == None:
            return self.listenRes('FAILED TO READ SLAVE ID')
        slave = struct.unpack_from('<H', slaveBytes)[0]

        ack = self.readOne()
        if ack == None:
            return self.listenRes('FAILED TO READ ACK', slave)

        status = self.readOne()
        if status == None:
            return self.listenRes('FAILED TO READ KEYBOARD STATE', slave)

        data = self.readTwo()
        if data == None:
            return self.listenRes('FAILED TO READ CHECKSUM', slave)
        crc = struct.unpack_from('<H', data)[0]

        data = self.readByte()
        if data == None or not data == self.EOP:
            return self.listenRes('LAST BYTE WAS NOT EOP', slave)

        if self.crc(lengthBytes + slaveBytes + bytes([ack, status])) == crc:
            if self.ACK == ack:
                self.updateStatus()
            else:
                self.updateStatus('NAK')

            self.updateLastSlave(slave, True)
            i = 0
            while i < 8:
                self.keyboardBVar[7 - i].set(self.keyboardNVar[7 - i].get())
                self.keyboardNVar[7 - i].set((status >> i) & 0x01)
                i += 1
        else:
            self.updateStatus('INVALID CHECKSUM')
            self.updateLastSlave(slave)

        if not self.checkNew():
            self.after(100, self.listen)

    def readTwo(self):
        one = self.readOne()
        two = self.readOne()
        if one == None or two == None:
            return None

        return bytes([one, two])

    def readOne(self):
        data = self.readByte()
        if None == data:
            return None

        if self.ESC == data:
            data = self.readByte()
            if None == data:
                return None

            if self.ESC == data:
                return self.ESC
            elif self.POS == data:
                return self.SOP
            elif self.POE == data:
                return self.EOP
            else:
                return None

        return data

    def readByte(self):
        data = self.com.read()
        if not len(data):
            time.sleep(0.01)
            data = self.com.read()
            if not len(data):
                return None

        return data[0]

    def updateStatus(self, text='READY'):
        self.statusVar.set('[%.1f] %s' % (time.clock(), text))
        self.status['foreground'] = '#0C0' if 'READY' == text else '#C00'

    def updateLastSlave(self, slave, sure=False):
        self.lastSlaveVar.set(slave if sure else '%d?' % slave)

    def escape(self, data):
        if not isinstance(data, collections.Iterable):
            data = [data]

        res = []
        for byte in data:
            if self.ESC == byte:
                res.extend([self.ESC, self.ESC])
            elif self.SOP == byte:
                res.extend([self.ESC, self.POS])
            elif self.EOP == byte:
                res.extend([self.ESC, self.POE])
            else:
                res.extend([byte])

        return bytes(res)

    def write(self, command, payload):
        if self.com == None:
            return self.updateStatus('PORT NOT SELECTED')

        if not self.comSlaveValid:
            return self.updateStatus('INVALID COM SLAVE ID')

        if not isinstance(payload, collections.Iterable):
            payload = [payload]

        payload = [command] + payload
        data = (
            struct.pack('<H', len(payload) + 6) +
            struct.pack('<H', int(self.comSlaveVar.get())) +
            bytes(payload)
        )
        data = (
            bytes([self.SOP]) +
            self.escape(data) +
            self.escape(struct.pack('<H', self.crc(data))) +
            bytes([self.EOP])
        )
        try:
            self.com.write(data)
        except:
            try:
                self.com.write(data)
            except:
                self.connect()
                self.updateStatus('FAILED TO WRITE')
                return False

        return True

    def speedButton(self):
        speed = self.speed.current()
        if self.write(3, speed):
            self.newSpeed = speed

    def slaveButton(self):
        if not self.slaveValid:
            return self.updateStatus('INVALID SLAVE ID')

        slave = self.slaveVar.get()
        if self.write(2, list(struct.pack('<H', int(slave)))):
            self.newSlave = slave

    def modeButton(self):
        self.write(0, self.modeVar.get())

    def configButton(self):
        self.write(4, 7
            (self.configVar[0].get() << 7) +
            (self.configVar[1].get() << 6) +
            (self.configVar[2].get() << 5) +
            (self.configVar[3].get() << 4)
        )

    def sequenceButton(self):
        if not self.tonValid:
            return self.updateStatus('INVALID TON')
        if not self.toffValid:
            return self.updateStatus('INVALID TOFF')
        if not self.sequenceValid:
            return self.updateStatus('INVALID SEQUENCE')

        self.write(5, 
            [
                (self.configVar[0].get() << 7) +
                (self.configVar[1].get() << 6) +
                (self.configVar[2].get() << 5) +
                (self.configVar[3].get() << 4),
                int(self.tonVar.get()),
                int(self.toffVar.get()),
                len(self.sequenceBytes)
            ] +
            list(self.sequenceBytes)
        )

    def updateButton(self):
        self.write(1, [])

    def __init__(self, master):
        Frame.__init__(self, master)
        self.grid(padx=12, pady=9)
        self.columnconfigure(1, minsize=256)

        self.comPortVar = StringVar()
        self.comPortVar.trace('w', self.comPortChanged)
        self.comPort = Combobox(
            self, state='readonly', textvariable=self.comPortVar
        )
        self.addPair(self.comPort, 'Com port')
        self.updatePorts()

        self.comSpeedVar = StringVar()
        self.comSpeedVar.trace('w', self.comSpeedChanged)
        self.comSpeed = Combobox(
            self, state='readonly', values=self.speeds,
            textvariable=self.comSpeedVar
        )
        self.addPair(self.comSpeed, 'Com speed')
        self.comSpeed.current(len(self.speeds) - 1)

        self.comSlaveVar = self.addEntry('Com slave ID', self.validateComSlave)
        self.comSlaveVar.set('0')
        self.comSlaveValid = True

        self.addSpacer()

        self.speed = Combobox(self, state='readonly', values=self.speeds)
        self.addPair(self.speed, 'Speed')
        self.speed.current(len(self.speeds) - 1)

        self.addButton('Set speed', self.speedButton)
        self.addSpacer()

        self.slaveVar = self.addEntry('Slave ID', self.validateSlave)
        self.slaveVar.set('0')
        self.slaveValid = True

        self.addButton('Set slave ID', self.slaveButton)
        self.addSpacer()

        self.modeVar = self.addCheckbutton('Mode one')

        self.addButton('Set mode', self.modeButton)
        self.addSpacer()

        self.configVar = []
        self.configVar.append(self.addCheckbutton('Disable beeper'))
        self.configVar.append(self.addCheckbutton('Disable keyboard'))
        self.configVar.append(self.addCheckbutton('Enable relay'))
        self.configVar.append(self.addCheckbutton('Key activation'))

        self.addButton('Set config', self.configButton)
        self.addSpacer()

        self.tonVar = self.addEntry('Press time', self.validateTon)
        self.tonVar.set('20')
        self.tonValid = True
        self.toffVar = self.addEntry('Pause', self.validateToff)
        self.toffVar.set('20')
        self.toffValid = True
        self.sequenceVar = self.addEntry('Sequence', self.validateSequence)
        self.sequenceVar.set('00')
        self.validateSequence(self.sequenceVar.get())

        self.addButton('Execute sequence', self.sequenceButton)
        self.addSpacer()

        self.statusVar = StringVar()
        self.status = Label(self, textvariable=self.statusVar)
        self.addPair(self.status, 'Status')
        self.updateStatus()

        self.lastSlaveVar = StringVar()
        lastSlave = Label(self, textvariable=self.lastSlaveVar)
        self.addPair(lastSlave, 'Last slave ID')
        self.lastSlaveVar.set('')

        keyboardBFrame = Frame(self)
        self.addPair(keyboardBFrame, 'Keyboard state before')
        self.keyboardBVar = []
        keyboardB = []
        i = 0
        while i < 8:
            self.keyboardBVar.append(IntVar())
            keyboardB.append(Radiobutton(
                keyboardBFrame, variable=self.keyboardBVar[i], state=DISABLED
            ))
            keyboardB[i].grid(column=i, row=0)
            i += 1

        keyboardNFrame = Frame(self)
        self.addPair(keyboardNFrame, 'Keyboard state now')
        self.keyboardNVar = []
        keyboardN = []
        i = 0
        while i < 8:
            self.keyboardNVar.append(IntVar())
            keyboardN.append(Radiobutton(
                keyboardNFrame, variable=self.keyboardNVar[i], state=DISABLED
            ))
            keyboardN[i].grid(column=i, row=0)
            i += 1

        self.addButton('Force update', self.updateButton)

        self.initialized = True
        self.connect()

if __name__ == "__main__":
    window = Tk()
    window.title('Alpha Protocol Test')
    window.resizable(0, 0)
    frame = MainFrame(window)
    window.mainloop()
