#!/usr/bin/env python
#
# This file is the main UI of cluster monitor.
#
# Liang Wang @ Dept. of Computer Science, University of Helsinki, Finland
# 2011.03.07
#

import re
import wx
import time
import random
import threading
import subprocess
import multiprocessing
from centermc import *
from myutil import *

class Node(object):
    def __init__(self, id=None, parent=None):
        self.id = id
        self.parent = parent
        self.name = "n%03i" % (id+1)
        self.highlight = False
        self.fontsize = 8
        self.x, self.y = 0, 0
        self.w, self.h = 100, 100
        self.plx, self.ply = 9, 9
        self.plw, self.plh = 9, 9
        self.pmx, self.pmy = 9, 9
        self.pmw, self.pmh = 9, 9
        self.r, self.rn = 3, 30.0        # Radius and Max num of histories
        self.rr_history = [1]
        self.tr_history = [1]
        # The states a node maintains
        self.ts = 0                      # Timestamp for the last message
        self.load = 0.0                  # 1 min average load
        self.cpu_count = 1.0             # Num of CPU cores
        self.mem_used = 0.0              # Used mem
        self.mem_total = 1.0             # Total physic mem
        self.user_count = 0              # Num of login users
        self.user_uniq = 0               # Num of uniq users
        self.disk = ""                   # Disk usage
        self.rx = ""                     # Total data recv by eth
        self.tx = ""                     # Total data send by eth
        self.rr = 0                      # The eth interface recv rate
        self.tr = 0                      # The eth interface send rate
        pass

    def draw(self, dc):
        self.draw_text_info(dc)
        self.draw_node_loadbar(dc, self.load/self.cpu_count, self.mem_used/self.mem_total)
        self.draw_speed_curve(dc)
        self.draw_frame(dc)
        self.parent.rr_total += self.rr
        self.parent.tr_total += self.tr
        pass

    def draw_frame(self, dc):
        x, y, w, h = self.x, self.y, self.w, self.h
        if self.highlight:
            dc.SetPen(wx.Pen('red', 2))
        else:
            dc.SetPen(wx.Pen(wx.Colour(64,64,64), 1))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(x, y, w, h)
        pass

    def draw_text_info(self, dc):
        x, y, w, h, fz = self.x, self.y, self.w, self.h, self.fz
        dc.SetFont(wx.Font(fz, wx.FONTFAMILY_SWISS,wx.FONTSTYLE_NORMAL,wx.FONTWEIGHT_NORMAL))
        if time.time() - self.ts < 60:
            dc.SetTextForeground('green')
        else:
            dc.SetTextForeground('grey')
        if w < 100:
            dc.DrawText("%s" % (self.name), x+1, y)
        else:
            dc.DrawText("%s D:%s U:%i" % (self.name, self.disk, self.user_count), x+2, y)
            dc.DrawText("R:%s T:%s" % (self.rx, self.tx), x+2, y+fz+3)
        pass

    def draw_node_loadbar(self, dc, load, mem):
        load = load if load <= 1 else 1.0
        mem  = mem  if mem  <= 1 else 1.0
        x, y, w, h = self.x, self.y, self.w, self.h
        plx, ply, plw, plh = self.plx, self.ply, self.plw, self.plh
        pmx, pmy, pmw, pmh = self.pmx, self.pmy, self.pmw, self.pmh
        dc.SetPen(wx.Pen('black', 0, wx.TRANSPARENT))
        dc.SetBrush(wx.BLACK_BRUSH)
        dc.GradientFillLinear((plx+1,ply+1,plw-2,plh-2), 'green', 'red')
        dc.GradientFillLinear((pmx+1,pmy+1,pmw-2,pmh-2), 'green', 'red')
        dc.DrawRectangle(plx+plw*load+1,ply+1,plw*(1-load)-1,plh-2)
        dc.DrawRectangle(pmx+pmw*mem+1,pmy+1,pmw*(1-mem)-1,pmh-2)
        pass

    def draw_speed_curve(self, dc):
        x, y, w, h, r = self.x, self.y, self.w, self.h, self.r
        rn = int(w/r)
        self.rr_history.append(self.rr)
        self.tr_history.append(self.tr)
        norm = max(max(self.rr_history), max(self.tr_history))
        self.parent.norm = max(norm, self.parent.norm)
        norm = 3.5*self.parent.norm
        self.rr_history = self.rr_history[-rn:]
        self.tr_history = self.tr_history[-rn:]
        dc.SetPen(wx.Pen("cyan", 0, wx.TRANSPARENT))
        dc.SetBrush(wx.GREEN_BRUSH)
        for i in range(1, len(self.rr_history)):
            rr = self.rr_history[-i]
            rh = int(h*rr/(norm))
            ry = y + h - rh
            rx = x + w - i*r
            rd = int(r/2)
            dc.DrawRectangle(rx-rd, ry, r-1, rh)
        dc.SetPen(wx.Pen("cyan", 0, wx.TRANSPARENT))
        dc.SetBrush(wx.RED_BRUSH)
        for i in range(1, len(self.tr_history)):
            tr = self.tr_history[-i]
            th = int(h*tr/(norm))
            ty = y + h - th
            tx = x + w - i*r
            dc.DrawRectangle(tx, ty, r-1, th)
        pass

class MyFrame(wx.Frame):
    def __init__(self, parent, title, size):
        self.matrix_x, self.matrix_y = 16, 15
        self.nodes = [ Node(i, self) for i in range(self.matrix_x*self.matrix_y) ]
        self.norm = 10
        self.nodes_lock = threading.Lock()
        self.rr_total = 0
        self.tr_total = 0
        self.power_consumption = get_pc_mikko()
        wx.Frame.__init__(self, parent, wx.ID_ANY, title, size=size)
        self.anchor0 = None
        self.anchor1 = None
        self.last_refresh = time.time()
        self.event = threading.Event()
        self.SetBackgroundColour('black')
        wx.EVT_SIZE(self, self.on_size)
        wx.EVT_PAINT(self, self.on_paint)
        wx.EVT_LEFT_DOWN(self, self.on_left_down)
        wx.EVT_LEFT_UP(self, self.on_left_up)
        wx.EVT_MOTION(self, self.on_motion)
        wx.EVT_RIGHT_DCLICK(self, self.btexp)
        wx.EVT_CLOSE(self, self.on_close)
        # Start the timer to refresh the frame periodically
        self.timer = wx.Timer(self, id=-1)
        self.Bind(wx.EVT_TIMER, self.update, self.timer)
        self.timer.Start(1000)
        # Start the timer to refresh power consumption periodically
        self.power_consumption_timer = wx.Timer(self, id=-1)
        self.Bind(wx.EVT_TIMER, self.update_power_consumption, self.power_consumption_timer)
        self.power_consumption_timer.Start(5*1000)

        pass

    def Show(self):
        wx.Frame.Show(self)
        self.on_size()

    def on_size(self, event=None):
        mx, my = self.matrix_x, self.matrix_y
        scrW, scrH = wx.PaintDC(self).GetSize()
        nw, nh = scrW/mx - 2, scrH/my - 2
        fz = 7 if int(min(nw,nh)/9.5)<7 else int(min(nw,nh)/9.5)
        r, rn = self.nodes[0].r, self.nodes[0].rn
        r = 3 if int(r/rn)<3 else int(r/rn)
        for i in range(my):
            for j in range(mx):
                id = i*mx+j
                node = self.nodes[id]
                node.w, node.h = nw, nh
                node.x, node.y = (nw+2)*j+2, (nh+2)*i+2
                node.plx = node.x + 0.02*nw
                node.ply = node.y + 0.35*nh
                node.plw = nw*0.95
                node.plh = nh*0.15
                node.pmx = node.plx
                node.pmy = node.ply + node.plh + 0.04*nh
                node.pmw = node.plw
                node.pmh = node.plh
                node.fz  = fz
                node.r   = r
        self.Refresh(False)
        pass

    def on_paint(self, event=None):
        dc = wx.PaintDC(self)
        dc.SetPen(wx.Pen('black', 0))
        self.nodes_lock.acquire()
        try:
            self.draw_nodes(dc)
        except Exception, err:
            print "Exception:MyFrame.on_paint():", err
        self.nodes_lock.release()
        self.draw_select_rect(dc)
        self.set_frame_title()
        self.last_refresh = time.time()
        pass

    def update(self, event=None):
        self.norm = 10 if self.norm*0.95<10 else self.norm*0.95
        self.rr_total, self.tr_total = 0, 0
        self.Refresh(False)

    def update_power_consumption(self, event=None):
        self.power_consumption = get_pc_mikko()
        pass

    def btexp(self, event=None):
        args = []
        for node in self.nodes:
            if node.highlight:
                args += [str(node.id+1)]
        subprocess.Popen(["./btexp.py"] + args)
        pass

    def draw_nodes(self, dc):
        for node in self.nodes:
            node.draw(dc)
        pass

    def on_left_down(self, event=None):
        self.anchor0 = (event.m_x, event.m_y)
        pass

    def on_left_up(self, event=None):
        self.highlight_nodes()
        self.anchor0 = None
        self.Refresh(False)
        pass

    def on_motion(self, event=None):
        self.anchor1 = (event.m_x, event.m_y)
        if self.anchor0:
            self.Refresh(False)
        pass

    def on_close(self, event=None):
        self.event.set()
        event.Skip()
        pass

    def draw_select_rect(self, dc):
        if self.anchor0:
            x1, y1 = self.anchor0
            x2, y2 = self.anchor1
            x,  y  = min(x1,x2), min(y1,y2)
            w,  h  = abs(x1-x2), abs(y1-y2)
            dc.SetPen(wx.Pen('red', 3, wx.SHORT_DASH))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(x, y, w, h)
        pass

    def highlight_nodes(self):
        if self.anchor0 and self.anchor1:
            x1,y1,x2,y2 = self.anchor0[0],self.anchor0[1],self.anchor1[0],self.anchor1[1]
            rect = (min(x1,x2),min(y1,y2),abs(x1-x2),abs(y1-y2))
            for node in self.nodes:
                if are_rects_overlapped(rect, (node.x,node.y,node.w,node.h)):
                    node.highlight = not node.highlight
        pass

    def set_frame_title(self):
        rr = calc_rate(self.rr_total)
        tr = calc_rate(self.tr_total)
        self.SetTitle("UKKO CLUSTER  PC: %s W  RX: %s  TX: %s" % (str(self.power_consumption), rr, tr))
        pass

    def process_multicast(self):
        while not self.event.isSet():
            try:
                data = INCQUE.get()
                self.nodes_lock.acquire()
                id = int(re.search(r"(\d+)", data["nodename"]).group(1)) - 1
                n = self.nodes[id]
                n.ts = time.time()
                n.load = float(data["load"])
                n.cpu_count = float(data["cpu_count"])
                n.mem_used = float(data["mem_used"])
                n.mem_total = float(data["mem_total"])
                n.user_count = int(data["user_count"])
                #n.user_uniq = int(data["user_uniq"])
                n.disk = data["disk"]
                n.rx = data["rx"]
                n.tx = data["tx"]
                n.rr = data["rr"]
                n.tr = data["tr"]
                self.nodes_lock.release()
            except Exception, err:
                self.nodes_lock.release()
                print "Exception:process_multicast():", err
    pass

if __name__=="__main__":
    app = wx.App()
    frame = MyFrame(None, "UKKO Cluster", (800,600))
    frame.Show()
    # Start the multicast listener as daemon
    listener = Process(target=MyListener(None, 1212, True).listen_forever, args=())
    listener.daemon = True
    listener.start()
    # Start the worker thread for processing update multicasts
    t = threading.Thread(target=frame.process_multicast, args=())
    t.daemon = True
    t.start()
    # Start the app's mainloop
    app.MainLoop()
