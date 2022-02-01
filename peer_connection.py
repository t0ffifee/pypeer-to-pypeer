from inspect import trace
import sys
import socket
import struct
from tempfile import TemporaryFile
import threading
import time
import traceback

def thread_debug(msg):
    thread = str(threading.currentThread().getName())
    print(f'{thread}, {msg}')

class PeerConnection:
    def __init__(self, peer_id, host, port, socket=None, debug=False):
        self.id = peer_id
        self.debug = debug

        if not socket:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.connect((host, int(port)))
        else:
            self.s = socket
        
        # ik weet nog niet wat dit doet lol
        self.sd = self.s.makefile('rw', 0)
    
    def __make_msg(self, msg_type, msg_data):
        msg_len = len(msg_data)
        msg = struct.pack("!4sL%ds",msg_len, msg_type, msg_len, msg_data)
        return msg

    def __debug(self, msg):
        if self.debut:
            thread_debug(msg)

    def send_data(self, msg_type, msg_data):
        try:
            msg = self.__make_msg(msg_type, msg_data)
            self.sd.write(msg)
            self.sd.flush()
        except KeyboardInterrupt:
            raise
        except:
            if self.debut:
                traceback.print_exc()
                return False
        return True
    
    def recv_data(self):
        try:
            msgtype = self.sd.read( 4 )
            if not msgtype: return (None, None)
            
            lenstr = self.sd.read( 4 )
            msglen = int(struct.unpack( "!L", lenstr )[0])
            msg = ""

            while len(msg) != msglen:
                data = self.sd.read( min(2048, msglen - len(msg)) )
                if not len(data):
                    break
                msg += data
            if len(msg) != msglen:
                return (None, None)

        except KeyboardInterrupt:
            raise
        except:
            if self.debug:
                traceback.print_exc()
                return (None, None)

        return ( msgtype, msg )

    def close(self):
        self.s.close()
        self.s = None
        self.sd = None