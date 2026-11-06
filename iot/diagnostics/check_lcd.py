"""Lee I2CexpDiag a 9600 baudios. SOLO placa dedicada a probar el LCD.
--reset reinicia esa placa para capturar la prueba completa desde setup.
"""
import argparse
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
from serial_bridge import serial

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',required=True)
    parser.add_argument('--seconds',type=float,default=30)
    parser.add_argument('--reset',action='store_true')
    args=parser.parse_args()
    if not 1 <= args.seconds <= 120: parser.error('seconds debe estar entre 1 y 120')
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    port=serial.Serial(port=None,baudrate=9600,timeout=.5)
    port.dtr=False;port.rts=False;port.port=args.port
    with port:
        if args.reset:
            port.reset_input_buffer();time.sleep(.1);port.dtr=True
        deadline=time.monotonic()+args.seconds
        while time.monotonic()<deadline:
            line=port.readline().decode('utf-8',errors='replace').strip()
            if line:print(line,flush=True)
if __name__=='__main__':main()
