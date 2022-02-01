import socket
import threading
import time
import traceback
from peer_connection import PeerConnection

def thread_debug(msg):
    thread = str(threading.currentThread().getName())
    print(f'{thread}, {msg}')

class Peer:
    def __init__(self, serverport, serverhost, debug=False):
        self.serverport = serverport
        if serverhost: self.serverhost = serverhost
        else: self.__init_serverhost()
        
        self.my_id = f'{self.serverhost}:{serverport}'
        self.debug = debug
        
        self.peerlock = threading.Lock()

        self.peers = {}
        self.shutdown = False
        self.handlers = {}
        self.router = None

    def __init_serverhost(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('www.google.com', 80))
        self.serverhost = s.getsockname()[0]
        s.close()

    def __debug(self, msg):
        thread_debug(msg)

    def make_server_socket(self, port, backlog=5):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind('', port)
        s.listen(backlog)
        return s

    def __handle_peer(self, client_socket):
        self.__debug( 'New child ' + str(threading.currentThread().getName()) )
        self.__debug( 'Connected ' + str(client_socket.getpeername()) )

        host, port = client_socket.getpeername()
        peer_conn = PeerConnection(None, host, port, client_socket, debug=False)

        try:
            msg_type, msg_data = peer_conn.recv_data()
            if msg_type: msg_type = msg_type.upper()
            if msg_type not in self.handlers:
                self.__debug('Not handled: %s: %s', (msg_type, msg_data))
            else:
                self.__debug( 'Handling peer msg: %s: %s' % (msg_type, msg_data) )
            self.handlers[ msg_type ]( peer_conn, msg_data )
        except KeyboardInterrupt:
            raise
        except:
            if self.debug:
                traceback.print_exc()
        
        self.__debug( 'Disconnecting ' + str(client_socket.getpeername()) )
        peer_conn.close()


    def add_handler(self, msg_type, handler):
        assert len(msg_type) ==  4
        self.handlers[msg_type] = handler

    
    def add_router(self, router):
        self.router = router

    def add_peer(self, peer_id, host, port):
        if peer_id not in self.peers:
            self.peers[peer_id] = (host, int(port))
            return True
        else:
            return False
    
    def get_peer(self, peer_id):
        assert peer_id in self.peers
        return self.peers[peer_id]
    
    def remove_peer(self, peer_id):
        if peer_id in self.peers:
            del self.peers[peer_id]
        
    def add_peer_at(self, loc, peer_id, host, port):
        self.peers[loc] = (peer_id, host, int(port))
    
    def get_peer_at(self, loc):
        if loc not in self.peers:
            return None
        return self.peers[loc]

    def remove_peer_at(self, loc):
        self.remove_peer(loc)
    
    def get_peer_ids(self):
        return self.peers.keys()
    
    def number_of_peers(self):
        return len(self.peers)

    def __run_stabilizer(self, stabilizer, delay):
        while not self.shutdown:
            stabilizer()
            time.sleep(delay)
    
    def start_stabilizer(self, stabilizer, delay):
        t = threading.Thread(target = self.__run_stabilizer,
                             args = [stabilizer, delay])
        t.start()
        
    def send_to_peer(self, peer_id, msg_type, msg_data, wait_reply=True):
        if self.router:
            next_pid, host, port = self.router(peer_id)
        if not self.router or not next_pid:
            self.__debug(f'Unabel to route %{msg_type} to %{peer_id}')
            return None
        return self.connect_and_send (host, port, msg_type, msg_data,
                                      pid=next_pid,
                                      wait_reply=wait_reply)

    def connect_and_send(self, host, port, msg_type, msg_data, pid=None, wait_reply=True):
        msg_reply = []
        try:
            peer_conn = PeerConnection(pid, host, port, debug=self.debug)
            peer_conn.send_data(msg_type, msg_data)
            self.__debug(f'Sent {pid}: {msg_type}')

            if wait_reply:
                one_reply = peer_conn.recv_data()
                while (one_reply != (None, None)):
                    msg_reply.append(one_reply)
                    self.__debug(f'Got reply {pid}: {str(msg_reply)}')
                    one_reply = peer_conn.recv_data()
                peer_conn.close()
        except KeyboardInterrupt:
            raise
        except:
            if self.debug:
                traceback.print_exc()
            
        return msg_reply

    def check_live_peers(self):
        to_delete = []
        for pid in self.peers:
            is_connected = False
            try:
                self.__debug(f'Check live {pid}')
                host, port = self.peers[pid]
                peer_conn = PeerConnection(pid, host, port, debug=self.debug)
                peer_conn.send_data('PING', '')
                is_connected = True
            except:
                to_delete(pid)
                if is_connected:
                    peer_conn.close()

        self.peerlock.acquire()
        try:
            for pid in to_delete:
                if pid in self.peers:
                    del self.peers[pid]
        finally:
            self.peerlock.release()

    def main_loop(self):
        s = self.make_server_socket(self.serverport)
        s.settimeout(2)
        self.__debug(f'Server started: {self.serverhost}, {self.serverport}')

        while not self.shutdown:
            try:
                self.__debug('Listening for connections...')  
                client_socket, client_addr = s.accept()
                client_socket.settimeout(None)

                t = threading.Thread(target = self.__handle_peer, args = [ client_socket ])
                t.start()
            except KeyboardInterrupt:
                print('KeyboardInterrupt: stopping mainloop')
                self.shutdown = True
            except:
                if self.debug:
                    traceback.print_exc()
                continue
        
        self.__debug('Main loop exiting')
        s.close()

