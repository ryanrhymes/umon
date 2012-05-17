#!/usr/bin/python
#
# This script is modified based on center.py, and supports IPV4 UDP multicast.
# The script keeps listening the broadcasts from the nodes.
#
# Liang Wang @ Dept. of Computer Science, University of Helsinki, Finland
# 2011.03.07
#

import time
import os,sys
import struct
import pickle
import socket
import threading
import subprocess
import SocketServer
from myutil import *
from multiprocessing import *

INCQUE = Queue(2**20)

class MyUDPServer(SocketServer.UDPServer):
    allow_reuse_address = True
    pass

class MyRequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        try:
            data = pickle.loads(self.request[0].strip())
            #print "%s wrote:%s" % (self.client_address[0], data) # Remember to comment it out!!!
            INCQUE.put(data, False)
            socket = self.request[1]
            #socket.sendto("OK", self.client_address)
        except Exception, err:
            print "Exception:CentralServer.handle():", err

    def handle_error(self, request, client_address):
        print "Error:CentralServer.handle_error():", request

class MyListener(object):
    def __init__(self, mgrp=None, mport=None, register=False):
        #self.addr = (subprocess.Popen(["hostname","-I"], stdout=subprocess.PIPE).communicate()[0].split()[0], 1212)
        self.addr = (mgrp if mgrp else get_myip(), mport if mport else 1212)
        self.server = MyUDPServer(self.addr, MyRequestHandler)
        self.server.allow_reuse_address = True
        self.sock = socket.fromfd(self.server.fileno(), socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.regs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        if register:
            t = threading.Thread(target=self.register_me, args=())
            t.daemon = True
            t.start()
        pass

    def register_me(self):
        while True:
            for i in range(1, 256):
                try:
                    self.regs.sendto(pickle.dumps(self.addr, pickle.HIGHEST_PROTOCOL),
                                     ("ukko%03i.hpc.cs.helsinki.fi" % i, self.addr[1]))
                except Exception, err:
                    print "Exception:centermc.py:MyListener.register_me():", err
            time.sleep(300)
        pass

    def listen_forever(self):
        self.server.serve_forever()
        pass

if __name__ == "__main__":
    listener = MyListener()
    listener.listen_forever()
    sys.exit(0)
