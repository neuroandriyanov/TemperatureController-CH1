"""Minimal Modbus RTU client. Default CLI command is READ ONLY.
Requires: python -m pip install pyserial
Examples: python examples/client.py PORT --address 1
          python examples/client.py PORT --address 1 --stop
"""
import argparse
import struct
import time

def crc16(data):
    crc=0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc=(crc>>1)^0xA001 if crc&1 else crc>>1
    return crc

class ControllerClient:
    def __init__(self,port,address=1):
        if not 1 <= address <= 247:
            raise ValueError("Slave address must be 1..247")
        import serial
        self.address=address
        self.serial=serial.Serial(None,38400,bytesize=8,parity="E",stopbits=1,timeout=0.5,write_timeout=0.5)
        # Hardware flow control is unused. Set inactive levels before opening.
        self.serial.dtr=False
        self.serial.rts=False
        self.serial.port=port
        self.serial.open()

    def close(self):
        self.serial.close()

    def _exact(self,n):
        data=bytearray()
        while len(data)<n:
            piece=self.serial.read(n-len(data))
            if not piece:
                raise TimeoutError("Incomplete Modbus response")
            data.extend(piece)
        return bytes(data)

    def _request(self,fc,payload):
        time.sleep(0.004)
        self.serial.reset_input_buffer()
        request=bytes([self.address,fc])+payload
        request+=struct.pack("<H",crc16(request))
        self.serial.write(request)
        self.serial.flush()
        head=self._exact(3)
        rest=2 if head[1]&0x80 else (head[2]+2 if fc in (3,4) else 5)
        response=head+self._exact(rest)
        if crc16(response[:-2]) != int.from_bytes(response[-2:],"little"):
            raise ValueError("Response CRC mismatch")
        if response[0]!=self.address or response[1] not in (fc,fc|0x80):
            raise ValueError("Unexpected slave/function")
        if response[1]&0x80:
            raise RuntimeError(f"Modbus exception {response[2]:02x}")
        if fc in (6,16) and response[:6]!=request[:6]:
            raise ValueError("Write acknowledgement mismatch")
        return response

    def read(self,address,count,input_registers=False):
        if not 1<=count<=125 or not 0<=address<=65535 or address+count>65536:
            raise ValueError("Invalid register range")
        reply=self._request(4 if input_registers else 3,struct.pack(">HH",address,count))
        if reply[2]!=count*2:
            raise ValueError("Wrong byte count")
        return list(struct.unpack(">"+"H"*count,reply[3:-2]))

    def write(self,address,values):
        if not 1<=len(values)<=123 or not 0<=address<=65535 or address+len(values)>65536:
            raise ValueError("Invalid write range")
        # Negative signed values become two's-complement registers.
        encoded=[v & 0xFFFF for v in values]
        if any(not -32768<=v<=65535 for v in values):
            raise ValueError("Value does not fit a register")
        if len(encoded)==1:
            self._request(6,struct.pack(">HH",address,encoded[0]))
        else:
            self._request(16,struct.pack(">HHB",address,len(encoded),2*len(encoded))+struct.pack(">"+"H"*len(encoded),*encoded))

    def stop(self):
        self.write(256,[0])

    def save(self):
        self.write(258,[0xA55A])
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            time.sleep(0.05)
            status=self.read(37,1,True)[0]
            if status==2:
                return
            if status==4:
                raise IOError("EEPROM write/verification failed")
        raise TimeoutError("EEPROM save not completed")

def signed(v):
    return v-65536 if v&0x8000 else v

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port");parser.add_argument("--address",type=int,default=1)
    parser.add_argument("--stop",action="store_true")
    args=parser.parse_args();client=ControllerClient(args.port,args.address)
    try:
        if args.stop:
            client.stop()
        r=client.read(0,64,True)
        print({"firmware":hex(r[0]),"mode":r[4],"active_faults":hex(r[8]<<16|r[9]),
               "latched_faults":hex(r[10]<<16|r[11]),"temperature_C":signed(r[16])/10,
               "cold_junction_C":signed(r[17])/100,"current_A":r[22]/1000,
               "loop_mA":r[28]/1000,"measurement_flags":r[35],"temperature_age_ms":r[32]})
    finally:
        client.close()
