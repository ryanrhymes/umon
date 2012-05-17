#!/usr/bin/python
#
# This script is modified based on node.py, and supports IPV4 UDP multicast.
# The script keeps monitoring and broadcasting the node's status. More
# features might be added in future. Stability is the first consideration.
#
# Liang Wang @ Dept. of Computer Science, University of Helsinki, Finland
# 2011.03.07
#

import re
import os
import sys
import time
import random
import pickle
import socket
import threading
import subprocess
import multiprocessing

BPORT = 1980
DEBUG = True
REGHOST = None
REGPORT = 1212
PACKAGE_LEN = 16*2**10

class Node(threading.Thread):
    """Monitor the node's stats itself."""
    def __init__(self):
        threading.Thread.__init__(self)
        self.agents = {}
        self.id = random.randint(0, 65535)
        self.ip, self.eth = self.get_ip_eth()
        self.interval = 1
        self.last_update = time.time()
        self.rx, self.tx = 0, 0
        self.clients = {}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.bsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.bsock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.event = threading.Event()
        t1 = threading.Thread(target=self.registrar, args=())
        t1.daemon = True
        t1.start()
        t2 = threading.Thread(target=self.report_service, args=())
        t2.daemon = True
        t2.start()
        t3 = threading.Thread(target=self.probe, args=())
        t3.daemon = True
        t3.start()
        pass

    def broadcast(self, msg):
        self.bsock.sendto(msg, ("<broadcast>", BPORT))
        pass

    def get_ip_eth(self):
        ip = subprocess.Popen(["hostname","-I"], stdout=subprocess.PIPE).communicate()[0].split()[0]
        eth = "eth2"
        for i in range(16):
            s = subprocess.Popen(["ifconfig", "eth%i" % i], stdout=subprocess.PIPE).communicate()[0]
            if re.search (r"(%s)" % ip, s, re.S):
                eth = "eth%i" % i
                break
        return (ip, eth)

    def get_app_path(self):
        app_path = os.path.realpath(__file__)
        return app_path

    def probe(self):
        t0 = time.time()
        while True:
            try:
                t1 = time.time()
                t = max(int(t1 - t0), 1)
                self.broadcast("live" + str(self.id))
                if t % 60 == 0:
                    if len(self.agents) < 2:
                        self.start_possible_agents()
                    for agid, agtp in self.agents.items():
                        agip, agtm = agtp
                        if t1 - agtm > 300:
                            self.agents.pop(agid)
                            if self.id == max(self.agents.keys()):
                                self.start_agent(agip)
                if t % 3600 == 0 and self.id == max(self.agents.keys()):
                    self.start_possible_agents()
                time.sleep(1)
            except Exception, err:
                if DEBUG:
                    print "Exception:node.py:Node.probe():", err
        pass

    def send(self, data):
        try:
            for client, ts in self.clients.items():
                try:
                    if time.time() - ts < 800:
                        self.sock.sendto(data + "\n", client)
                    else:
                        del self.clients[client]
                except Exception, err:
                    print "Exception:node.py:Node.send():for_loop", err
            if DEBUG:
                print("Send %i bytes message to %i clients, %i active nodes, boss:%s" %
                      (len(data), len(self.clients), len(self.agents), self.agents[max(self.agents.keys())][0]))
        except Exception, err:
            if DEBUG:
                print "Exception:node.py:Node.send():", err

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", BPORT))
        while not self.event.isSet():
            try:
                msg, addr = sock.recvfrom(PACKAGE_LEN)
                cmd, args = msg[0:4], msg[4:]
                if cmd == "helo":
                    if addr[0] != self.ip:
                        self.broadcast("agid" + str(111))
                elif cmd == "live":
                     self.agents[int(args)] = (addr[0], time.time())
                     if self.id == int(args) and self.ip != addr[0]:
                         old_id = self.id
                         self.id = random.randint(0, 65535)
                         self.broadcast("dele" + str(old_id))
                elif cmd == "dele":
                    self.agents.pop(int(args))
                elif cmd == "exit":
                    break
            except KeyboardInterrupt:
                break
            except Exception, err:
                print "Exception:Node.start():", err
        pass

    def start_possible_agents(self):
        all_agents = self.get_all_possible_agents(self.ip)
        active_agents = set()
        for k, v in self.agents.items():
            ip, ts = v
            active_agents.add(ip)
        for agent in all_agents:
            if agent != self.ip and agent not in active_agents:
                t = threading.Thread(target=self.start_agent, args=(agent,))
                t.daemon = True
                t.start()
        pass

    def get_all_possible_agents(self, ip):
        """Return the IP addresses for all possible agents."""
        agents = []
        parts = ip.split('.')
        prefix = "%s.%s.%s." % (parts[0],parts[1],parts[2])
        for i in range(255):
            agent_ip = prefix + str(i)
            agents.append(agent_ip)
        return agents

    def start_agent(self, ip):
        """Start the agent on a node based on given ip."""
        ret = subprocess.call("ssh -o BatchMode=yes -o StrictHostKeyChecking=no %s 'screen -dmS NodeMonitor %s; exit'" %
                              (ip,self.get_app_path()),
                              shell=True,
                              stdout=open('/dev/null', 'w'),
                              stderr=subprocess.STDOUT)
        return ret

    def report_service(self):
        while True:
            try:
                time.sleep(self.interval)
                self.report_stats()
            except Exception, err:
                print "Exception:Node.report_service():", err

    def registrar(self):
        REGHOST = subprocess.Popen(["hostname","-I"], stdout=subprocess.PIPE).communicate()[0]
        REGHOST = REGHOST.split()[0]    # UKKO SUCKS!
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((REGHOST, REGPORT))
        while not self.event.isSet():
            try:
                client = pickle.loads(sock.recv(1024))
                self.clients[client] = time.time()
            except Exception, err:
                print "Exception:Node.registrar():", err
        pass

    def report_stats(self):
        """Some information is commented out since I don't need them at
        the moment. Then I can save some bandwidth."""
        stats = {}
        stats["timestamp"] = time.time()
        stats["type"] = "node"
        # uname
        uname = os.uname()
        #stats["sysname"] = uname[0]
        stats["nodename"] = uname[1]
        #stats["release"] = uname[2]
        #stats["version"] = uname[3]
        #stats["machine"]  = uname[4]
        # uptime
        s = subprocess.Popen("uptime", stdout=subprocess.PIPE).communicate()[0]
        stats["user_count"] = re.search(r"(\d+) user", s).groups()[0]
        stats["load"] = re.search(r"load average: (.+?),", s).groups()[0]
        #stats["up"] = re.search(r"up (.+?),", s).groups()[0]
        stats["cpu_count"] = multiprocessing.cpu_count()
        # free -m
        s = subprocess.Popen(["free", "-m"], stdout=subprocess.PIPE).communicate()[0]
        s = re.search(r"Mem:.*?(\d+)\W+(\d+)\W+(\d+)", s, re.I).groups()
        stats["mem_total"] = s[0]
        stats["mem_used"] = s[1]
        # how many unique users are there
        #stats["user_uniq"] = int(subprocess.Popen("who | cut -d ' ' -f 1 | sort | uniq | wc -l", shell=True, stdout=subprocess.PIPE).communicate()[0])
        # df -h
        s = subprocess.Popen(["df", "-h", "/"], stdout=subprocess.PIPE).communicate()[0]
        stats["disk"] = re.search(r"(\d+%)", s).group(0)
        # ifconfig
        interval = time.time() - self.last_update
        s = subprocess.Popen(["ifconfig", self.eth], stdout=subprocess.PIPE).communicate()[0]
        m = re.search(r"RX.*?(\d+).*?\((.*?)\)", s).groups()
        stats["rx"] = m[1]
        rx0, rx1 = self.rx, int(m[0])
        self.rx = rx1
        stats["rr"] = int((rx1-rx0)/interval)
        m = re.search(r"TX.*?(\d+).*?\((.*?)\)", s).groups()
        stats["tx"] = m[1]
        tx0, tx1 = self.tx, int(m[0])
        stats["tr"] = int((tx1-tx0)/interval)
        self.tx = tx1
        self.last_update = time.time()

        # serialization
        data = pickle.dumps(stats, pickle.HIGHEST_PROTOCOL)
        self.send(data)
        pass

    pass


def is_running(fn):
    """If there is another monitor running, then quit."""
    uid = os.getuid()
    p = subprocess.Popen(['lsof', '-i', "UDP:%i" % BPORT],
                         stdout = subprocess.PIPE)
    s = p.communicate()[0].strip()
    b = len(s) > 0
    return b


if __name__=="__main__":
    if not is_running(__file__):
        node = Node()
        node.start()
        print "Node monitor stops"
    sys.exit(0)
