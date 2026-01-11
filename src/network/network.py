# https://github.com/hyperdriveguy/python-p2p
# https://github.com/AnandShegde/p2p
from concurrent.futures import thread
import threading
import queue
from time import sleep
import queue
import socket


class Manager:

    s: socket.socket
    
    accepting_thread: threading.Thread
    multicasting_thread: threading.Thread
    recv_thread: threading.Thread

    MULTICAST_IP = ""
    PORT = "7649"
    connections = {}

    def __init__(self):
        self.socket = socket.socket()
        self.socket.bind(self.MULTICAST_IP, self.PORT)
        self.socket.listen(10)
    
    def __del__(self):
        self.socket.close()





