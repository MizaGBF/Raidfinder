version = "2.8" # raidfinder version

#######################################################################
# import
import json
import queue
import tweepy
import pyperclip
import configparser
import threading
import datetime
import time
from time import strftime
import html
import re
import base64
import tkinter as Tk
import tkinter.ttk as ttk
from tkinter import messagebox, simpledialog
import webbrowser

#######################################################################
# sound
soundFile = None
try:
    import winsound # windows only
except ImportError: # if it fails
    import os
    def playsound():
        os.system('beep -f %s -l %s' % (200,100)) # frequency (Hz) and duration (ms)
else:
    # load the sound file
    try:
        with open('alert.wav','rb') as f: # open the file
            soundFile = f.read() # store in string format
        soundLoaded = True
    except IOError: # not working ? the file probably doesn't exist
        soundLoaded = False

    def playsound(): # run winsound.PlaySound() in a thread to not block (SND_ASYNC doesn't work when playing a sound from the memory)
        if soundLoaded:
            threading.Thread(target=winsound.PlaySound, args=(soundFile, winsound.SND_MEMORY)).start()

#######################################################################
# Main class and tweepy listener
#######################################################################
class Raidfinder(tweepy.StreamListener):
    def __init__(self):
        # class variables
        self.settings = {'jp':1, 'en':1, 'sound':1, 'copy':1, 'author':1, 'blacklist':1, 'dupe':1}
        self.tweetQueue = queue.Queue()
        self.listenerDaemon = None
        self.tweetDaemon = []
        self.maxTweetThread = 4 # control the number of tweet processing threads
        self.tweetLock = threading.Lock()
        self.running = True
        self.pause = False
        self.connected = False
        self.reconnect = True
        self.blacklist = []
        self.dupes = []
        self.idregex = re.compile('([A-F0-9]{8}) :')
        self.dupes = []
        self.raids = {}
        self.custom = []
        self.stats = {'runtime':None, 'tweet':0, 'all tweet':0, 'dupe':0, 'blacklist':0, 'last':None, 'last filter':None}
        self.time = time.time()
        self.elapsed = 0
        self.lasttab = 0

        # tweepy stuff
        self.keys = {'consumer_key': '', 'consumer_secret': '', 'access_token_secret': '', 'access_token' : ''}
        self.auth = None
        self.api = None
        self.stream = None

        # tweet streaming
        super().__init__()
        self.paused = False

        # START
        tmpLog = []
        self.configLoaded = self.loadConfig(tmpLog)
        self.UI = RaidfinderUI(self)
        for msg in tmpLog: self.UI.log(msg)
        self.runRaidfinder()

    def loadConfig(self, tmpLog): # call it once at the start
        # load the .cfg with the twitter API keys
        config = configparser.ConfigParser()
        config.read('gbfraidcopier.cfg')
        if len(config) == 0 or 'Keys' not in config: # create a file if empty
            try:
                config['Keys'] = self.keys
                with open('gbfraidcopier.cfg', 'w') as configfile:
                    config.write(configfile)
                tmpLog.append("[Info] 'gbfraidcopier.cfg' file has been created")
                tmpLog.append("Get your personal keys at https://developer.twitter.com/en/apps")
                tmpLog.append("and fill in 'gbfraidcopier.cfg'")
                tmpLog.append("Consult the README for more informations")
            except:
                tmpLog.append("[Error] Something went wrong, couldn't create 'gbfraidcopier.cfg'")
            return False

        # storing the keys
        try:
            self.keys = config['Keys']
        except:
            tmpLog.append("[Error] your 'gbfraidcopier.cfg' file is missing one or multiple twitter keys")
            tmpLog.append("Get your personal keys at https://developer.twitter.com/en/apps")
            tmpLog.append("and fill in 'gbfraidcopier.cfg'")
            tmpLog.append("Consult the README for more informations")
            return False

        # check if last used settings are here. if yes, read them
        if 'Settings' in config:
            try: self.settings['jp'] = int(config['Settings']['japanese'])
            except: pass
            try: self.settings['en'] = int(config['Settings']['english'])
            except: pass
            try: self.settings['sound'] = 1 - int(config['Settings']['mute'])
            except:
                try: self.settings['sound'] = int(config['Settings']['sound'])
                except: pass
            try: self.settings['copy'] = int(config['Settings']['copy'])
            except: pass
            try: self.settings['author'] = int(config['Settings']['author'])
            except: pass
            try: self.settings['blacklist'] = int(config['Settings']['blacklist'])
            except: pass
            try: self.settings['dupe'] = int(config['Settings']['duplicate'])
            except: pass
            try: self.lasttab = int(config['Settings']['lasttab'])
            except: pass
            try: self.maxTweetThread = int(config['Settings']['maxthread'])
            except: pass
            if self.maxTweetThread < 1: self.maxTweetThread = 1

        # custom user raids
        if 'Raids' in config:
            for i in range(0, 30):
                self.custom.append(["My Raid {}".format(i+1), "Lvl 100 ???", "Lv100 ???"])
                try:
                    self.custom[i][0] = base64.b64decode(config['Raids']['savedName' + str(i)]).decode('utf-8')
                    self.custom[i][1] = base64.b64decode(config['Raids']['savedEN' + str(i)]).decode('utf-8')
                    self.custom[i][2] = base64.b64decode(config['Raids']['savedJP' + str(i)]).decode('utf-8')
                except:
                    pass

        return True

    def saveConfig(self): # called when quitting
        # update the values
        # NOTE : pause setting isn't saved !
        config = configparser.ConfigParser()
        try: self.lasttab = self.UI.mainframes[0].index(self.UI.mainframes[0].select())
        except: self.lasttab = 0
        config['Settings'] = {
            'japanese': str(self.settings['jp']),
            'english': str(self.settings['en']),
            'sound': str(self.settings['sound']),
            'copy': str(self.settings['copy']),
            'author': str(self.settings['author']),
            'blacklist': str(self.settings['blacklist']),
            'duplicate': str(self.settings['dupe']),
            'lasttab':str(self.lasttab),
            'maxthread':str(self.maxTweetThread)
        }

        config['Keys'] = self.keys

        config['Raids'] = {}
        for i in range(0, 30): # custom user raids
            if i>= len(self.custom):
                config['Raids']['savedName' + str(i)] = base64.b64encode("My Raid {}".format(i+1).encode('utf-8')).decode('ascii') 
                config['Raids']['savedEN' + str(i)] = base64.b64encode("Lvl 100 ???".encode('utf-8')).decode('ascii') 
                config['Raids']['savedJP' + str(i)] = base64.b64encode("Lv100 ???".encode('utf-8')).decode('ascii') 
            else:
                config['Raids']['savedName' + str(i)] = base64.b64encode(self.custom[i][0].encode('utf-8')).decode('ascii') 
                config['Raids']['savedEN' + str(i)] = base64.b64encode(self.custom[i][1].encode('utf-8')).decode('ascii') 
                config['Raids']['savedJP' + str(i)] = base64.b64encode(self.custom[i][2].encode('utf-8')).decode('ascii') 
        # Writing our configuration file
        with open('gbfraidcopier.cfg', 'w') as configfile:
             config.write(configfile)

        return True

    def loadBlacklist(self): # call it once at the start
        try:
            f = open("blacklist.txt", 'r')
            bl = f.readlines()
            bl = [x.strip() for x in bl] # read and make a list
            self.blacklist = bl # everything is good, so update
        except IOError:
            f = open("blacklist.txt", 'w') # create the file if it doesn't exist
        except:
            return
        f.close()

    def loadRaids(self): # load the raid.json, return an empty string on success
        try: # open the fail and load the data
            with open('raid.json', encoding='utf-8') as f:
                raidData = json.load(f)
        except Exception as e:
            return "[JSON Error] Missing or invalid file\nPlease check if 'raid.json' is beside this python script\nAlternatively, please reinstall\n(Exception: {})".format(e)

        # build the raid dictionnary
        x = {}

        try:
            for p in raidData['pages']: # for each page
                for r in p['list']: # read this page raid list
                    if 'en' in r: # retrieve english code
                       if r['en'] not in x: x[r['en']] = []
                       x[r['en']].append(r.get('name', ''))
                    if 'jp' in r: # retrieve japanese code
                       if r['jp'] not in x: x[r['jp']] = []
                       x[r['jp']].append(r.get('name', ''))
            for r in self.custom: # for each custom raid
                if r[1] not in x: x[r[1]] = [] # retrieve english code
                x[r[1]].append(r[0])
                if r[2] not in x: x[r[2]] = [] # retrieve japanese code
                x[r[2]].append(r[0])
            self.raids = x # overwrite our dictionnary with the new one
            self.UI.refreshRaids(raidData, self.custom) # update the UI
        except Exception as e:
            return "[JSON Error] Invalid file\n(Exception: {})".format(e)

        return ""

    def on_data(self, data): # when twitter data is received
        if self.paused or not self.running: # if the app isn't running, nothing to do
            return True
        self.tweetQueue.put(data) # queue the data
        return True

    def on_connect(self): # when the twitter stream connects
        if not self.connected:
            self.UI.log("[System] Twitter stream connected")
        self.connected = True

    def on_disconnect(self): # when the twitter stream disconnects
        if self.connected:
            self.UI.log("[System] Twitter stream disconnected")
        self.connected = False

    def on_exception(self, exception): # when a problem occurs
        print("on_exception():", exception)
        if str(exception).find("('Connection broken: IncompleteRead(0 bytes read)', IncompleteRead(0 bytes read))") != -1:
            return True
        elif self.connected: # exception happened while being connected
            self.UI.log("[Error] An exception occurred: {}".format(exception))
            self.connected = False
        else: # else, unknown error
            self.UI.log("[Error] Twitter keys might be invalid or your Internet is down.") 
            self.UI.log("Exception: {}".format(exception)) 
            self.connected = False
            self.reconnect = False
        return False
 
    def on_error(self, status): # for error stuff
        print("on_error():", status)
        if status == 420:
            self.UI.log("[Error] Rate limited by twitter, restarting might be needed")
            self.connected = False
        elif status >= 500 and status < 600:
            self.UI.log("[Error] HTTP Error {}: Server error, twitter might be overloaded".format(status))
            self.connected = False
        elif not self.connected:
            self.UI.log("[Error] Invalid twitter keys. Check them at https://developer.twitter.com/en/apps")
            self.connected = False
            self.reconnect = False
        else:
            self.UI.log("[Error] HTTP Error {}: Check your internet connection or twitter server status".format(status))
            self.connected = False
        return False

    def runRaidfinder(self): # MAIN FUNCTION
        # init
        err = self.loadRaids() # load the raid list
        if err != "":
            self.UI.log(err)
        self.loadBlacklist() # load blacklist.txt
        if self.configLoaded: # don't bother starting the threads if our config file didn't load
            try:
                # twitter authentification
                self.auth = tweepy.OAuthHandler(self.keys['consumer_key'], self.keys['consumer_secret'])
                self.auth.secure = True
                self.auth.set_access_token(self.keys['access_token'], self.keys['access_token_secret'])
                self.api = tweepy.API(self.auth, retry_count=100, retry_delay=8, retry_errors=set([401, 404, 420, 500, 502, 503, 504]), wait_on_rate_limit=True, wait_on_rate_limit_notify=True)
                # prepare and start the threads
                for i in range(0, self.maxTweetThread): # process the tweets
                    self.tweetDaemon.append(threading.Thread(target=self.processTweet, args=[i]))
                    self.tweetDaemon[-1].setDaemon(True)
                    self.tweetDaemon[-1].start()

                self.listenerDaemon = threading.Thread(target=self.runDaemon) # start the twitter listener
                self.listenerDaemon.setDaemon(True)
                self.listenerDaemon.start()
            except Exception as e:
                self.UI.log("[Error] Failed to start the raidfinder, check your twitter keys.")
                self.UI.log("Check them at https://developer.twitter.com/en/apps")
                self.UI.log("Exception: {}".format(e))

        # main loop
        while self.running:
            self.elapsed = time.time() - self.time # measure elapsed time
            self.time = time.time()
            if not self.paused:
                if self.stats['runtime'] is None: self.stats['runtime'] = self.elapsed
                else: self.stats['runtime'] += self.elapsed
            self.UI.updateAll()
            time.sleep(0.02)

    def runDaemon(self): # tweepy listener thread
        self.UI.log("[System] Connecting to Twitter...")
        stream = tweepy.Stream(auth=self.auth, listener=self)
        while self.running:
            try: # starting tweepy
                stream.filter(track=["参加者募集！\n", u"I need backup!\n"]) # this thread will block here until an issue occur
            except:
                pass
            if not self.running or not self.reconnect:
                return
            elif self.connected:
                continue
            else:
                self.UI.log("[System] Attempting a new connection in 90 seconds")
                time.sleep(90)
                self.UI.log("[System] Connecting to Twitter...")
                stream = tweepy.Stream(auth=self.auth, listener=self)

    def processTweet(self, i = -1): # tweet processing thread (can be run in parallel)
        while self.running:
            try:
                if i >= len(self.tweetDaemon):
                    return
                try: data = self.tweetQueue.get(block=True, timeout=1) # get the next tweet data
                except:
                    time.sleep(0.01)
                    continue
                if self.paused or not self.running: # if the app isn't running, we have nothing to do and we don't care about the tweets
                    if i <= 0: # only the main thread clears the queue while the app is paused
                        while not self.tweetQueue.empty() and (self.paused or not self.running): # empty the queue (because we won't process it)
                            try: self.tweetQueue.get(block=True, timeout=1)
                            except: pass
                    else:
                        time.sleep(0.01) # else sleep during 10 ms
                    continue # continue to loop
                tweet = json.loads(data) # convert the json
                if tweet['source'] != u"<a href=\"http://granbluefantasy.jp/\" rel=\"nofollow\">グランブルー ファンタジー</a>":
                    continue # not a GBF tweet, we skip
                # blacklist check
                if self.settings['blacklist'] and tweet['user']['screen_name'] in self.blacklist:
                    self.tweetLock.acquire()
                    self.stats['blacklist'] += 1
                    self.tweetLock.release()
                    continue # author is blacklisted, we skip
                st = html.unescape(tweet['text']) # tweet content
                # search the ID in this string
                m = self.idregex.search(st)
                if not m:
                    continue # not found, we skip
                code = m.group(1) # get the code

                p = st.rfind("参加者募集！\n") # search the japanese 'I need backup' first (because it's most likely to be a japanese tweet
                lg = '(JP)'
                mp = 0 # minimal position of I need backup + raidname (used later to retrive the author comment if any)
                if p != -1 and p >= 15: # check the minimal position for jp
                    if not self.settings['jp']: continue
                    p += 7 # valid, add the size of JP I need backup. p nows points to the raid name
                    mp = 22
                else:
                    p = st.rfind("I need backup!\n") # same thing but for english
                    if p < 20 or not self.settings['en']: continue # english isn't valid, so is JP, we skip
                    p += 15 # size of I need backup
                    mp = 35
                    lg = '(EN)'

                raidName = st[p:].rsplit('\nhttp', 1)[0] # retrieve the raid name
                self.tweetLock.acquire()
                self.stats['all tweet'] += 1
                self.stats['last'] = time.time()
                self.tweetLock.release()
                for r in self.raids.get(raidName, []): # get the corresponding raids
                    if r in self.UI.readonly and self.UI.readonly[r]: # check if enabled on the UI
                        self.tweetLock.acquire()
                        self.stats['tweet'] += 1
                        if self.settings['dupe'] and code in self.dupes:
                            self.stats['dupe'] += 1
                            self.tweetLock.release()
                            break
                        self.tweetLock.release()
                        if self.settings['copy']: pyperclip.copy(code) # copy if enabled (note: is this thread safe?)
                        if self.settings['sound']: playsound() # play a sound if enabled
                        comment = "" # get the author comment, ignoring out of range characters
                        for c in range(0, p-mp):
                            if ord(st[c]) in range(65536):
                                comment += st[c]
                        # write to the log
                        self.UI.log('[{}] {} : {} {} [@{}] {}'.format(strftime("%H:%M:%S"), r, code, lg, tweet['user']['screen_name'], comment))
                        self.tweetLock.acquire()
                        self.stats['last filter'] = time.time()
                        self.dupes.append(code)
                        if len(self.dupes) > 150: self.dupes = self.dupes[50:]
                        self.tweetLock.release()
                        break
            except Exception as e:
                if i == -1: print(e)
                else: print('thread', i, ':', e)

#######################################################################
# UI class
#######################################################################
class RaidfinderUI(Tk.Tk):
    def __init__(self, raidfinder): # the UI is built here
        Tk.Tk.__init__(self,None)
        # variables
        self.parent = None
        self.raidfinder = raidfinder # Raidfinder class
        self.tracking = {}
        self.readonly = {}
        self.mainsett = []
        self.advsett = []
        self.logQueue = queue.Queue()
        self.logSize = 0
        self.iconbitmap('favicon.ico')
        self.inputting = False

        # building the UI
        ## raid part
        self.mainframes = []
        self.mainframes.append(ttk.Notebook(self))
        self.mainframes[-1].grid(row=0, column=0, columnspan=10, sticky="we")
        self.raids = [] # empty for now
        self.raidchilds = []
        self.custom = []

        ## main settings
        self.mainframes.append(ttk.Frame(self))
        self.mainframes[-1].grid(row=1, column=0, columnspan=8, sticky="we")
        self.mainsett_b = []
        self.mainsett_tag = ["Pause","Japanese","English","Sound","Auto Copy"]
        convert = {"Pause":"", "Japanese":"jp", "English":"en", "Sound":"sound", "Auto Copy":"copy"}
        for x in self.mainsett_tag: # adding the buttons
            self.mainsett_b.append(Tk.Checkbutton(self.mainframes[-1], text="[{}] {}".format(len(self.mainsett_b), x), variable=self.newIntVar(self.mainsett, self.raidfinder.settings.get(convert[x], 0)), command=lambda n=len(self.mainsett_b): self.toggleMainSetting(n)))
            self.mainsett_b[-1].grid(row=0, column=len(self.mainsett_b)-1)

        ## bottomn (log / advanced setting / stats)
        self.mainframes.append(ttk.Notebook(self))
        self.mainframes[-1].grid(row=2, column=0, columnspan=10, sticky="we")
        self.subtabs = []
        ### log
        self.subtabs.append(ttk.Frame(self.mainframes[-1]))
        self.mainframes[-1].add(self.subtabs[-1], text="Log")
        scrollbar = Tk.Scrollbar(self.subtabs[-1]) # the scroll bar
        scrollbar.pack(side=Tk.RIGHT, fill=Tk.Y)
        scrollbar.pack(side=Tk.RIGHT, fill=Tk.Y)
        self.logtext = Tk.Text(self.subtabs[-1], state=Tk.DISABLED, yscrollcommand=scrollbar.set, height=8, bg='#f8f8f8') # the log box itself, with a height limit
        self.logtext.pack(fill=Tk.BOTH, expand=1, side=Tk.LEFT)
        scrollbar.config(command=self.logtext.yview)
        ### advanced settings
        self.subtabs.append(Tk.Frame(self.mainframes[-1], bg='#dfe5d7'))
        self.mainframes[-1].add(self.subtabs[-1], text="Advanced")
        Tk.Checkbutton(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text="Ignore duplicate codes", variable=self.newIntVar(self.advsett, self.raidfinder.settings['dupe']), command=lambda n=0: self.toggleAdvSetting(n)).grid(row=0, column=0, stick=Tk.W)
        Tk.Checkbutton(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text="Show twitter handle", variable=self.newIntVar(self.advsett, self.raidfinder.settings['author']), command=lambda n=1: self.toggleAdvSetting(n)).grid(row=1, column=0, stick=Tk.W)
        Tk.Checkbutton(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text="Enable Author Blacklist", variable=self.newIntVar(self.advsett, self.raidfinder.settings['blacklist']), command=lambda n=2: self.toggleAdvSetting(n)).grid(row=2, column=0, stick=Tk.W)

        Tk.Button(self.subtabs[-1], text="Reload Blacklist", command=self.reloadBlacklist).grid(row=0, column=1, sticky="ews") # reload blacklist button
        Tk.Button(self.subtabs[-1], text="Reload Raid List", command=self.reloadRaidList).grid(row=1, column=1, sticky="ews") # reload raid list button
        Tk.Button(self.subtabs[-1], text="Latest Version", command=lambda n=0 : self.openBrowser(n)).grid(row=0, column=2, sticky="ews") # download link button
        Tk.Button(self.subtabs[-1], text="Latest raid.json", command=lambda n=1 : self.openBrowser(n)).grid(row=1, column=2, sticky="ews") # download link button

        # thread count spinbox
        Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text="Tweet processing threads").grid(row=0, column=3, sticky="ews")
        self.threadSpinBox = Tk.Spinbox(self.subtabs[-1], from_=1, to=50, textvariable=Tk.StringVar(value=str(self.raidfinder.maxTweetThread)), validate='all', validatecommand=(self.subtabs[-1].register(self.updateTweetThreadCount), '%P'))
        self.threadSpinBox.grid(row=1, column=3, sticky="ews")
        self.threadSpinBox.bind("<FocusIn>", self.focusin)
        self.threadSpinBox.bind("<FocusOut>", self.focusout)

        ### stats
        # mostly text labels, you can skip over it
        self.subtabs.append(Tk.Frame(self.mainframes[-1], bg='#e5e0d7'))
        self.mainframes[-1].add(self.subtabs[-1], text="Statistics")
        self.stats = []
        Tk.Button(self.subtabs[-1], text="Reset", command=self.resetStats).grid(row=4, column=0, sticky="ews") # reset button
        Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text="Connection Time:").grid(row=0, column=0, sticky="ws")
        self.stats.append(Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=""))
        self.stats[-1].grid(row=0, column=1, sticky="nw")
        Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text="Received tweets:").grid(row=1, column=0, sticky="ws")
        self.stats.append(Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=""))
        self.stats[-1].grid(row=1, column=1, sticky="nw")
        Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text="Filtered tweets:").grid(row=2, column=0, sticky="ws")
        self.stats.append(Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=""))
        self.stats[-1].grid(row=2, column=1, sticky="nw")
        Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text="Filtered/Received:").grid(row=3, column=0, sticky="ws")
        self.stats.append(Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=""))
        self.stats[-1].grid(row=3, column=1, sticky="nw")
        Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text="Received rate:").grid(row=1, column=2, sticky="ws")
        self.stats.append(Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=""))
        self.stats[-1].grid(row=1, column=3, sticky="nw")
        Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text="Filtered rate:").grid(row=2, column=2, sticky="ws")
        self.stats.append(Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=""))
        self.stats[-1].grid(row=2, column=3, sticky="nw")
        Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text="Blacklisted:").grid(row=0, column=2, sticky="ws")
        self.stats.append(Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=""))
        self.stats[-1].grid(row=0, column=3, sticky="nw")
        Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text="Dupes:").grid(row=0, column=4, sticky="ws")
        self.stats.append(Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=""))
        self.stats[-1].grid(row=0, column=5, sticky="nw")
        Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text="Last Received:").grid(row=1, column=4, sticky="ws")
        self.stats.append(Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=""))
        self.stats[-1].grid(row=1, column=5, sticky="nw")
        Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text="Last Filtered:").grid(row=2, column=4, sticky="ws")
        self.stats.append(Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=""))
        self.stats[-1].grid(row=2, column=5, sticky="nw")

        # others
        self.statusLabel = Tk.Label(self, text="Offline", bg='#edc7c7') # for the offline/online text
        self.statusLabel.grid(row=0, column=9, sticky="ne")
        self.timeLabel = Tk.Label(self, text="") # for the current time
        self.timeLabel.grid(row=1, column=9, sticky="ne")

        # make the window and bind the keyboard
        self.title('Raid ID copier v{}'.format(version))
        self.resizable(width=False, height=False) # not resizable
        self.protocol("WM_DELETE_WINDOW", self.close) # call close() if we close the window
        self.bind_all("<Key>", self.key)

    def newTrackingVar(self, key): # used by raid checkboxes
        if key not in self.tracking:
             self.tracking[key] = Tk.IntVar(value=0)
             self.readonly[key] = 0
        return self.tracking[key]

    def newIntVar(self, array, init=0): # used by setting checkboxes
        array.append(Tk.IntVar(value=init))
        return array[-1]

    def refreshRaids(self, raids, custom):
        # clean stuff
        for c in self.raidchilds:
             c.destroy()
        for p in self.custom:
             p.destroy()
        for p in self.raids:
             p.destroy()
        self.tracking = {}
        # build the raid UI
        try:
            self.raids = []
            for p in raids['pages']: # for each page
                self.raids.append(Tk.Frame(self.mainframes[0], background=p.get('color', ''))) # make a tab
                self.mainframes[0].add(self.raids[-1], text=p.get('name', ''))
                for r in p.get('list', []): # and add a checkbox for each raid
                    self.raidchilds.append(Tk.Checkbutton(self.raids[-1], bg=p.get('color', ''), text=r.get('name', ''), variable=self.newTrackingVar(r.get('name', '')), command=lambda r=r.get('name', ''): self.toggleRaid(r)))
                    self.raidchilds[-1].grid(row=r.get('posY', 0), column=r.get('posX', 0), stick=Tk.W)
            # add the custom tab
            self.raids.append(Tk.Frame(self.mainframes[0], background=raids['custom color']))
            self.mainframes[0].add(self.raids[-1], text="Custom")
            self.custom = []
            for i in range(0, len(custom)): # same thing, with an extra Edit button
                self.raidchilds.append(Tk.Button(self.raids[-1], text="Edit", command=lambda i=i: self.editCustom(i)))
                self.raidchilds[-1].grid(row=i%6, column=(i//6)*2, sticky='ews')
                self.custom.append(Tk.Checkbutton(self.raids[-1], bg=raids['custom color'], text=custom[i][0], variable=self.newTrackingVar(custom[i][0]), command=lambda r=custom[i][0]: self.toggleRaid(r)))
                self.custom[-1].grid(row=i%6, column=1+(i//6)*2, stick=Tk.W)
            # select the last tab used
            self.mainframes[0].select(self.raidfinder.lasttab)
        except Exception as e:
            self.log("[Error] Something went wrong while building the raid UI")
            self.log("Exception: {}".format(e))

    def toggleRaid(self, r): # called when un/checking a raid
        state = self.tracking[r].get()
        self.readonly[r] = state
        if state: self.log('[Raid] Now tracking {}'.format(r))
        else: self.log('[Raid] Stopped tracking of {}'.format(r))

    def toggleMainSetting(self, n): # called when un/checking a main setting
        state = self.mainsett[n].get()
        if n == 0: self.raidfinder.paused = state
        elif n == 1: self.raidfinder.settings['jp'] = state
        elif n == 2: self.raidfinder.settings['en'] = state
        elif n == 3: self.raidfinder.settings['sound'] = state
        elif n == 4: self.raidfinder.settings['copy'] = state
        if state: self.log("[Settings] '{}' is enabled".format(self.mainsett_tag[n]))
        else:  self.log("[Settings] '{}' is disabled".format(self.mainsett_tag[n]))

    def toggleAdvSetting(self, n): # called when un/checking an advanced setting
        state = self.subsett[n].get()
        if n == 0: self.raidfinder.settings['dupe'] = state
        elif n == 1: self.raidfinder.settings['author'] = state
        elif n == 2: self.raidfinder.settings['blacklist'] = state

    def editCustom(self, i): # called when editing a custom raid
        self.inputting = True # to disable the keyboard shortcuts
        tmp = self.raidfinder.paused # save the pause setting
        self.raidfinder.paused = True # pause the app
        customEntry = self.raidfinder.custom[i]
        v1 = simpledialog.askstring("Edit custom raid", "input a name", initialvalue=customEntry[0]) # ask for user input
        if v1 == None: # if the user cancelled
            self.inputting = False
            self.raidfinder.paused = tmp
            return # we return
        v2 = simpledialog.askstring("Edit custom raid", "input the english code", initialvalue=customEntry[1])
        if v2 == None: # same thing
            self.inputting = False
            self.raidfinder.paused = tmp
            return
        v3 = simpledialog.askstring("Edit custom raid", "input the japanese code", initialvalue=customEntry[2])
        if v3 == None: # same thing
            self.inputting = False
            self.raidfinder.paused = tmp
            return
        self.inputting = False # re-enable keyboard shortcuts

        self.raidfinder.custom[i] = [v1, v2, v3] # save the user inputs

        # reload list
        self.reloadRaidList(False)

        # log and end
        self.log("[System] {} saved in slot {}".format(v1, i+1)) # logging for the user to check any mistake
        self.log("code EN : {}".format(v2))
        self.log("code JP : {}".format(v3))

        self.raidfinder.paused = tmp # restore the pause setting

    def key(self, event): # key event for setting shortcuts
        if not self.raidfinder.running or event.type != '2' or self.inputting: # 2 is KeyPress
            return
        numKey = event.keycode - 48 # 48 is the 0 key
        if numKey < 0 or numKey > 4:
            numKey = event.keycode - 96 # 96 is the 0 numpad key
        if numKey < 0 or numKey > 4:
            return # not a number, so return
        self.mainsett_b[numKey].toggle() # toggle the checkbox
        self.toggleMainSetting(numKey) # call the event

    def close(self): # called by the app when closed
        if self.raidfinder.configLoaded:
            self.raidfinder.saveConfig() # update config file
        self.raidfinder.running = False
        self.destroy() # destroy the window

    def log(self, msg):
        self.logQueue.put(msg) # add a message to the log queue

    def reloadBlacklist(self): # reload the blacklist
        self.raidfinder.loadBlacklist()
        messagebox.showinfo("Info", "'blacklist.txt' has been reloaded.\n{} entrie(s) found.".format(len(self.raidfinder.blacklist)))

    def reloadRaidList(self, prompt = True): # reload the raid list
        self.raidfinder.lasttab = self.mainframes[0].index(self.mainframes[0].select()) # memorize last used tab
        err = self.raidfinder.loadRaids() # reload the list
        self.log("[System] Raid list have been reloaded")
        if prompt:
            if err == "":
                messagebox.showinfo("Info", "'raid.json' has been reloaded.\n{} code(s) found.".format(len(self.raidfinder.raids)))
            else:
                messagebox.showinfo("Error", "Failed to reload 'raid.json'\Exception: {}".format(err))

    def updateTweetThreadCount(self, entry):
        try: # validate the spinbox value
            n = int(entry)
            valid = n in range(1, 50)
        except ValueError:
            valid = False
        if valid: # update the threads
            self.raidfinder.maxTweetThread = n
            while n < len(self.raidfinder.tweetDaemon):
                self.raidfinder.tweetDaemon.pop()
            while n > len(self.raidfinder.tweetDaemon):
                self.raidfinder.tweetDaemon.append(threading.Thread(target=self.raidfinder.processTweet, args=[len(self.raidfinder.tweetDaemon)]))
                self.raidfinder.tweetDaemon[-1].setDaemon(True)
                self.raidfinder.tweetDaemon[-1].start()
        return valid

    def focusin(self, event): # event for managing a widget focus
        self.inputting = True

    def focusout(self, event): # event for managing a widget focus
        self.inputting = False

    def resetStats(self): # simply reset the stats
        self.raidfinder.stats = {'runtime':None, 'tweet':0, 'all tweet':0, 'dupe':0, 'blacklist':0, 'last':None, 'last filter':None}

    def openBrowser(self, n): # open the user web browser
        if n == 0: webbrowser.open('https://drive.google.com/file/d/0B9YhZA7dWJUsY1lKMXY4bV9nZUE/view?usp=sharing', new=2)
        elif n == 1: webbrowser.open('https://drive.google.com/file/d/1mq0zkMwqf6Uvem12gdoUIvSJhC_u7jDT/view?usp=sharing', new=2)

    def updateAll(self): # update the UI
        # update the log
        if not self.logQueue.empty():
            self.logtext.configure(state="normal")
            while not self.logQueue.empty():
                self.logtext.insert(Tk.END, self.logQueue.get()+"\n")
                if self.logSize >= 200: self.logtext.delete(1.0, 2.0)
                else: self.logSize += 1
            self.logtext.configure(state="disabled") # back to read only
            self.logtext.yview(Tk.END) # to the end of the text

        # update the stats
        if self.raidfinder.stats['runtime'] is not None:
            self.stats[0].config(text="{}".format(datetime.timedelta(seconds=round(self.raidfinder.stats['runtime'], 0))))
        else:
            self.stats[0].config(text="0:00:00")
        self.stats[1].config(text="{}".format(self.raidfinder.stats['all tweet']))
        self.stats[2].config(text="{}".format(self.raidfinder.stats['tweet']))
        if self.raidfinder.stats['all tweet'] == 0: self.stats[3].config(text="0%")
        else: self.stats[3].config(text="{:.2f}%".format(100*self.raidfinder.stats['tweet']/self.raidfinder.stats['all tweet']))
        if self.raidfinder.stats['runtime'] > 0: self.stats[4].config(text="{:.2f}/s".format(self.raidfinder.stats['all tweet']/self.raidfinder.stats['runtime']))
        else: self.stats[4].config(text="0/s")
        if self.raidfinder.stats['runtime'] > 0: self.stats[5].config(text="{:.2f}/s".format(self.raidfinder.stats['tweet']/self.raidfinder.stats['runtime']))
        else: self.stats[5].config(text="0/s")
        self.stats[6].config(text="{}".format(self.raidfinder.stats['blacklist']))
        self.stats[7].config(text="{}".format(self.raidfinder.stats['dupe']))
        if self.raidfinder.stats['last'] is not None:
            self.stats[8].config(text="{:.2f}s".format(time.time() - self.raidfinder.stats['last']))
        else: 
            self.stats[8].config(text="0.00s")
        if self.raidfinder.stats['last filter'] is not None:
            self.stats[9].config(text="{:.2f}s".format(time.time() - self.raidfinder.stats['last filter']))
        else: 
            self.stats[9].config(text="0.00s")
        
        # update the time and online indicator
        self.timeLabel.config(text=strftime("%H:%M:%S"))
        if self.raidfinder.connected: self.statusLabel.config(text="Online", background='#c7edcd')
        else: self.statusLabel.config(text="Offline", background='#edc7c7')

        # update tkinter
        self.update()

# entry point
Raidfinder()