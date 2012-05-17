#!/usr/bin/env python
#
# This script provides GUI for BitTorrent experiments on cluster. Please
# supress your comments if it relates to the UI design, :-)
#
# Liang Wang @ Dept. of Computer Science, University of Helsinki, Finland
# 2011.03.08
#


import wx
import sys
import time
import threading
import multiprocessing
from centermc import *

BTNID_START = 5
NLISTID = 10

class Node(object):
    def __init__(self, id):
        self.id = id - 1
        self.name = "ukko%03i" % (id)
        self.x, self.y = 0, 0
        self.w, self.h = 100, 100
        pass

    pass

class PeerPanel(object):
    def __init__(self, id, parent):
        self.id = id
        self.parent = parent
        self.x, self.y, self.w, self.h = 0, 0, 0, 0
        self.r, self.rn = 3, 60
        self.ul_history = [1]
        self.dl_history = [1]
        self.ul_norm = 10
        self.dl_norm = 10
        pass

    def update(self, peer, dc):
        x, y, w, h = self.x, self.y, self.w, self.h
        fz = int(h/12.0)
        self.draw_percentage_bar(peer, dc)
        dc.SetFont(wx.Font(fz, wx.FONTFAMILY_SWISS,wx.FONTSTYLE_NORMAL,wx.FONTWEIGHT_NORMAL))
        dc.SetTextForeground(wx.Colour(0,255,0,alpha=255))
        dc.DrawText(peer["peer"], x+4, y)
        dc.DrawText("ac:%i  uc:%i  tc:%i" % (peer["ac"], peer["uc"], peer["tc"]), x+4, y+fz+4)
        dc.DrawText("uz:%iMB  dz:%iMB\n" % (peer["ul_size"]/2**20, peer["dl_size"]/2**20), x+4, y+2*(fz+4))
        dc.DrawText("ul:%iKB/s  dl:%iKB/s\n" % (peer["ul_rate"]/1024, peer["dl_rate"]/1024), x+4, y+3*(fz+4))
        self.draw_extra_info(peer, dc)
        self.draw_speed_curve(peer, dc)
        self.draw_panel_frame(dc)
        pass

    def draw_extra_info(self, peer, dc):
        x, y, w, h = self.x, self.y, self.w, self.h
        fz = int(h/12.0)
        s = ""
        if peer["fw"]:
            dc.SetTextForeground(wx.Colour(255,0,0))
            s += "FW"
        if peer["fr"]:
            dc.SetTextForeground(wx.Colour(0,255,255))
            s += "FR"
        if len(s)==4:
            dc.SetTextForeground(wx.Colour(255,0,0))
            s = "FW&FR"
        dc.DrawText(s, x+w-(len(s))*fz-2, y+fz+4)
        pass

    def draw_panel_frame(self, dc):
        x, y, w, h = self.x, self.y, self.w, self.h
        dc.SetPen(wx.Pen('grey', 1))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(x, y, w, h)
        pass

    def draw_speed_curve(self, peer, dc):
        x, y, w, h, r = self.x, self.y, self.w, self.h, self.r
        rn = int(w/r)
        self.ul_history.append(peer["ul_rate"]/1024)
        self.dl_history.append(peer["dl_rate"]/1024)
        norm = max(max(self.ul_history), max(self.dl_history))
        self.parent.norm = max(norm, self.parent.norm)
        norm = self.parent.norm
        self.ul_history = self.ul_history[-rn:]
        self.dl_history = self.dl_history[-rn:]
        dc.SetPen(wx.Pen("cyan", 0, wx.TRANSPARENT))
        dc.SetBrush(wx.GREEN_BRUSH)
        for i in range(1, len(self.dl_history)):
            dl = self.dl_history[-i]
            dh = int(h*dl/(2*norm))
            dy = y + h - dh
            dx = x + w - i*r
            sd = int(r/2)
            dc.DrawRectangle(dx-sd, dy, r-1, dh)
        dc.SetPen(wx.Pen("cyan", 0, wx.TRANSPARENT))
        dc.SetBrush(wx.RED_BRUSH)
        for i in range(1, len(self.ul_history)):
            ul = self.ul_history[-i]
            uh = int(h*ul/(2*norm))
            uy = y + h - uh
            ux = x + w - i*r
            dc.DrawRectangle(ux, uy, r-1, uh)
        pass

    def draw_percentage_bar(self, peer, dc):
        x, y, w, h = self.x, self.y, self.w, self.h
        dc.SetPen(wx.Pen("cyan", 0, wx.TRANSPARENT))
        dc.SetBrush(wx.Brush(wx.Colour(0,0,255),wx.SOLID))
        dc.DrawRectangle(x, y, w*peer["dl_size"]/(2044*2**20), int(h/12.0)+2)
        pass

    pass

class ControlPanel(wx.Panel):
    def __init__(self, parent, nodes):
        wx.Panel.__init__(self, parent, -1, size=(500,200))
        self.SetBackgroundColour('black')
        self.node_listbox = wx.ListBox(self, NLISTID, (0,0))
        self.node_listbox.SetBackgroundColour(wx.Colour(32,32,32))        
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.node_listbox, 1, wx.EXPAND|wx.ALL, 5)        
        sizer.Add(wx.Button(self, BTNID_START, 'start'), 0, wx.EXPAND|wx.ALL, 5)
        self.SetSizer(sizer)
        self.load_nodes(nodes, self.node_listbox)
        pass

    def load_nodes(self, nodes, list):
        nodelist = []
        for node in nodes:
            nodelist += [node.name]
        list.InsertItems(nodelist, 0)
        pass

    pass

class InfoPanel(object):
    def __init__(self, parent):
        self.matrix_x, self.matrix_y = 12, 10
        self.panellist = [ PeerPanel(i,self) for i in range(self.matrix_x*self.matrix_y) ]
        self.norm = 10
        pass

    def update_size(self, x, y, w, h):
        scrW, scrH = w, h
        w, h = scrW/self.matrix_x - 4, scrH/self.matrix_y - 4
        for i in range(self.matrix_y):
            for j in range(self.matrix_x):
                id = i*self.matrix_x+j
                panel = self.panellist[id]
                panel.w, panel.h = w, h
                panel.x, panel.y = x+(w+4)*j, y+(h+4)*i
                panel.r = 3 if int(w/panel.rn)<3 else int(w/panel.rn)
        pass


    def update(self, peers, dc):
        self.norm = 10 if self.norm*0.95<10 else self.norm*0.95
        for peer in peers.values():
            panel = self.panellist[peer["panel"]]
            panel.update(peer, dc)
        pass

class MyFrame(wx.Frame):
    def __init__(self, parent, title, size):
        self.nodes = [ Node(int(i)) for i in sys.argv[1:] ]
        self.peers = {}
        self.peers_lock = threading.Lock()
        self.filter = None
        self.last_refresh = time.time()
        wx.Frame.__init__(self, parent, wx.ID_ANY, title, size=size)
        self.SetBackgroundColour('black')
        topsizer = wx.BoxSizer(wx.HORIZONTAL);
        self.control_panel = ControlPanel(self, self.nodes)
        topsizer.Add(self.control_panel, 0, wx.EXPAND|wx.ALL,10);
        self.info_panel = InfoPanel(self)
        self.SetSizer(topsizer)

        # Bind events
        wx.EVT_SIZE(self, self.on_size)
        wx.EVT_PAINT(self, self.on_paint)
        wx.EVT_LISTBOX(self, NLISTID, self.on_list_select)
        wx.EVT_BUTTON(self, BTNID_START, self.start_experiment)

        # Start the timer to refresh the panel periodically
        self.timer = wx.Timer(self, id=-1)
        self.Bind(wx.EVT_TIMER, self.update, self.timer)
        self.timer.Start(1000)

        pass

    def Show(self):
        wx.Frame.Show(self)
        self.on_size()

    def on_size(self, event=None):
        dc = wx.PaintDC(self)
        self.Layout()
        x, _ = self.GetSizer().GetItem(self.control_panel).GetSize()
        w, h = self.GetSize()
        w, h = w - x, h - 20
        self.info_panel.update_size(x, 10, w, h)
        pass

    def on_paint(self, event=None):
        dc = wx.PaintDC(self)
        self.peers_lock.acquire()
        try:
            self.info_panel.update(self.peers, dc)
        except Exception, err:
            print "Exception:MyFrame.on_paint():", err
        self.peers_lock.release()
        pass

    def update(self, event=None):
        self.Refresh(False)
        pass

    def on_list_select(self, event=None):
        self.filter = event.GetString()
        self.peers = {}
        pass

    def start_experiment(self, event=None):
        print "Put your start code here."
        self.detail_panel.Show()
        self.info_panel.Hide()
        self.Layout()
        pass

    def process_multicast(self):
        while True:
            try:
                data = INCQUE.get()
                self.peers_lock.acquire()
                if data["node"] == self.filter:
                    peer = data["peer"]
                    if peer in self.peers.keys():
                        data["panel"] = self.peers[peer]["panel"]
                    else:
                        data["panel"] = len(self.peers)
                    self.peers[peer] = data
                self.peers_lock.release()
            except Exception, err:
                print "Exception:process_multicast():", err
                self.peers_lock.release()
        pass

    def test(self):
        self.GetSizer().Remove(self.info_panel)
        self.info_panel.Hide()
        self.GetSizer().Add(self.detail_panel, 1, wx.EXPAND|wx.ALL,10);
        self.detail_panel.Show()
        pass

if __name__=="__main__":
    app = wx.App()
    frame = MyFrame(None, "Liang, Experiment Monitor", (800, 600))
    frame.Show()
    # Start the multicast listener as daemon
    listener = Process(target=MyListener(None,2121,False).listen_forever, args=())
    listener.daemon = True
    listener.start()
    # Start the worker thread for processing update multicasts
    t = threading.Thread(target=frame.process_multicast, args=())
    t.daemon = True
    t.start()
    # Start the app's mainloop
    app.MainLoop()
