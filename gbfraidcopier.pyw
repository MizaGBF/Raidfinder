# -*- coding: utf-8 -*-
import json
import re
import queue
import configparser
import time
import threading
from time import strftime
import datetime
import base64
import webbrowser
import sys, os

import tkinter as Tk
import tkinter.ttk as ttk
from tkinter import colorchooser, simpledialog, messagebox
import pyperclip
import tweepy

# =============================================================================================
# Sound
# =============================================================================================
soundFile = "" # to store the .wav file

try:
    import winsound # windows only
except ImportError: # linux alternative
    import os
    def playsound():
        os.system('beep -f %s -l %s' % (200,100)) # frequency (Hz) and duration (ms)
else: # windows
    # load the sound file
    try:
        with open('alert.wav','rb') as f: # open the file
            soundFile = f.read() # store in string format
        soundLoaded = True
    except IOError: # not working ? the file probably doesn't exist
        soundLoaded = False

    def playsound(): # run winsound.PlaySound() in a thread (SND_ASYNC doesn't work when playing a sound from the memory)
        if soundLoaded:
            threading.Thread(target=winsound.PlaySound, args=(soundFile, winsound.SND_MEMORY)).start()

# =============================================================================================
# Variables
# =============================================================================================
# version number
revision = "rev.85"
# to store the twitter API keys ( https://developer.twitter.com/en/apps )
consumer_key = None
consumer_secret = None
access_token = None
access_token_secret = None
config = None
# thread variables
tweetQueue = queue.Queue() # contains tweets to be processed
twitterThread = None # will store the current listener thread
streamKill = False # if true, the watchdog will kill the stream
rateLimit = False # if true, twitter is limiting us
twitterConnected = False # simple way to check if connected to twitter
stream = None # store the tweepy stream
appRunning = True # must be true when the app is running
freezeUI = False # if true, do nothing in the ui functions
watchdogKill = False
# stats
startTime = None
statsCount = 7
stats = [0]*statsCount
stats[4] = -1
statLabel = []
# used variables
blacklist = [] # list of blacklisted twitter handles
dupes = [] # contains recent raid codes
timeLabel = None # will contain the text label showing the current time
statusLabel = None # will contain the text label showing the stream status
buttonColor = ['#F0F0F0', '#A0A0A0'] # button colors (not clicked and clicked)
cfgLoaded = False # set to True once the .cfg is loaded
queueframe = None # will contain the ttk.Notebook used for the Queue
bottomHeight = 4 # max number of row for the bottom part
queueSize = 0 # size of the saved code queue
futureQueueSize = 0 # size of the queue size after the next reboot (will be saved in the .cfg)
queuePageSize = 15 # number of element on a Queue Page
queueCode = [None] # contain the codes
queueRaid = [None] # contain the raid names
queueButton = [None] # contain the Tk.Button
queueClicked = [False] # if true, the button color will be changed
queueUpdate = False # set to true when we have to update the buttons
queueMutex = threading.Lock() # to make thread safe actions
raidTab = None # contain the ttk.Notebook object at the top
raidTabSaved = 0 # is used when closing the app
enRaidNameMin = 20 # lower possible position of the raid name (to avoid raid name in the tweet message)
jpRaidNameMin = 15 # same for jp tweet
enRaidNameOffset = 15 # "I need backup！\n" size
jpRaidNameOffset = 7 # "参加者募集！\n" size
focused = False # check if the app is in focus
logSize = 0 # contain the number of lines in the logbox
logLimit = 200 # logbox line limit (old lines will be deleted)
logStrings = [] # store the strings to be put in the logbox
logMutex = threading.Lock() # to make thread safe actions
raidCount = 0 # number of raid (init in jsonLoad)
customCount = 18 # number of saved custom code
customSize = 12 # maximum name size on the custom tab
trk = [] # contain which raid is tracked
cpyOn = [] # contain which raid is auto copied
sndOn = [] # contain which raid is in sound alert mode
# json
raidList = [] # contain all raids (name and codes)
tabData = [] # contain data such as the tab color
searchStrings = [] # used by tweepy
# dictionnaries for faster searches (updated in related functions)
enDict = {}
jpDict = {}
# settings
settings = [
    "Japanese",
    "English",
    "Mute all alerts",
    "Enable log",
    "Allow Auto Copy",
    "Show Tweet Author",
    "Enable Blacklist",
    "Ignore duplicates",
    "Pause the stream"
    ]
settingCount = len(settings) # total number of setting
sJP = 0 # setting ID for japanese filter
sEN = 1 # setting ID for english filter
sMute = 2 # setting ID to mute sound
sLog = 3 # setting ID to enable the log
sCopy = 4 # setting ID to enable the auto copy
sAuthor = 5 # setting ID to show the tweet author
sBlacklist = 6 # setting ID to enable the blacklist
sDupe = 7 # setting ID to ignore duplicates
sPause = 8 # setting ID to pause the stream
settButton = [None]*settingCount # store the buttons used for the settings
settOn = [0]*settingCount # contain which languages to display
# others
logtext = {}
idregex = re.compile(u'([A-F0-9]{8}) :') # to parse the ID

# =============================================================================================
# twitter part
# =============================================================================================
class TwitterStreamListener(tweepy.StreamListener):
    def on_data(self, data): # when data is received
        if settOn[sPause] or not appRunning or streamKill: # if the app isn't running, nothing to do
            return True

        # process the tweet
        try:
            tweet = json.loads(data)
            if tweet['source'] != u"<a href=\"http://granbluefantasy.jp/\" rel=\"nofollow\">グランブルー ファンタジー</a>":
                return True # not a GBF tweet
            st = tweet['text'] # tweet content in string form, utf-8
            # blacklist check
            if settOn[sBlacklist] and tweet['user']['screen_name'] in blacklist:
                stats[6] = stats[6] + 1
                return True
            # search the ID in this string
            m = idregex.search(st)
            if not m:
                return True # not found, so we return
            tweetQueue.put([st, m, tweet['user']['screen_name']])
        except:
            pass
        return True

    def on_connect(self): # when the stream connects
        global twitterConnected
        if not twitterConnected:
            log("[System] Twitter stream connected")
        twitterConnected = True

    def on_disconnect(self): # when the stream disconnects
        global twitterConnected
        if twitterConnected:
            log("[System] Twitter stream disconnected")
        twitterConnected = False

    def on_exception(self, exception): # when a problem occurs
        global twitterConnected
        global watchdogKill
        if twitterConnected: # exception happened while being connected
            log("[Error] An exception occurred: " + str(exception), True)
            print(exception)
            twitterConnected = False
        else: # else, the keys are probably invalid
            log("[Error] Invalid twitter keys. Check them at https://developer.twitter.com/en/apps", True) 
            print("on_exception(): ", exception)
            watchdogKill = True # kill the watchdog
 
    def on_error(self, status): # for error stuff
        global twitterConnected
        global streamKill
        global watchdogKill
        global rateLimit
        if status == 420:
            log("[Error] Rate limited by twitter, restarting in 90 seconds...", True)
            twitterConnected = False
            rateLimit = True
            streamKill = True # kill the stream
        elif not twitterConnected:
            log("[Error] Invalid twitter keys. Check them at https://developer.twitter.com/en/apps", True)
            watchdogKill = True # kill the watchdog
            twitterConnected = False
        else:
            log("[Error] HTTP Error " + str(status) + ": check your internet connection or twitter server status", True)
            print("on_error(): error http ", status)
            twitterConnected = False
        return False # don't keep the stream alive

# =============================================================================================
# UI part
# =============================================================================================
class simpleui(Tk.Tk):
    def __init__(self, parent): # the UI is built here
        global freezeUI
        global logtext
        global queueframe
        global raidCount
        global queueButton
        global settButton
        global timeLabel
        global statusLabel
        global raidTab

        Tk.Tk.__init__(self,parent)
        self.parent = parent
        self.copying = []
        self.sounds = []
        self.tracking = []
        self.all = []
        self.settings = []
        self.custom = []

        self.iconbitmap('favicon.ico')
        # top part containing the raids
        # do nothing if the json failed to load
        if raidList:
            raidTab = ttk.Notebook(self)
            raidTab.grid(row=0, column=0, columnspan=15, sticky="we")
            statusLabel = Tk.Label(self, text="Offline", bg='#edc7c7') # for the offline/online text
            statusLabel.grid(row=0, column=14, sticky="ne")

            raidframe = []
            for i in range(0, len(tabData)):
                raidframe.append(Tk.Frame(raidTab, background=tabData[i][0]))
                raidTab.add(raidframe[i], text=tabData[i][1])

            if len(raidframe) < 3:
                raidTab.select(len(raidframe)-1)
            else:
                raidTab.select(0)

            for j in range(0, len(raidframe)-1):
                for i in range(0, tabData[j][2]):
                    # all the top stuff first
                    Tk.Label(raidframe[j], text='Raid', bg=raidframe[j]['bg']).grid(row=0, column=i*5) # raid text
                    trklabel = Tk.Label(raidframe[j], text='Show', bg=raidframe[j]['bg']) # show text
                    trklabel.grid(row=0, column=1+i*5)
                    cpylabel = Tk.Label(raidframe[j], text='Copy', bg=raidframe[j]['bg']) # auto copy text
                    cpylabel.grid(row=0, column=2+i*5)
                    sndlabel = Tk.Label(raidframe[j], text='Alert', bg=raidframe[j]['bg']) # alert text
                    sndlabel.grid(row=0, column=3+i*5)
                    Tk.Label(raidframe[j], text='All', bg=raidframe[j]['bg']).grid(row=0, column=4+i*5) # all text

            id = 0
            cf = 0
            limit = raidCount-customCount
            # buttons
            for i in range(id, limit):
                if(raidList[i][0] == "next"): # to go to the next page
                    newIntVar(self.tracking) # still create a spot in the arrays
                    newIntVar(self.copying)
                    newIntVar(self.sounds)
                    newIntVar(self.all)
                    if cf == len(raidframe)-2: # in case we reached max capacity, we continue
                        continue
                    id = i+1;
                    cf += 1
                    continue
                if(raidList[i][0] == "dummy"): # to make empty spaces on the UI
                    newIntVar(self.tracking) # still create a spot in the arrays
                    newIntVar(self.copying)
                    newIntVar(self.sounds)
                    newIntVar(self.all)
                    continue
                p = i - id # position relative
                # raid name
                Tk.Label(raidframe[cf], text=raidList[i][0], bg=raidframe[cf]['bg']).grid(row=1+(p//4)*5, column=(p%4)*5, stick=Tk.W)
                # show button
                Tk.Checkbutton(raidframe[cf], bg=raidframe[cf]['bg'], variable=newIntVar(self.tracking), command=lambda i=i: self.changeTrk(i)).grid(row=1+(p//4)*5, column=1+(p%4)*5)
                # auto copy button
                Tk.Checkbutton(raidframe[cf], bg=raidframe[cf]['bg'], variable=newIntVar(self.copying), command=lambda i=i: self.changeCpy(i)).grid(row=1+(p//4)*5, column=2+(p%4)*5)
                # alert button
                Tk.Checkbutton(raidframe[cf], bg=raidframe[cf]['bg'], variable=newIntVar(self.sounds), command=lambda i=i: self.changeSnd(i)).grid(row=1+(p//4)*5, column=3+(p%4)*5)
                # all button
                Tk.Checkbutton(raidframe[cf], bg=raidframe[cf]['bg'], variable=newIntVar(self.all), command=lambda i=i: self.changeAll(i)).grid(row=1+(p//4)*5, column=4+(p%4)*5)
                if p >= 23 or i == limit - 1:
                    if cf == len(raidframe)-2: # in case we reached max capacity, we continue
                        continue
                    id = i+1
                    cf += 1

            # custom tab
            framepos = len(raidframe)-1
            cframe = raidframe[framepos]
            for i in range(limit, limit+customCount):
                p = i - limit # position relative
                if p >= customCount:
                    break
                if p % 6 == 0:
                    # top stuff
                    Tk.Label(cframe, text='Raid', bg=cframe['bg']).grid(row=0, column=1+(p//6)*6) # raid text
                    trklabel = Tk.Label(cframe, text='Show', bg=cframe['bg']) # show text
                    trklabel.grid(row=0, column=2+(p//6)*6)
                    cpylabel = Tk.Label(cframe, text='Copy', bg=cframe['bg']) # auto copy text
                    cpylabel.grid(row=0, column=3+(p//6)*6)
                    sndlabel = Tk.Label(cframe, text='Alert', bg=cframe['bg']) # alert text
                    sndlabel.grid(row=0, column=4+(p//6)*6)
                    Tk.Label(cframe, text='All', bg=cframe['bg']).grid(row=0, column=5+(p//6)*6) # all text
                if(raidList[i][0] == "dummy" or raidList[i][0] == "next"): # to make empty spaces on the UI
                    newIntVar(self.tracking) # still create a spot in the arrays
                    newIntVar(self.copying)
                    newIntVar(self.sounds)
                    newIntVar(self.all)
                    continue
                Tk.Button(cframe , text="Edit ", command=lambda i=p: self.editCustom(i)).grid(row=1+(p%6), column=(p//6)*6, stick=Tk.W)
                # raid name
                self.custom.append(Tk.Label(cframe, text=raidList[i][0], bg=cframe['bg']))
                self.custom[p].grid(row=1+(p%6), column=1+(p//6)*6, stick=Tk.W)
                # show button
                Tk.Checkbutton(cframe, bg=cframe['bg'], variable=newIntVar(self.tracking), command=lambda i=i: self.changeTrk(i)).grid(row=1+(p%6), column=2+(p//6)*6, stick=Tk.W)
                    # auto copy button
                Tk.Checkbutton(cframe, bg=cframe['bg'], variable=newIntVar(self.copying), command=lambda i=i: self.changeCpy(i)).grid(row=1+(p%6), column=3+(p//6)*6, stick=Tk.W)
                # alert button
                Tk.Checkbutton(cframe, bg=cframe['bg'], variable=newIntVar(self.sounds), command=lambda i=i: self.changeSnd(i)).grid(row=1+(p%6), column=4+(p//6)*6, stick=Tk.W)
                # all button
                Tk.Checkbutton(cframe, bg=cframe['bg'], variable=newIntVar(self.all), command=lambda i=i: self.changeAll(i)).grid(row=1+(p%6), column=5+(p//6)*6, stick=Tk.W)

        # contain the bottom part
        n = ttk.Notebook(self)
        n.grid(row=2, column=0, columnspan=15, sticky="we")
        timeLabel = Tk.Label(self, text=strftime("%H:%M:%S"), bg=self['bg']) # clock
        timeLabel.grid(row=2, column=14, sticky="ne")
        logframe = Tk.Frame(n) # first page
        queueframe = ttk.Notebook(n) # second page, check createQueue()
        settframe = Tk.Frame(n, bg='#dfe5d7') # third page
        statframe = Tk.Frame(n, bg='#e5e0d7') # fourth page
        n.add(logframe, text='Log')
        n.add(queueframe, text='Queue')
        n.add(settframe, text='Settings')
        n.add(statframe, text='Statistics')

        # settings display
        for i in range(0, settingCount): # button creation loop
            Tk.Label(settframe, bg=settframe['bg'], text="[" + str(i+1) + "] " + settings[i]).grid(row=i%bottomHeight, column=(i//bottomHeight)*2, sticky="w") # name
            settButton[i] = Tk.Checkbutton(settframe, bg=settframe['bg'], variable=newIntVar(self.settings, settOn[i]), command=lambda i=i: self.changeSetting(i))
            settButton[i].grid(row=i%bottomHeight, column=1+(i//bottomHeight)*2) # button
        Tk.Button(settframe, text="Restart Stream", command=self.resetStream).grid(row=0, column=6, sticky="ews") # stream reset button
        Tk.Button(settframe, text="Reload Blacklist", command=self.reloadBlacklist).grid(row=1, column=6, sticky="ews") # reload blacklist button
        Tk.Button(settframe, text="Download link", command=self.openBrowser).grid(row=2, column=6, sticky="ews") # download link button
        Tk.Button(settframe, text="Queue Color", command=self.clickedColor).grid(row=0, column=7, sticky="ews") # clicked color button
        Tk.Button(settframe, text="Reset Color", command=self.resetColor).grid(row=1, column=7, sticky="ews") # clicked color button
        Tk.Button(settframe, text="Queue Size", command=self.changeSize).grid(row=2, column=7, sticky="ews") # clicked color button
        Tk.Label(settframe, text="Shortcut: Press the corresponding [Key]", bg=settframe['bg']).grid(row=3, column=6, columnspan=3, sticky="w")

        # log box
        scrollbar = Tk.Scrollbar(logframe) # the scroll bar
        scrollbar.pack(side=Tk.RIGHT, fill=Tk.Y)
        logtext = Tk.Text(logframe, state=Tk.DISABLED, yscrollcommand=scrollbar.set, height=6, bg='#f8f8f8') # the log box itself, with a height limit
        logtext.pack(fill=Tk.BOTH, expand=1, side=Tk.LEFT)
        scrollbar.config(command=logtext.yview)

        # stats
        # text stuff
        Tk.Label(statframe, bg=statframe['bg'], text="Execution Time:").grid(row=0, column=0, sticky="ws")
        Tk.Label(statframe, bg=statframe['bg'], text="Tweet count:").grid(row=1, column=0, sticky="ws")
        Tk.Label(statframe, bg=statframe['bg'], text="Tweet rate:").grid(row=2, column=0, sticky="ws")
        Tk.Label(statframe, bg=statframe['bg'], text="Average:").grid(row=3, column=0, sticky="ws")
        Tk.Label(statframe, bg=statframe['bg'], text="Auto copy:").grid(row=0, column=2, sticky="ws")
        Tk.Label(statframe, bg=statframe['bg'], text="Alert:").grid(row=1, column=2, sticky="ws")
        Tk.Label(statframe, bg=statframe['bg'], text="Show:").grid(row=2, column=2, sticky="ws")
        Tk.Label(statframe, bg=statframe['bg'], text="Last tweet:").grid(row=3, column=2, sticky="ws")
        Tk.Label(statframe, bg=statframe['bg'], text="Dupe count:").grid(row=0, column=4, sticky="ws")
        Tk.Label(statframe, bg=statframe['bg'], text="Blacklisted:").grid(row=1, column=4, sticky="ws")
        # labels which will be modified
        statLabel.append(Tk.Label(statframe, bg=statframe['bg'], text="0")) # exec time
        statLabel.append(Tk.Label(statframe, bg=statframe['bg'], text="0")) # count
        statLabel.append(Tk.Label(statframe, bg=statframe['bg'], text="0.0/s")) # rate
        statLabel.append(Tk.Label(statframe, bg=statframe['bg'], text="0.0 s")) # gape
        statLabel.append(Tk.Label(statframe, bg=statframe['bg'], text="0 (0.0%)")) # auto copy
        statLabel.append(Tk.Label(statframe, bg=statframe['bg'], text="0 (0.0%)")) # alert
        statLabel.append(Tk.Label(statframe, bg=statframe['bg'], text="0 (0.0%)")) # show
        statLabel.append(Tk.Label(statframe, bg=statframe['bg'], text="0.0 s")) # last tweet
        statLabel.append(Tk.Label(statframe, bg=statframe['bg'], text="0 (0.0%)")) # dupes
        statLabel.append(Tk.Label(statframe, bg=statframe['bg'], text="0")) # blacklisted
        # place them with a loop because I'm lazy to copy paste
        for i in range(0, len(statLabel)):
            statLabel[i].grid(row=i%4, column=1+(i//4)*2, sticky="ews")
        Tk.Button(statframe, text="Reset statistics", command=self.resetStat).grid(row=0, column=6, sticky="ews") # reset button

    def openBrowser(self):
        webbrowser.open('https://drive.google.com/file/d/0B9YhZA7dWJUsY1lKMXY4bV9nZUE/view?usp=sharing', new=2)

    def changeAll(self, i): # if all button is pressed
        if freezeUI: # do nothing
            return
        state = self.all[i].get()
        self.tracking[i].set(state)
        self.copying[i].set(state)
        self.sounds[i].set(state)
        trk[i] = self.tracking[i].get()
        cpyOn[i] = self.copying[i].get()
        sndOn[i] = self.sounds[i].get()
        if state:
            log("[System] Started showing, notifying and auto-copying " + raidList[i][0] + " tweets")
        else:
            log("[System] Stopped showing, notifying and auto-copying " + raidList[i][0] + " tweets")

    def changeTrk(self, i): # if show button is pressed
        global trk
        if freezeUI: # do nothing
            return
        trk[i] = self.tracking[i].get()
        if trk[i]:
            log("[System] Started showing " + raidList[i][0] + " tweets")
        else:
            log("[System] Stopped showing " + raidList[i][0] + " tweets")

    def changeCpy(self, i): # if copy button is pressed
        global cpyOn
        if freezeUI: # do nothing
            return
        cpyOn[i] = self.copying[i].get()
        if cpyOn[i]:
            log("[System] Started auto-copying " + raidList[i][0] + " tweets")
        else:
            log("[System] Stopped auto-copying " + raidList[i][0] + " tweets")

    def changeSnd(self, i): # if alert button is pressed
        global sndOn
        if freezeUI: # do nothing
            return
        sndOn[i] = self.sounds[i].get()
        if sndOn[i]:
            log("[System] Started notifying on " + raidList[i][0] + " tweets")
        else:
            log("[System] Stopped notifying on " + raidList[i][0] + " tweets")

    def changeSetting(self, i): # if setting button is pressed
        global settOn
        if freezeUI: # do nothing
            return
        settOn[i] = self.settings[i].get()
        if settOn[i]:
            log("[Setting] Enabled '" + settings[i] + "'", True)
        else:
            log("[Setting] Disabled '" + settings[i] + "'", True)

    def editCustom(self, i):
        global focused
        global freezeUI
        global settOn
        if freezeUI: # do nothing
            return
        focused = True # to disable the keyboard shortcuts
        tmp = settOn[sPause] # save the pause setting
        settOn[sPause] = True # pause the app
        id = raidCount-customCount+i
        v1 = simpledialog.askstring("Edit custom raid", "input a name", initialvalue=raidList[id][0]) # ask for user input
        if v1 == None: # if the user cancelled
            focused = False
            settOn[sPause] = tmp
            return # we return
        v2 = simpledialog.askstring("Edit custom raid", "input the japanese code", initialvalue=raidList[id][2])
        if v2 == None: # same thing
            focused = False
            settOn[sPause] = tmp
            return
        v3 = simpledialog.askstring("Edit custom raid", "input the english code", initialvalue=raidList[id][1])
        if v3 == None: # same thing
            focused = False
            settOn[sPause] = tmp
            return
        focused = False # re-enable keyboard shortcuts

        freezeUI = True # disable UI events (may not be needed anymore...)
        raidList[id] = [v1, v3, v2] # save the user inputs

        # update the text label
        if len(raidList[id][0]) > customSize: # change the label name
            self.custom[i].config(text=raidList[id][0][:(customSize-1)] + "...") # if the name is too long, cut the string a bit
        else:
            self.custom[i].config(text=raidList[id][0])
        freezeUI = False # re-enable UI events

        # log and end
        log("[System] " + raidList[id][0] + " saved in slot " + str(i+1)) # logging for the user to check any mistake
        log("code JP : " + raidList[id][2])
        log("code EN : " + raidList[id][1])
        log("The stream will now be restarted with the new codes")

        updateCustomRaids()
        self.resetStream(False) # force a stream reset to ensure the filter has the new strings
        settOn[sPause] = tmp # restore the pause setting

    def init(self): # initialize the text entries and settings
        global freezeUI
        if freezeUI: # do nothing
            return
        freezeUI = True
        for i in range(0, settingCount): # set the setting checkboxes
            self.settings[i].set(settOn[i])
        for i in range(0, customCount): # set the custom tab labels
            if len(raidList[raidCount-customCount+i][0]) > customSize:
                self.custom[i].config(text=raidList[raidCount-customCount+i][0][:(customSize-1)] + "...") # if the name is too long, cut the string a bit
            else:
                self.custom[i].config(text=raidList[raidCount-customCount+i][0])
        freezeUI = False

    def copyQueue(self, i):
        if freezeUI: # do nothing
            return
        queueMutex.acquire()
        if queueCode[i] != None and queueRaid[i] != None: # must check both in case the user press the button at the same time one of them change from None to a string
            pyperclip.copy(queueCode[i]) # put in the clipboard
            log("[System] " + queueRaid[i] + ": " + queueCode[i] + " set in the clipboard")
            queueClicked[i] = True # set to true because we clicked it
            queueButton[i].config(background=buttonColor[1]) # change the color right now (we can't wait for the next update)
        queueMutex.release()

    def resetStream(self, showMSG=True):
        global twitterConnected
        global streamKill
        if freezeUI: # do nothing
            return
        try:
            streamKill = True
            if showMSG:
                tkMessageBox.showinfo("Info", "Stream reset. Please wait for the reconnection.")
        except:
            pass

    def reloadBlacklist(self):
        loadBlacklist("blacklist.txt")
        messagebox.showinfo("Info", "'blacklist.txt' has been reloaded. " + str(len(blacklist)) + " entrie(s) found.")

    def clickedColor(self):
        if freezeUI: # do nothing
            return
        color = colorchooser.askcolor(color=buttonColor[1], title="Select the color")
        if color != (None, None):
            buttonColor[1] = color[1]

    def resetColor(self):
        if freezeUI: # do nothing
            return
        buttonColor[1] = "#A0A0A0"

    def changeSize(self):
        global futureQueueSize
        global focused
        if freezeUI: # do nothing
            return
        focused = True # to disable the keyboard shortcuts
        v1 = simpledialog.askstring("Edit queue size", "input a value (min: 1, max: 150)", initialvalue=futureQueueSize) # ask for user input
        if v1 == None: # if the user cancelled
            focused = False
            return # we return
        try:
            v2 = int(v1) # check for int
            if v2 <= 0 or v2 > 150: # if invalid value
                messagebox.showinfo("Error", "The value must be between 1 and 150 included")
                focused = False
                return # we return
            futureQueueSize = v2
            messagebox.showinfo("Info", "The size will change after a restart\nThe new size is " + str(futureQueueSize))
        except ValueError: # if not a number
            messagebox.showinfo("Error", "The value isn't an integer")
            focused = False
            return # we return
        focused = False # re-enable keyboard shortcuts

    def resetStat(self): # reset the stats (time and stored values)
        global startTime
        global stats
        if freezeUI: # do nothing
            return
        startTime = time.time()
        stats = [0]*statsCount
        stats[4] = -1

    def createQueue(self):
        global queueCode
        global queueRaid
        global queueButton
        global queueClicked
        global queueSize
        global futureQueueSize
        if queueSize <= 0 or queueSize > 150: # if invalid size, default is 30
            queueSize = 30
        futureQueueSize = queueSize
        queueCode = [None]*queueSize # set the arrays to the right size
        queueRaid = [None]*queueSize
        queueButton = [None]*queueSize
        queueClicked = [False]*queueSize

        q = []
        for i in range(0, ((queueSize-1) // queuePageSize)+1): # create the pages
            q.append(Tk.Frame(queueframe, bg='#e7e7f7'))
            queueframe.add(q[i], text='page ' + str(i+1))

        # create the buttons
        queueHeight = bottomHeight - 1
        for i in range(0, queueSize):
            page = i // queuePageSize
            it = i % queuePageSize
            Tk.Label(q[page], text=str(i+1)+":", bg=q[page]['bg']).grid(row=it%queueHeight, column=(it//queueHeight)*2)
            buttonframe = Tk.Frame(q[page], width=140, height=25, bg=q[page]['bg']) # using this "trick" to keep the button from changing size and position too much
            buttonframe.grid(row=it%queueHeight, column=(it//queueHeight)*2+1, sticky="ews")
            buttonframe.grid_propagate(False)
            queueButton[i] = Tk.Button(buttonframe , text="          empty          ", command=lambda i=i: self.copyQueue(i))
            queueButton[i].grid(row=0, column=0, sticky="ews")
            queueButton[i].config(background=buttonColor[0])

# =============================================================================================
# variable creation and append
# =============================================================================================
def newIntVar(array, init=0):
    var = Tk.IntVar(value=init) # create and initialize
    array.append(var) # append
    return var

# =============================================================================================
# button queue
# =============================================================================================
def pushQueue(name, code):
    global queueCode
    global queueRaid
    global queueUpdate
    global queueClicked
    # if app isn't running, stop
    if not appRunning:
        return
    # shift the queue content to make a space and insert
    queueMutex.acquire() # locked to make it thread safe
    queueCode = [code] + queueCode[0:-1]
    queueRaid = [name] + queueRaid[0:-1]
    queueClicked = [False] + queueClicked[0:-1]
    queueUpdate = True
    queueMutex.release()

# =============================================================================================
# stat update
# =============================================================================================
def updateStat(): # called in the main thread (because Tkinter isn't thread safe)
    sec = time.time() - startTime # elapsed time in second
    statLabel[0].config(text=str(datetime.timedelta(seconds=round(sec, 0)))) # elapsed time
    statLabel[1].config(text=str(stats[0])) # tweet count

    # if elapsed time > 0
    if sec > 0:
        rate = stats[0]/sec
    else:
        rate = 0
    statLabel[2].config(text=str(round(rate, 2)) + "/s") # tweet rate

    if rate > 0:
        gap = 1/rate # average gap between tweets
    else:
        gap = 0

    # time gap between tweets
    if gap > 86400:
        statLabel[3].config(text=str(round(gap/86400, 1)) + " d")
    elif gap > 3600:
        statLabel[3].config(text=str(round(gap/3600, 1)) + " h")
    elif gap > 60:
        statLabel[3].config(text=str(round(gap/60, 1)) + " m")
    else:
        statLabel[3].config(text=str(round(gap, 1)) + " s") # time gap between tweets

    if stats[0] > 0: # percent %
        statLabel[4].config(text=str(stats[1]) + " (" + str(round(100*stats[1]/stats[0], 2)) + "%)") # auto copy
        statLabel[5].config(text=str(stats[2]) + " (" + str(round(100*stats[2]/stats[0], 2)) + "%)") # alert
        statLabel[6].config(text=str(stats[3]) + " (" + str(round(100*stats[3]/stats[0], 2)) + "%)") # show
    else:
        statLabel[4].config(text=str(stats[1]) + " (0.0%)") # auto copy
        statLabel[5].config(text=str(stats[2]) + " (0.0%)") # alert
        statLabel[6].config(text=str(stats[3]) + " (0.0%)") # show

    statLabel[8].config(text=str(stats[5])) # auto copy
    statLabel[9].config(text=str(stats[6])) # blacklisted

    # elapsed time since last tweet
    if stats[4] == -1:
        elaps = 0
    else:
        elaps = sec - stats[4]
        if elaps < 0: # for threading issues
            elaps = 0
    if elaps > 86400:
        statLabel[7].config(text=str(round(elaps/86400, 1)) + " d")
    elif elaps > 3600:
        statLabel[7].config(text=str(round(elaps/3600, 1)) + " h")
    elif elaps > 60:
        statLabel[7].config(text=str(round(elaps/60, 1)) + " m")
    else:
        statLabel[7].config(text=str(round(elaps, 1)) + " s") # elapsed time since last tweet

    return

# =============================================================================================
# gui update
# =============================================================================================
def updateGui(): # called in the main thread (because Tkinter isn't thread safe)
    global queueButton
    global queueUpdate
    global logSize

    if not appRunning: # no update if the app isn't running
        return

    # queue update
    if queueUpdate: # check if we have an update
        queueMutex.acquire() # lock
        for i in range(0, queueSize): # update the UI buttons
            if queueCode[i] != None: queueButton[i].config(text=queueRaid[i] + ": " + queueCode[i])
            else: queueButton[i].config(text="          empty          ")
            if queueClicked[i]: queueButton[i].config(background=buttonColor[1])
            else: queueButton[i].config(background=buttonColor[0])
        queueUpdate = False
        queueMutex.release()

    # log update
    logMutex.acquire()
    if len(logStrings) > 0:
        logtext.configure(state="normal") # state set to normal to write in
        for i in range(0, len(logStrings)):
            logtext.insert(Tk.END, logStrings[i]+"\n")
            if logSize > logLimit: # one call = one line, so if the number of line reachs the limit...
                logtext.delete(1.0, 2.0) # delete the oldest line
            else: # else, increase
                logSize += 1
        logtext.configure(state="disabled") # back to read only
        logtext.yview(Tk.END) # to the end of the text
        del logStrings[:] # delete the stored lines
    logMutex.release()

    # others
    timeLabel.config(text=strftime("%H:%M:%S"))
    if twitterConnected:
        statusLabel.config(text="Online", background='#c7edcd')
    else:
        statusLabel.config(text="Offline", background='#edc7c7')

# =============================================================================================
# log
# =============================================================================================
def log(text, force=False):
    if not appRunning or (not force and not settOn[sLog]): # force set to true allows you to write in the log no matter what
        return
    logMutex.acquire()
    logStrings.append(text) # append to our list of line (see updateGui() for more)
    logMutex.release()

# =============================================================================================
# creating the twitter stream
# =============================================================================================
def twitter_stream(): 
    global stream
    log("[System] Connecting the twitter stream...")
    try: # tweepy stuff
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.secure = True
        auth.set_access_token(access_token, access_token_secret)
        api = tweepy.API(auth, retry_count=100, retry_delay=8, retry_errors=set([401, 404, 420, 500, 502, 503, 504]), wait_on_rate_limit=True, wait_on_rate_limit_notify=True)
        streamListener = TwitterStreamListener()
        stream = tweepy.Stream(auth=auth, listener=streamListener)
        stream.filter(track=searchStrings) # this thread will block here until an issue occur
    except:
        pass

# =============================================================================================
# tweet processing
# =============================================================================================
def process_tweet(): # process the queued tweets
    global lastCode
    global lastRaid
    global tweetCount
    global dupes
    while appRunning : # failsafe to avoid weird behaviors
        if tweetQueue.empty():
            time.sleep(0.010)
        else:
            if settOn[sPause] or not appRunning or streamKill: # if the app isn't running, we have nothing to do and the queue should be empty
                with tweetQueue.mutex: # empty the queue if the app is paused
                    tweetQueue.queue.clear() # clear is not thread safe so use the mutex
                continue # continue to loop

            tweet = tweetQueue.get() # get the tweet to process
            st = tweet[0] # string
            code = tweet[1].group(1) # retrieve the code
            if settOn[sDupe] and len(dupes) > 0: # check if it's a dupe (if the setting is enabled)
                try:
                    dupes.index(code)
                    stats[5] = stats[5] + 1
                    continue # it's a dupe
                except:
                    pass

            # language check
            isJp = True
            if not settOn[sJP]: # if japanese if disabled, we ignore
                raidNamePos = jpRaidNameMin - 1
            else:
                raidNamePos = st.find(u"参加者募集！\n") # search the I need backup! part
            if raidNamePos < jpRaidNameMin: # minimal position of the string
                # it's not a japanese tweet, so:
                if not settOn[sEN]: # if english if disabled, we return
                    continue
                isJp = False # means japanese not found, check english
                raidNamePos = st.find(u"I need backup!\n") # search the I need backup! part
                if raidNamePos < enRaidNameMin: # minimal position of the string
                    continue # not found, so we return
                else:
                    raidNamePos = raidNamePos + enRaidNameOffset # add "I need backup!\n" size
            else:
                raidNamePos = raidNamePos + jpRaidNameOffset # add "参加者募集！\n" size

            raidName = st[raidNamePos:].rsplit('\nhttp', 1)[0] # get the raid name (between the "I need backup" and the twitter image link)

            # raid name check
            try: # get the index in our array
                if isJp:
                    foe = jpDict[raidName]
                else:
                    foe = enDict[raidName]
            except:
                continue # not found ? go back and ignore this one

            if settOn[sPause] or not appRunning or streamKill: # check again if the app didn't stop in the meantime
                continue

            # acting accordingly to the buttons checked
            if (trk[foe] or sndOn[foe] or cpyOn[foe]): # if we are doing something...
                dupes.insert(0, code) # add to the dupe list
                if len(dupes) > 100: # limit the list to 100
                    dupes = dupes[:70] # remove the last 30
                if cpyOn[foe] and settOn[sCopy]:
                    pyperclip.copy(code) # copy in the clipboard first
                    stats[1] = stats[1] + 1 # copy stat
                if sndOn[foe] and not settOn[sMute]:
                    playsound() # then, play the sound
                    stats[2] = stats[2] + 1 # alert stat
                if trk[foe]: # finally, writing in the logbox
                    logstr = "[" + strftime("%H:%M:%S") + "]" # timestamp
                    logstr += " " + raidList[foe][0] + " : " + code # raid name and code
                    if (isJp): logstr += " (JP) " + st[:raidNamePos-jpRaidNameMin-jpRaidNameOffset] # language and comment
                    else: logstr += " (EN) " + st[:raidNamePos-enRaidNameMin-enRaidNameOffset]
                    if settOn[sAuthor]:
                        logstr += " [@" + tweet[2] + "]" # twitter id
                    log(logstr, True) # print in the logbox
                    stats[3] = stats[3] + 1 # show stat
                pushQueue(raidList[foe][0], code) # add to the queue
                stats[0] = stats[0] + 1 # tweet count stat
                stats[4] = round(time.time()-startTime, 0) # current time


# =============================================================================================
# watchdog
# =============================================================================================
def watchdog(): # restart the twitter thread and the tweet processing thread if something happens
    global tweetThread
    global twitterThread
    global streamKill
    global rateLimit
    global twitterConnected
    time.sleep(5)
    while appRunning : # failsafe to avoid weird behaviors
        time.sleep(0.5)
        if watchdogKill:
            return
        if not twitterThread.isAlive() or streamKill:
            del(twitterThread)
            twitterConnected = False
            twitterThread = threading.Thread(target=twitter_stream) # make a new thread to restart
            twitterThread.setDaemon(True)
            if rateLimit:
                time.sleep(30)
                log("[System] 60 seconds left")
                time.sleep(30)
                log("[System] 30 seconds left")
                time.sleep(25)
                rateLimit = False
            log("[System] Restarting the thread in 5 seconds")
            time.sleep(5) # waiting a bit to not overload twitter
            twitterThread.start()
            streamKill = False
        if not tweetThread.isAlive():
            del(tweetThread)
            tweetThread = threading.Thread(target=process_tweet) # make a new thread to restart
            tweetThread.setDaemon(True)
            tweetThread.start()

# =============================================================================================
# blacklist loading
# =============================================================================================
def loadBlacklist(filename):
    global blacklist
    try:
        blacklist = []
        f = open(filename, 'r')
        blacklist = f.readlines()
        blacklist = [x.strip() for x in blacklist]
    except IOError:
        f = open(filename, 'w') # create the file if it doesn't exist
    except:
        return
    f.close()

# =============================================================================================
# .cfg loading, saving and error processing
# =============================================================================================
def loadConfig(filename): # called once at the start
    global consumer_key
    global consumer_secret
    global access_token
    global access_token_secret
    global config
    global settOn
    global queueSize
    global raidList

    # default settings
    settOn[sJP] = 1 # japanese is enabled
    settOn[sEN] = 1 # english is enabled
    settOn[sLog] = 1 # log is enabled
    settOn[sCopy] = 1 # auto copy is enabled
    settOn[sBlacklist] = 1 # blacklist is enabled

    # load the .cfg with the twitter API keys
    config = configparser.ConfigParser()
    config.read(filename)
    if len(config) == 0 or 'Keys' not in config:
        log("[Error] " + filename + " is not found, an empty one will be created", True)
        try:
            config['Keys'] = {'consumer_key': '', 'consumer_secret': '', 'access_token_secret': '', 'access_token' : ''}
            with open('gbfraidcopier.cfg', 'w') as configfile:
                config.write(configfile)
        except:
            log("[Error] couldn't create " + filename, True)
            log("Get your personal keys at https://developer.twitter.com/en/apps", True)
            log("and fill in " + filename, True)
            log("Consult the README for more informations", True)
            return False

    # storing the keys
    try:
        consumer_key = config['Keys']['consumer_key']
        consumer_secret = config['Keys']['consumer_secret']
        access_token = config['Keys']['access_token']
        access_token_secret = config['Keys']['access_token_secret']
    except:
        log("[Error] your " + filename + " file is missing one or multiple keys", True)
        log("Get your personal keys at https://developer.twitter.com/en/apps", True)
        log("and fill in " + filename, True)
        log("Consult the README for more informations", True)
        return False

    # check if last used settings are here. if yes, read them
    if 'Settings' in config:
        settOn[sJP] = int(config['Settings']['japanese'])
        settOn[sEN] = int(config['Settings']['english'])
        settOn[sMute] = int(config['Settings']['mute'])
        settOn[sLog] = int(config['Settings']['log'])
        settOn[sCopy] = int(config['Settings']['copy'])
        settOn[sAuthor] = int(config['Settings']['author'])
        settOn[sBlacklist] = int(config['Settings']['blacklist'])
        settOn[sDupe] = int(config['Settings']['duplicate'])
        buttonColor[1] = config['Settings']['clickcolor']
        queueSize = int(config['Settings']['queuesize'])
        try:
            raidTab.select(int(config['Settings']['lasttab']))
        except:
            pass

    # custom user raids
    if 'Raids' in config:
        for i in range(0, customCount):
            try:
                raidList[raidCount-customCount+i][0] = base64.b64decode(config['Raids']['savedName' + str(i)]).decode('utf-8')
                raidList[raidCount-customCount+i][2] = base64.b64decode(config['Raids']['savedJP' + str(i)]).decode('utf-8')
                if raidList[raidCount-customCount+i][2] == "Lv100 ???":
                    raidList[raidCount-customCount+i][2] = ""
                raidList[raidCount-customCount+i][1] = base64.b64decode(config['Raids'][ 'savedEN' + str(i)]).decode('utf-8')
                if raidList[raidCount-customCount+i][1] == "Lvl 100 ???":
                    raidList[raidCount-customCount+i][1] = ""
            except:
                pass

    
    return True

def saveConfig(filename): # called when quitting
    # update the values
    # NOTE : pause setting isn't saved !
    config['Settings'] = {
        'japanese': str(settOn[sJP]),
        'english': str(settOn[sEN]),
        'mute': str(settOn[sMute]),
        'log': str(settOn[sLog]),
        'copy': str(settOn[sCopy]),
        'author': str(settOn[sAuthor]),
        'blacklist': str(settOn[sAuthor]),
        'duplicate': str(settOn[sDupe]),
        'clickcolor': str(buttonColor[1]),
        'queuesize': str(futureQueueSize),
        'lasttab':str( raidTabSaved),
        }

    if customCount:
        config['Raids'] = {}
    for i in range(0, customCount): # custom user raids
        config['Raids']['savedName' + str(i)] = base64.b64encode(raidList[raidCount-customCount+i][0].encode('utf-8')).decode('ascii') 
        config['Raids']['savedJP' + str(i)] = base64.b64encode(raidList[raidCount-customCount+i][2].encode('utf-8')).decode('ascii') 
        config['Raids']['savedEN' + str(i)] = base64.b64encode(raidList[raidCount-customCount+i][1].encode('utf-8')).decode('ascii') 
    # Writing our configuration file
    with open(filename, 'w') as configfile:
         config.write(configfile)

    return True

# =============================================================================================
# other functions
# =============================================================================================
def close(): # called by the app when closed
    global appRunning
    global raidTabSaved
    appRunning = False
    raidTabSaved = raidTab.index(raidTab.select())
    app.destroy()
    if cfgLoaded: # save the settings
        saveConfig('gbfraidcopier.cfg')

def updateCustomRaids():
    global searchStrings
    global enDict
    global jpDict
    warning = False
    # update the raid list
    searchStrings = []
    for k in raidList:
        if k[0] == "dummy" or k[0] == "next":
            continue
        if k[1] in searchStrings or k[2] in searchStrings:
            continue
        if k[1] != "":
            searchStrings.append(k[1])
        if k[2] != "":
            searchStrings.append(k[2])

    # update the dictionnaries
    enDict = {}
    jpDict = {}
    for i in range(0, len(raidList)):
        if raidList[i][0] == "dummy" or raidList[i][0] == "next":
            continue
        if raidList[i][1] == "" and raidList[i][2] == "":
            continue
        if raidList[i][1] in enDict:
            warning = True
        else:
            enDict[raidList[i][1]] = i
        if raidList[i][2] in jpDict:
            warning = True
        else:
            jpDict[raidList[i][2]] = i

    if warning:
        log("[Warning] Detected one or multiple duplicates of the same raid", True)
        log("These raids might not work, please avoid having multiple copies", True)
        log("of the same raid in your raid.json and/or your custom raid Tab", True)

def key(event): # key event for setting shorcuts
    if not appRunning or event.type != '2' or focused: # 2 is KeyPress
        return
    numKey = event.keycode - 49 # 49 is the 1 key
    if numKey < 0 or numKey >= settingCount:
        numKey = event.keycode - 97 # 97 is the 1 numpad key
    if numKey < 0 or numKey >= settingCount:
        return # not a number, so return
    settButton[numKey].toggle()
    app.changeSetting(numKey)

def jsonLoad(): # load the raid list and ui appearance
    global raidList
    global tabData
    global raidCount
    global trk
    global cpyOn
    global sndOn

    try: # open the fail and load the data
        with open('raid.json', encoding='utf-8') as f:
            raidData = json.load(f)
    except:
        return "[JSON Error] File missing or invalid\nPlease check if 'raid.json' is present beside this python script\nAlternatively, please reinstall"

    # various check of data integrity
    if not isinstance(raidData, list):
        return "[JSON Error] Dataset isn't a list"

    if len(raidData) != 2:
        return "[JSON Error] Invalid size of the main array"

    if not isinstance(raidData[0], list):
        return "[JSON Error] First dataset isn't a list"

    if not isinstance(raidData[1], list):
        return "[JSON Error] Second dataset isn't a list"

    if len(raidData[0]) == 0:
        return "[JSON Error] First array is empty"

    if len(raidData[1]) == 0:
        return "[JSON Error] Second array is empty"

    # add the custom raid list
    raidCount = len(raidData[0])
    for i in range(raidCount, raidCount+customCount):
        raidData[0].append([u"My Raid " + str(i-raidCount).zfill(2), u"", u""])

    # initialize some variables
    raidCount = len(raidData[0])
    trk = [0]*raidCount
    cpyOn = [0]*raidCount
    sndOn = [0]*raidCount

    # assign the data to variables with proper names
    raidList = raidData[0]
    tabData = raidData[1]

    return ""

# =============================================================================================
# entry point
# =============================================================================================
if __name__ == "__main__":
    # load the raid list
    logstr = jsonLoad() # return a non empty string if an error happens
    # create the UI
    app = simpleui(None)
    app.title('Raid ID copier - (You) edition - ' + revision)
    app.resizable(width=False, height=False) # not resizable
    app.protocol("WM_DELETE_WINDOW", close) # call close() if we close the window
    app.bind_all("<Key>", key)
    # load the twitter blacklist
    loadBlacklist("blacklist.txt")
    # load the .cfg and check for errors
    cfgLoaded = False
    if logstr == "": # don't load if we failed to load the json
        cfgLoaded = loadConfig('gbfraidcopier.cfg')
        app.createQueue() # called once after the .cfg loading
        app.init() # must be called once
    startTime = time.time()

    if logstr != "": # print the json error if any
        log(logstr, True)

    if cfgLoaded: # if the twitter keys are loaded
        updateCustomRaids()
        # messages to the user
        if not settOn[sLog]: log("[Info] Logs are disabled", True)
        if not settOn[sJP]: log("[Info] Japanese is disabled")
        if not settOn[sEN]: log("[Info] English is disabled")
        if not settOn[sCopy]: log("[Info] Auto Copy is disabled")
        if settOn[sMute]: log("[Info] Alerts are muted")
        if not settOn[sBlacklist]: log("[Info] Blacklist is disabled")
        # create the threads
        tweetThread = threading.Thread(target=process_tweet)
        twitterThread = threading.Thread(target=twitter_stream)
        watchdogThread = threading.Thread(target=watchdog)
        # daemon to kill them all at the end
        tweetThread.setDaemon(True)
        twitterThread.setDaemon(True)
        watchdogThread.setDaemon(True)
        # start
        tweetThread.start()
        twitterThread.start()
        watchdogThread.start()

    # main loop
    while appRunning:
        updateStat()
        updateGui()
        app.update()
        time.sleep(0.02)
    