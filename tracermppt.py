import serial
import struct
import logging
import socket
from enum import Enum

class Commands(Enum):
    ReadRealtime = 0xA0
    ManualControl = 0xAA

class BufferedSocketReceiver:
    
    def __init__(self, address):
        self.address = address
        self.sock = None
        self.log = logging.getLogger('tracer.socket')
        self.buffer = ""

    def connect(self):
        self.log.info('socket connecting to tcp://%s:%d', self.address[0], self.address[1])
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(self.address)
            self.sock.settimeout(1.0)
        except socket.error as e:
            self.log.exception('socket error while connecting: %s', str(e))
            self.sock = None
            raise

    def disconnect(self):
        if self.sock is not None:
            self.sock.close()
        self.sock = None

    def recv(self, length):
        if length <= len(self.buffer):
            data = self.buffer[:length]
            self.buffer = self.buffer[length:]
            self.__log_recv(data, "from buffer")
            return data
        else:
            data = self.buffer
            self.buffer = ""
            while len(data) < length:
                try:
                    if self.sock is None:
                        self.connect()
                    self.buffer = self.sock.recv(1024)
                    #s = " ".join(map(lambda x: "%02X" % ord(x), list(self.buffer)))
                    #self.log.debug("buff: %s", s)

                    if len(self.buffer) == 0:
                        # recv timed out with no additional data
                        #self.__log_recv(data, "timeout")
                        return data
                    n = min(length - len(data), len(self.buffer))
                    data = data + self.buffer[:n]
                    self.buffer = self.buffer[n:]
                except socket.error as e:
                    self.disconnect()
                    self.log.exception('socket error during reception: %s', str(e))
                    self.__log_recv(data, "exception")
                    return data
            #self.__log_recv(data, "after receive")
            return data

    def send(self, data):
        try:
            if self.sock is None:
                self.connect()
            #s = " ".join(map(lambda x: "%02X" % ord(x), list(data)))
            #self.log.debug("send: %s", s)
            self.sock.sendall(data)
        except socket.error as e:
            self.disconnect()
            self.log.exception('socket error during transmission: %s', str(e))
            raise

    def __log_recv(self, data, comment=""):
        s = " ".join(map(lambda x: "%02X" % ord(x), list(data)))
        if len(comment) > 0:
            comment = " (" + comment + ")"
        #self.log.debug("recv: %s%s", s, comment)

class SerialReceiver:
    
    def __init__(self, port, baud):
        self.serial = serial.Serial(port, baud, timeout=1.0)

    def recv(self, length):
        return self.serial.read(length)

    def send(self, data):
        return self.serial.write(data)


class TracerBase:

    PWL_START="\xAA\x55\xAA\x55\xAA\x55" 
    COMM_SYNC="\xEB\x90\xEB\x90\xEB\x90"
    DATA_END ="\x7F"

    def __init__(self, io, controller_id=0x16):
        """Constructs a new Tracer object for communicating with the charge 
        controller.  port and baud specify the serial port.  The controller
        ID appears to be ignored; the documentation uses a value of 0x16 so
        that's used by default here too."""
        self.controller_id = controller_id
        self.io = io

    def send(self, cmd, args=""):
        """Sends a command to the device.  args should be packed binary data,
        without the CRC."""
        out = TracerBase.PWL_START + TracerBase.COMM_SYNC
        data = (chr(self.controller_id) + chr(cmd.value) + chr(len(args)) 
            + args)
        out += data
        out += struct.pack(">H", crc(data))
        out += TracerBase.DATA_END
        self.io.send(out)

    def read(self, expected_cmd=None):
        """Reads the response from the device.  Will raise various exceptions
        if a response is not received in a timely manner, or if the response
        is malformed or corrupted in some way.  If expected_cmd is specified,
        it will keep reading commands until the one specified is received, or
        nothing is received for the duration of the timeout period."""
        syncpos = 0
        while syncpos < len(TracerBase.COMM_SYNC):
            c = self.io.recv(1)
            if len(c) == 0:
                raise TracerSyncTimeout(
                    "Did not receive synchronization response")
            if c == TracerBase.COMM_SYNC[syncpos]:
                syncpos += 1
            else:
                syncpos = 0
        id = self.__read_byte()
        cmd = self.__read_byte()
        length = self.__read_byte()
        if length > 0:
            args = self.io.recv(length)
            if len(args) < length:
                raise TracerReadTimeout(
                    "Timed out while waiting for payload data")
        else:
            args = None
        crc_str = self.io.recv(2)
        if len(crc_str) < 2:
            raise TracerReadTimeout("Timed out while waiting for CRC")
        (crc_val,) = struct.unpack(">H", crc_str)
        payload = chr(id) + chr(cmd) + chr(length) 
        if args is not None:
            payload += args
        if crc_val != crc(payload):
            raise TracerCRCError(
                "Computed CRC of received data does not match checksum")
        terminator = self.__read_byte()
        if expected_cmd is not None and cmd != expected_cmd.value:
            return read(expected_cmd)
        else:
            return self.__process_data(cmd, args)

    def read_realtime(self):
        """Reads the "real-time" parameters from the device."""
        self.send(Commands.ReadRealtime)
        return self.read(Commands.ReadRealtime)

    def set_load_on(self, on):
        """Sets the state of the load switch (true for on)."""
        self.send(Commands.ManualControl, chr(1) if on else chr(0))
        return self.read(Commands.ManualControl)
    
    def __read_byte(self):
        c = self.io.recv(1)
        if len(c) == 0:
            raise TracerReadTimeout("Timed out waiting for data byte")
        return ord(c)

    def __process_data(self, cmd, args):
        if cmd == Commands.ReadRealtime.value :
            if len(args) != 24:
                raise TracerMalformedDataError(
                    "Wrong response length for realtime data command")
            (
                battery_voltage,
                pv_voltage,
                load_current,
                overdischarge_voltage,
                battery_full_voltage,
                load_on,
                overload,
                load_short,
                battery_overload,
                over_discharge,
                full_battery,
                charging,
                battery_temperature,
                charge_current
            ) = struct.unpack("<HHxxHHH???x????BHx", args)
            return {
                'battery_voltage': battery_voltage / 100.,
                'pv_voltage': pv_voltage / 100.,
                'load_current': load_current / 100.,
                'overdischarge_voltage': overdischarge_voltage / 100.,
                'battery_full_voltage': battery_full_voltage / 100.,
                'load_on': load_on,
                'overload': overload,
                'load_short': load_short,
                'battery_overload': battery_overload,
                'over_discharge': over_discharge,
                'battery_full': full_battery,
                'charging': charging,
                'battery_temperature': battery_temperature - 30,
                'charge_current': charge_current / 100.
            }
        elif cmd == Commands.ManualControl.value:
            if len(args) != 1:
                raise TracerMalformedDataError(
                    "Wrong response length for realtime data command")
            load_state = ord(args[0]) != 0
            return {
                "load_on": load_state,
            }

class NetTracer(TracerBase):
    
    def __init__(self, hostname, port, controller_id=0x16):
        TracerBase.__init__(self, BufferedSocketReceiver((hostname, port)), 
            controller_id)

class Tracer(TracerBase):

    def __init__(self, port, baud=9600, controller_id=0x16):
        TracerBase.__init__(self, SerialReceiver(port, baud), 
            controller_id)


def crc(s):
    """Function for computing the CRC used in the protocol.  I haven't looked
    at it closely enough to really see what it's doing..."""
    s += "\x00\x00"
    p = 0
    r1 = ord(s[p]); p+=1
    r2 = ord(s[p]); p+=1
    for i in range(len(s) - 2):
        r3 = ord(s[p]); p+=1
        for j in range(8):
            r4 = r1
            r1 = (r1 << 1) & 0xFF
            if (r2 & 0x80) != 0:
                r1 = (r1 + 1) & 0xFF
            r2 = (r2 << 1) & 0xFF
            if (r3 & 0x80) != 0:
                r2 = (r2 + 1) & 0xFF
            r3 = (r3 << 1) & 0xFF
            if (r4 & 0x80) != 0:
                r1 = r1 ^ 0x10
                r2 = r2 ^ 0x41
    return (r1 << 8) | r2

class TracerException(IOError):
    pass

class TracerSyncTimeout(TracerException):
    pass

class TracerReadTimeout(TracerException):
    pass

class TracerCRCError(TracerException):
    pass

class TracerMalformedDataError(TracerException):
    pass
