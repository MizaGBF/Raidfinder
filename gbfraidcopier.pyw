version = "2.44" # raidfinder version

#######################################################################
# import
import json
import queue
import configparser
import threading
import datetime
import time
from time import strftime
import html
import re
import base64
import platform
import subprocess
import os
import sys
import tkinter as Tk
import tkinter.ttk as ttk
from tkinter import messagebox, simpledialog
import webbrowser
import traceback

if __name__ == "__main__": # module check
    try: # try to import
        import tweepy
        import pyperclip
        if tweepy.__version__ != "4.2.0" or pyperclip.__version__ != "1.8.2": # version check
            raise Exception("outdated")
    except Exception as e: # failed, call pip to install
        root = Tk.Tk() # dummy window
        root.withdraw()
        if str(e) == "outdated": messagebox.showinfo("Outdated modules", "Modules will be updated")
        else: messagebox.showinfo("Missing modules", "Missing modules will be installed")
        if os.name == 'nt':
            py_interpreter = os.path.join(os.__file__.split("lib\\")[0],"python")
        else:
            py_interpreter = "python"
        try:
            subprocess.check_call([py_interpreter, "-m", "pip", "install", "-r", "requirements.txt"])
            import tweepy
            import pyperclip
        except: # failed again, we exit
            if sys.platform == "win32":
                import ctypes
                try: is_admin = ctypes.windll.shell32.IsUserAnAdmin()
                except: is_admin = False
                if is_admin:
                    messagebox.showerror("Installation failed", "Failed to install the missing modules, check your internet connection\nAlternatively, try to run this application as administrator to force the installation.\nOr try to run the command pip install -r requirements.txt")
                elif messagebox.askquestion ("Installation failed","Restart the application as an administrator to try again?") == "yes":
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", py_interpreter, " ".join(sys.argv), None, 1)
            else:
                messagebox.showerror("Installation failed", "Failed to install the missing modules, check your internet connection\nAlternatively, try to run this application as a sudo user.\nOr try to run the command pip install -r requirements.txt")
            exit(0)
        root.destroy()
else:
    import tweepy
    import pyperclip

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

# global variables
enableTooltip = 1

#######################################################################
# Main class and tweepy listener
#######################################################################
class Raidfinder():
    def __init__(self):
        # class variables
        self.settings = {'jp':1, 'en':1, 'sound':1, 'copy':1, 'author':1, 'blacklist':1, 'dupe':1, 'delay':0, 'delay_limit':180, 'time_mode':0, 'max_thread':4, 'jst':0, 'lang':'English'}
        self.tweetQueue = queue.Queue()
        self.tweetDaemon = []
        self.THREAD_LIMIT = 50 # const
        self.tweetLock = []
        for i in range(6): self.tweetLock.append(threading.Lock())
        self.apprunning = True
        self.pause = False
        self.connected = False
        self.retry_delay = 0
        self.blacklist = []
        self.dupes = []
        self.filtervar = ""
        self.idregex = re.compile('([A-F0-9]{8}) :')
        self.dupes = []
        self.raids = {}
        self.custom = []
        self.stats = {'runtime':None, 'tweet':0, 'all tweet':0, 'dupe':0, 'blacklist':0, 'last':None, 'last tweet':None, 'delay':0, 'filtered':0}
        self.time = time.time()
        self.elapsed = 0
        self.lasttab = 0
        self.ping = None
        self.pingLock = threading.Lock()
        self.high_delay = False
        self.high_delay_count = 0
        self.filters = [" :参戦ID\n参加者募集！\n", " :Battle ID\nI need backup!\nLvl"]
        self.lang_options = ['English']
        self.lang_replace = {}
        try:
            self.si = subprocess.STARTUPINFO()
            self.si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        except:
            self.si = None

        # tweepy stuff
        self.keys = {'consumer_key': '', 'consumer_secret': '', 'access_token' : '', 'access_token_secret': ''}
        self.auth = None
        self.twitter_api = None
        self.stream = None
        self.paused = False

        # START
        tmpLog = []
        self.loadConfig(tmpLog)
        self.loadTranslation()
        self.UI = RaidfinderUI(self)
        for msg in tmpLog: self.UI.log(msg)

    def translate(self, string):
        if self.settings['lang'] == 'English': return string
        return self.lang_replace.get(string, string)

    def loadConfig(self, tmpLog): # call it once at the start
        global enableTooltip
        # load the .cfg with the Twitter API keys and settings
        config = configparser.ConfigParser()
        config.read('gbfraidcopier.cfg')

        # create a file if it didn't exist
        if len(config) == 0:
            try:
                config['Keys'] = self.keys
                with open('gbfraidcopier.cfg', 'w') as configfile:
                    config.write(configfile)
            except:
                pass
            return

        # twitter access keys
        try: self.keys = config['Keys']
        except: pass

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
            try: self.settings['delay'] = int(config['Settings']['delay'])
            except: pass
            try: self.settings['delay_limit'] = int(config['Settings']['delay_limit'])
            except: pass
            if self.settings['delay_limit'] < 60: self.settings['delay_limit'] = 60
            elif self.settings['delay_limit'] > 3600: self.settings['delay_limit'] = 3600
            try: self.settings['time_mode'] = int(config['Settings']['time_mode'])
            except: pass
            try: self.settings['jst'] = int(config['Settings']['jst'])
            except: pass
            try: self.lasttab = int(config['Settings']['lasttab'])
            except: pass
            try: enableTooltip = int(config['Settings']['tooltip'])
            except: pass
            try: self.filtervar = base64.b64decode(config['Settings']['filter']).decode('utf-8')
            except: pass
            try: self.settings['max_thread'] = int(config['Settings']['maxthread'])
            except: pass
            try: self.settings['lang'] = base64.b64decode(config['Settings']['lang']).decode('utf-8')
            except: pass
            if self.settings['max_thread'] < 1: self.settings['max_thread'] = 1
            elif self.settings['max_thread'] > self.THREAD_LIMIT: self.settings['max_thread'] = self.THREAD_LIMIT

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
            'delay': str(self.settings['delay']),
            'delay_limit': str(self.settings['delay_limit']),
            'time_mode': str(self.settings['time_mode']),
            'lasttab':str(self.lasttab),
            'maxthread':str(self.settings['max_thread']),
            'jst':str(self.settings['jst']),
            'tooltip':str(enableTooltip),
            'filter':base64.b64encode(self.filtervar.encode('utf-8')).decode('ascii'),
            'lang':base64.b64encode(self.UI.lang_var.get().encode('utf-8')).decode('ascii'),
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

    def loadTranslation(self): # load the raid.json, return an empty string on success
        try: # open the fail and load the data
            with open('translation.json', encoding='utf-8') as f:
                translationData = json.load(f)
            self.lang_options = ['English']
            for k in translationData:
                if k not in self.lang_options: self.lang_options.append(k)
            if self.settings['lang'] not in self.lang_options: self.settings['lang'] = 'English'
            self.lang_replace = translationData.get(self.settings['lang'], {})
        except Exception as e:
            print(e)
            self.settings['lang'] = 'English'
            self.lang_options = ['English']
            self.lang_replace = {}

    def loadRaids(self): # load the raid.json, return an empty string on success
        try: # open the fail and load the data
            with open('raid.json', encoding='utf-8') as f:
                raidData = json.load(f)
        except Exception as e:
            return self.translate("[JSON Error] Missing or invalid file\nPlease check if 'raid.json' is beside this python script\nAlternatively, please reinstall\n(Exception: {})").format(e)

        self.filters = raidData.get('filters', self.filters)

        # build the raid dictionnary
        x = {}
        try:
            for p in raidData['pages']: # for each page
                for r in p['list']: # read this page raid list
                    if 'en' in r: # retrieve english code
                       if r['en'] not in x: x[r['en']] = []
                       x[r['en']].append(self.translate(r.get('name', '')))
                    if 'jp' in r: # retrieve japanese code
                       if r['jp'] not in x: x[r['jp']] = []
                       x[r['jp']].append(self.translate(r.get('name', '')))
            for r in self.custom: # for each custom raid
                if r[1] not in x: x[r[1]] = [] # retrieve english code
                x[r[1]].append(r[0])
                if r[2] not in x: x[r[2]] = [] # retrieve japanese code
                x[r[2]].append(r[0])
            self.raids = x # overwrite our dictionnary with the new one
            self.UI.refreshRaids(raidData, self.custom) # update the UI
        except Exception as e:
            return self.translate("[JSON Error] Invalid file\n(Exception: {})").format(e)

        return ""

    def runRaidfinder(self): # MAIN FUNCTION
        # init
        err = self.loadRaids() # load the raid list
        if err != "":
            self.UI.log(err)
        self.loadBlacklist() # load blacklist.txt

        try:
            # Twitter authentification
            try: # test registered keys (if any)
                self.auth = tweepy.OAuthHandler(self.keys['consumer_key'], self.keys['consumer_secret'])
                self.auth.set_access_token(self.keys['access_token'], self.keys['access_token_secret'])
                self.twitter_api = tweepy.API(self.auth, wait_on_rate_limit=True)
                if self.twitter_api.verify_credentials() is None: raise Exception()
            except: # ask for authentification
                self.UI.log(self.translate("[Error] Authentification is required"))
                self.auth = tweepy.OAuthHandler("uSMr3m0GmKTqsNT0gnLyBpSPb", "PRya1sy5qkdJek7IWiCUQ3TLcJRcS46mPgOrEQPyllI7xqjTd2")
                try:
                    redirect_url = self.auth.get_authorization_url()
                    webbrowser.open(redirect_url, new=2)
                    verifier = simpledialog.askstring("Authorize this application", "enter the PIN code", initialvalue="")
                    self.auth.get_access_token(verifier)
                    self.twitter_api = tweepy.API(self.auth, wait_on_rate_limit=True)
                    if self.twitter_api.verify_credentials() is None: raise Exception("Authentification failed")
                    self.keys = {
                        'consumer_key': 'uSMr3m0GmKTqsNT0gnLyBpSPb',
                        'consumer_secret': 'PRya1sy5qkdJek7IWiCUQ3TLcJRcS46mPgOrEQPyllI7xqjTd2',
                        'access_token': self.auth.access_token,
                        'access_token_secret': self.auth.access_token_secret
                    }
                except Exception as x:
                    raise x
            # prepare and start the threads
            while len(self.tweetDaemon) < self.settings['max_thread']:
                self.tweetDaemon.append(threading.Thread(target=self.processTweet, args=[len(self.tweetDaemon)]))
                self.tweetDaemon[-1].setDaemon(True)
                self.tweetDaemon[-1].start()

            listenerDaemon = threading.Thread(target=self.runDaemon) # start the Twitter listener
            listenerDaemon.setDaemon(True)
            listenerDaemon.start()
        except Exception as e:
            self.UI.log(self.translate("[Error] Failed to start the raidfinder, authentification failed."))
            self.UI.log(self.translate("If the problem persists, try to delete the keys in 'gbfraidcopier.cfg'."))
            self.UI.log(self.translate("Exception: {}".format(traceback.format_exception(type(e), e, e.__traceback__))))

        self.UI.log("[Info] The next major version(s) will potentially have breaking changes.")
        self.UI.log("If you encounter any issues updating 'raid.json' in the future, please update the raidfinder.")

        # main loop
        while self.apprunning:
            self.elapsed = time.time() - self.time # measure elapsed time
            self.time = time.time()
            if not self.paused and self.connected:
                if self.stats['runtime'] is None: self.stats['runtime'] = self.elapsed
                else: self.stats['runtime'] += self.elapsed
            if self.ping is not None:
                msg = self.translate("Ping to {}").format(self.ping[5])
                if self.ping[0] > 0: msg += self.translate("\nMinimum {}ms, Average {}ms, Maximum {}ms").format(self.ping[3], self.ping[2], self.ping[4])
                if self.ping[1] > 0: msg += self.translate("\n{:.2f}% Packet Loss").format(100*self.ping[1]/(self.ping[0]+self.ping[1]))
                messagebox.showinfo(self.translate("Ping Results"), msg)
                self.UI.log(self.translate("[Info] Ping Results\n") + msg)
                self.ping = None
            self.UI.updateAll()
            time.sleep(0.02)

        # quitting
        for t in range(0, self.THREAD_LIMIT): # for each possible thread
            self.tweetQueue.put(None) # putting dummies to unblock the threads

    def pingServer(self, host, n): # update the ping stat
        if n < 1: return
        with self.pingLock:
            if self.ping is not None:
                return
            if self.settings['sound']: playsound()
            self.UI.log(self.translate("[Info] Sending 10 pings to {} ...").format(host))
            regex = re.compile('\d+ms')
            param = '-n' if platform.system().lower()=='windows' else '-c' # param
            command = ['ping', param, '1', host] # command
            result = [0, 0, 0, 0, 0, '']
            pings = []
            for i in range(0, n):
                p = subprocess.Popen(command, stdout=subprocess.PIPE, startupinfo=self.si) # call ping
                strout = str(p.communicate()[0]) # get output

                m = regex.search(strout) # search result
                if m:
                    try:
                        pings.append(int(m.group(0)[:-2]))
                        result[0] += 1
                    except:
                        pass
                else:
                    result[1] += 1
            result[1] = n - len(pings)
            if len(pings) > 0:
                result[0] = len(pings)
                result[2] = sum(pings) // len(pings)
                result[3] = min(pings)
                result[4] = max(pings)
            result[5] = host
            self.ping = result

    def runDaemon(self): # tweepy listener thread
        while self.apprunning:
            try: # starting tweepy
                if not self.connected:
                    self.UI.log(self.translate("[System] Connecting to Twitter..."))
                    self.stream = RaidfinderStream(self)
                self.stream.filter(track=self.filters) # this thread will block here until an issue occur
            except:
                pass
            if not self.apprunning or self.retry_delay == -1:
                return
            elif self.connected:
                continue
            elif self.retry_delay > 0:
                if self.retry_delay > 3:
                    self.UI.log(self.translate("[System] Attempting a new connection in {} seconds").format(self.retry_delay))
                time.sleep(self.retry_delay)
                self.high_delay = False

    def processTweet(self, i = -1): # tweet processing thread (can be run in parallel)
        while self.apprunning:
            try:
                if i >= len(self.tweetDaemon): # quit the thread if the number of threads got reduced
                    return
                try:
                    data, current_time = self.tweetQueue.get(block=True, timeout=0.01) # retrieve next tweet and its reception time
                except:
                    continue
                if not self.apprunning: # app stopped, we quit
                    return
                if self.paused: # app paused, we skip
                    continue

                # convert
                try: tweet = tweepy.models.Status.parse(self.twitter_api, json.loads(data))
                except: continue
                if tweet.source != "グランブルー ファンタジー": # filter non gbf tweet
                    continue
                # timestamp check
                delay = current_time - tweet.created_at
                with self.tweetLock[0]:
                    self.stats['delay'] = delay.seconds

                if self.settings['delay'] and delay.seconds >= self.settings['delay_limit']:
                    self.high_delay = True
                    continue # we raise the high delay flag
                # blacklist check
                if self.settings['blacklist'] and tweet.user.screen_name in self.blacklist:
                    with self.tweetLock[1]:
                        self.stats['blacklist'] += 1
                    continue # author is blacklisted, we skip
                st = html.unescape(tweet.text) # tweet content
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

                with self.tweetLock[2]:
                    self.stats['all tweet'] += 1
                    self.stats['last'] = time.time()

                comment = "" # build the author comment
                for c in range(0, p-mp): # ignoring out of range characters
                    if ord(st[c]) in range(65536):
                        comment += st[c]
                if self.filtervar != "" and self.filtervar.lower() not in comment.lower():
                    with self.tweetLock[3]:
                        self.stats['filtered'] += 1
                    continue

                raidName = st[p:].rsplit('\nhttp', 1)[0] # retrieve the raid name
                for r in self.raids.get(raidName, []): # get the corresponding raids
                    if self.UI.readonly.get(r, False): # check if enabled on the UI
                        with self.tweetLock[4]:
                            self.stats['tweet'] += 1
                            if self.settings['dupe'] and code in self.dupes:
                                self.stats['dupe'] += 1
                                break
                            self.UI.lastCode = code
                        if self.settings['copy']:
                            pyperclip.copy(code) # copy if enabled (note: is this thread safe?)
                        if self.settings['sound']: playsound() # play a sound if enabled
                        # write to the log
                        if self.settings['time_mode'] == 1:
                            if self.settings['jst']:
                                d = tweet.created_at + datetime.timedelta(seconds=32400)
                                t = d.strftime("%H:%M:%S JST")
                            else: t = tweet.created_at.strftime("%H:%M:%S UTC")
                        else:
                            if self.settings['jst']:
                                d = datetime.datetime.utcnow() + datetime.timedelta(seconds=32400)
                                t = d.strftime("%H:%M:%S JST")
                            else: t = strftime("%H:%M:%S")
                        if self.settings['author']: self.UI.log('[{}] {} : {} {} [@{}] {}'.format(t, r, code, lg, tweet.user.screen_name, comment))
                        else: self.UI.log('[{}] {} : {} {} {}'.format(t, r, code, lg, comment))
                        with self.tweetLock[5]: # stat + dupe cleanup
                            self.stats['last tweet'] = time.time()
                            self.dupes.append(code)
                            if len(self.dupes) > 200: self.dupes = self.dupes[50:] # removing 50 oldest if 200 dupes
                        break
            except Exception as e:
                if i == -1: print(traceback.format_exception(type(e), e, e.__traceback__))
                else: print('thread', i, ':', traceback.format_exception(type(e), e, e.__traceback__))

#######################################################################
# Stream
#######################################################################
class RaidfinderStream(tweepy.Stream):
    def __init__(self, parent):
        self.parent = parent
        super().__init__(self.parent.keys['consumer_key'], self.parent.keys['consumer_secret'], self.parent.keys['access_token'], self.parent.keys['access_token_secret'])

    def on_data(self, data):
        if self.parent.high_delay: # trigger high delay restart
            self.parent.high_delay = False
            self.parent.high_delay_count = min(self.parent.high_delay_count+1, 12)
            raise Exception("High Delay")

        self.parent.tweetQueue.put_nowait((data, datetime.datetime.now(datetime.timezone.utc)))

    def on_connect(self): # when the Twitter stream connects
        if not self.parent.connected:
            self.parent.UI.log(self.parent.translate("[System] Twitter stream connected"))
        self.parent.connected = True

    def on_disconnect(self): # when the Twitter stream disconnects
        if self.parent.connected:
            self.parent.UI.log(self.parent.translate("[System] Twitter stream disconnected"))
        self.parent.connected = False

    def on_exception(self, exception): # when a problem occurs
        print("on_exception():", traceback.format_exception(type(exception), exception, exception.__traceback__))
        s = str(exception)
        if s == "High Delay": # high delay restart triggered
            self.parent.UI.log(self.parent.translate("[Error] High delay detected"))
            self.parent.connected = False
            self.parent.retry_delay = self.parent.high_delay_count * 5
        elif self.parent.connected: # exception happened while being connected
            if s.lower().find("timed out") != -1 or s.lower().find("connection broken") != -1:
                self.parent.UI.log(self.parent.translate("[Error] Communication issue, check your internet connection or Twitter server status"))
            else:
                self.parent.UI.log(self.parent.translate("[Error] An exception occurred: {}").format(traceback.format_exception(type(exception), exception, exception.__traceback__)))
            self.parent.connected = False
            self.parent.retry_delay = 10
        else: # else, unknown error
            self.parent.UI.log(self.parent.translate("[Error] Twitter keys might be invalid or your Internet is down"))
            self.parent.UI.log(self.parent.translate("Exception: {}".format(exception)))
            self.parent.connected = False
            self.parent.retry_delay = -1

#######################################################################
# Custom UI ToolTip class
#######################################################################
class Tooltip():
    def __init__(self, parent, text): # create a tooltip for the parent widget, with the associated text
        self.parent = parent
        self.tip = None
        self.text = text
        if parent:
            self.parent.bind('<Enter>', self.show) # bind to hover
            self.parent.bind('<Leave>', self.hide) # bind to not-hover

    def show(self, event): # called by the enter event, show the text
        if not enableTooltip or self.tip or not self.text: # don't show twice or if no text
            return
        x, y, cx, cy = self.parent.bbox("insert") # bound box
        x = x + self.parent.winfo_rootx() + 20 # make our tip 20px on the right
        y = y + cy + self.parent.winfo_rooty() + 20 # and 20px lower
        self.tip = Tk.Toplevel(self.parent)
        self.tip.wm_overrideredirect(1)
        self.tip.wm_geometry("+%d+%d" % (x, y))
        label = Tk.Label(self.tip, text=self.text, justify=Tk.LEFT, background="#ffffe0", relief=Tk.SOLID, borderwidth=1)
        label.pack(ipadx=1)

    def hide(self, event): # called by the leave event, destroy the label
        tmp = self.tip
        self.tip = None
        if tmp: tmp.destroy()

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
        self.lastCode = None
        self.lastSettingNum = None
        self.lang_var = Tk.StringVar()
        self.lang_var.set(self.raidfinder.settings['lang'])

        # building the UI
        ## raid part
        self.mainframes = []
        self.mainframes.append(ttk.Notebook(self))
        self.mainframes[-1].grid(row=0, column=0, columnspan=10, sticky="we")
        self.raids = [] # empty for now
        self.raidchilds = []
        self.custom = []

        ## tweet filter
        self.mainframes.append(ttk.Frame(self))
        self.mainframes[-1].grid(row=1, column=0, rowspan=1, columnspan=10, sticky="we")
        self.filterlabel = Tk.Label(self.mainframes[-1], text=self.raidfinder.translate("Filter by Messages"))
        self.filterlabel.pack(side=Tk.LEFT)
        Tooltip(self.filterlabel, self.raidfinder.translate("Only the tweets containing this string will be processed"))
        self.filterlabeloriginal = self.filterlabel.cget("background")
        self.filter=Tk.Text(self.mainframes[-1], height=1)
        self.filter.pack(side=Tk.LEFT, fill=Tk.X)
        self.filter.insert(Tk.END, self.raidfinder.filtervar)
        self.filter.bind("<FocusIn>", self.focusin)
        self.filter.bind("<FocusOut>", self.focusout)
        self.filter.bind('<<Modified>>', self.updateFilter)
        self.filterModified = False

        ## main settings
        self.mainframes.append(ttk.Frame(self))
        self.mainframes[-1].grid(row=2, column=0, columnspan=10, sticky="we")
        self.mainsett_b = []
        self.mainsett_tag = ["Pause","Japanese","English","Sound","Auto Copy"]
        convert = {"Pause":["", "If enabled, tweets will be discarded instead of being processed."], "Japanese":["jp", "If disabled, japanese tweets will be discarded."], "English":["en", "If disabled, english tweets will be discarded."], "Sound":["sound", "If enabled, a sound will play when a new code is available."], "Auto Copy":["copy", "If enabled, the latest code will be copied to your clipboard."]} # convert to the setting dict key + the tooltip text
        for x in self.mainsett_tag: # adding the buttons
            self.mainsett_b.append(Tk.Checkbutton(self.mainframes[-1], text="[{}] {}".format(len(self.mainsett_b), self.raidfinder.translate(x)), variable=self.newIntVar(self.mainsett, self.raidfinder.settings.get(convert[x][0], 0)), command=lambda n=len(self.mainsett_b): self.toggleMainSetting(n)))
            self.mainsett_b[-1].grid(row=0, column=len(self.mainsett_b)-1)
            Tooltip(self.mainsett_b[-1], self.raidfinder.translate(convert[x][1]))
        b = Tk.Button(self.mainframes[-1], text=self.raidfinder.translate("[{}] Copy Latest").format(len(self.mainsett_b)), command=self.copyLatest) # ping mobage
        b.grid(row=0, column=len(self.mainsett_b), sticky="ews")
        self.lastSettingNum = len(self.mainsett_b)
        Tooltip(b, self.raidfinder.translate("Put the latest raid code in the clipboard."))

        ## bottomn (log / advanced setting / stats)
        self.mainframes.append(ttk.Notebook(self))
        self.mainframes[-1].grid(row=3, column=0, columnspan=10, sticky="we")
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
        self.subtabs.append(Tk.Frame(self.mainframes[-1], bg='#dfe5d7')) # setting frame
        self.mainframes[-1].add(self.subtabs[-1], text=self.raidfinder.translate("Advanced")) # tab
        b = Tk.Checkbutton(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=self.raidfinder.translate("Ignore Duplicate Codes"), variable=self.newIntVar(self.advsett, self.raidfinder.settings['dupe']), command=lambda n=0: self.toggleAdvSetting(n))
        b.grid(row=0, column=0, stick=Tk.W)
        Tooltip(b, self.raidfinder.translate("If enabled, codes already in memory will be skipped.\nA code is added to the memory only if the corresponding raid is selected.\nUp to 200 codes are stored in memory. Once reached, the 50 oldests are discarded."))
        b = Tk.Checkbutton(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=self.raidfinder.translate("Show Twitter Handle"), variable=self.newIntVar(self.advsett, self.raidfinder.settings['author']), command=lambda n=1: self.toggleAdvSetting(n))
        b.grid(row=1, column=0, stick=Tk.W)
        Tooltip(b, self.raidfinder.translate("If enabled, the tweet author handle will be added to the log."))
        b = Tk.Checkbutton(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=self.raidfinder.translate("Enable Author Blacklist"), variable=self.newIntVar(self.advsett, self.raidfinder.settings['blacklist']), command=lambda n=2: self.toggleAdvSetting(n))
        b.grid(row=2, column=0, stick=Tk.W)
        Tooltip(b, self.raidfinder.translate("If enabled, tweets from the authors whose handles are in blacklist.txt will be ignored."))
        b = Tk.Checkbutton(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=self.raidfinder.translate("Restart stream on high delay"), variable=self.newIntVar(self.advsett, self.raidfinder.settings['delay']), command=lambda n=3: self.toggleAdvSetting(n))
        b.grid(row=3, column=0, stick=Tk.W)
        Tooltip(b, self.raidfinder.translate("If enabled, the tweet stream will automatically restart once the delay limit is reached.\nIt's useful when twitter has server issues and the tweet delay starts building up over time."))
        b = Tk.Checkbutton(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=self.raidfinder.translate("Tweet Creation Time"), variable=self.newIntVar(self.advsett, self.raidfinder.settings['time_mode']), command=lambda n=4: self.toggleAdvSetting(n))
        b.grid(row=0, column=1, stick=Tk.W)
        Tooltip(b, self.raidfinder.translate("If enabled, all new timestamps in the log will be using the tweet creation time, in UTC, instead of the current time."))
        b = Tk.Checkbutton(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=self.raidfinder.translate("Force JST Timezone"), variable=self.newIntVar(self.advsett, self.raidfinder.settings['jst']), command=lambda n=5: self.toggleAdvSetting(n))
        b.grid(row=1, column=1, stick=Tk.W)
        Tooltip(b, self.raidfinder.translate("If enabled, the clock and all timestamps will be converted to JST."))
        b = Tk.Checkbutton(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=self.raidfinder.translate("Enable Tool Tips"), variable=self.newIntVar(self.advsett, enableTooltip), command=lambda n=6: self.toggleAdvSetting(n))
        b.grid(row=2, column=1, stick=Tk.W)
        Tooltip(b, self.raidfinder.translate("If disabled, tooltips such as this one will not show up."))

        b = Tk.Button(self.subtabs[-1], text=self.raidfinder.translate("Reload Blacklist"), command=self.reloadBlacklist) # reload blacklist button
        b.grid(row=0, column=2, sticky="ews")
        Tooltip(b, self.raidfinder.translate("Reload the content of blacklist.txt."))
        b = Tk.Button(self.subtabs[-1], text=self.raidfinder.translate("Reload Raid List"), command=self.reloadRaidList) # reload raid list button
        b.grid(row=1, column=2, sticky="ews")
        Tooltip(b, self.raidfinder.translate("Reload the content of raid.json.\nCurrent selected raids will be discarded."))
        b = Tk.Button(self.subtabs[-1], text="Ping Twitter", command=lambda n=0 : self.startPing(n)) # ping twitter
        b.grid(row=2, column=2, sticky="ews")
        Tooltip(b, self.raidfinder.translate("Send 10 pings to stream.twitter.com.\nIf the values are high or you notice packet loss, your connection or twitter might have issues"))
        b = Tk.Button(self.subtabs[-1], text=self.raidfinder.translate("Ping GBF"), command=lambda n=1 : self.startPing(n)) # ping granblue fantasy
        b.grid(row=2, column=3, sticky="ews")
        Tooltip(b, self.raidfinder.translate("Send 10 pings to game.granbluefantasy.jp.\nIf the values are high or you notice packet loss, your connection or GBF might have issues"))
        b = Tk.Button(self.subtabs[-1], text=self.raidfinder.translate("Latest Version"), command=lambda n=0 : self.openBrowser(n)) # download link button
        b.grid(row=0, column=3, sticky="ews")
        Tooltip(b, self.raidfinder.translate("Open up the download link to the latest version in your browser."))
        b = Tk.Button(self.subtabs[-1], text=self.raidfinder.translate("Latest raid.json"), command=lambda n=1 : self.openBrowser(n)) # download raid list button
        b.grid(row=1, column=3, sticky="ews")
        Tooltip(b, self.raidfinder.translate("Open up the download link to the latest raid.json in your browser."))
        b = Tk.Button(self.subtabs[-1], text=self.raidfinder.translate("Github"), command=lambda n=2 : self.openBrowser(n)) # github
        b.grid(row=3, column=2, sticky="ews")
        Tooltip(b, self.raidfinder.translate("Open up the link to the project Github."))

        # language choice
        b = Tk.OptionMenu(self.subtabs[-1], self.lang_var, *self.raidfinder.lang_options, command=self.lang_changed)
        b.grid(row=4, column=0, stick=Tk.W)
        Tooltip(b, self.raidfinder.translate("Change the UI language."))

        # thread count spinbox
        l = Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=self.raidfinder.translate("Tweet Processing Threads"))
        l.grid(row=0, column=4, sticky="ws")
        Tooltip(l, self.raidfinder.translate("Number of threads used to process the incoming tweets."))
        threadSpinBox = Tk.Spinbox(self.subtabs[-1], from_=1, to=self.raidfinder.THREAD_LIMIT, textvariable=Tk.StringVar(value=str(self.raidfinder.settings['max_thread'])), validate='all', validatecommand=(self.subtabs[-1].register(self.updateTweetThreadCount), '%P'))
        threadSpinBox.grid(row=1, column=4, sticky="ews")
        threadSpinBox.bind("<FocusIn>", self.focusin)
        threadSpinBox.bind("<FocusOut>", self.focusout)

        # delay limit spinbox
        l = Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=self.raidfinder.translate("Delay Limit"))
        l.grid(row=2, column=4, sticky="ws")
        Tooltip(l, self.raidfinder.translate("Delay limit, in seconds, before an automatic restart (if enabled)."))
        delaySpinBox = Tk.Spinbox(self.subtabs[-1], from_=60, to=3600, textvariable=Tk.StringVar(value=str(self.raidfinder.settings['delay_limit'])), validate='all', validatecommand=(self.subtabs[-1].register(self.updateDelayLimit), '%P'))
        delaySpinBox.grid(row=3, column=4, sticky="ews")
        delaySpinBox.bind("<FocusIn>", self.focusin)
        delaySpinBox.bind("<FocusOut>", self.focusout)

        ### stats
        # mostly text labels, you can skip over it
        self.subtabs.append(Tk.Frame(self.mainframes[-1], bg='#e5e0d7'))
        self.mainframes[-1].add(self.subtabs[-1], text=self.raidfinder.translate("Statistics"))
        self.stats = []
        Tk.Button(self.subtabs[-1], text=self.raidfinder.translate("Reset"), command=self.resetStats).grid(row=4, column=0, sticky="ews") # reset button
        # all stats to be displayed (Label Text, Position X, Position Y, Default Text, Tooltip Text)
        labels = [["Connection Time:", 0, 0, "0:00:00", "Duration of your connection to twitter.\nPauses are ignored."],["Received tweets:", 0, 1, "0", "Number of tweets received by the listener."],["Matched tweets:", 0, 2, "0", "Number of received tweets correponding to the user selected raid(s)."],["Matched/Received:", 0, 3, "0.00%", "Ratio of selected raid tweets by all received tweets."],["Received rate:", 1, 1, "0/s", "Average reception speed."],["Match rate:", 1, 2, "0/s", "Average reception speed for the selected raids."],["Blacklisted:", 1, 0, "0", "Numbed of tweets blocked by the blacklist."],["Dupes:", 2, 0, "0", "Numbed of blocked duplicate codes."],["Last Received:", 2, 1, "?", "When was received the last tweet."],["Last Matched:", 2, 2, "?", "When was received the last tweet corresponding to a selected raid."],["Queued Tweets:", 1, 3, "0", "Number of tweets waiting to be processed."],["Twitter Delay:", 2, 3, "0s", "Delay between the tweet creation and its reception by the listener."],["Filtered:", 3, 0, "0", "Numbed of tweets blocked by the filter."]
        ]
        for l in labels:
            b = Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=self.raidfinder.translate(l[0]))
            b.grid(row=l[2], column=l[1]*2, sticky="ws")
            Tooltip(b, self.raidfinder.translate(l[4]))
            self.stats.append(Tk.Label(self.subtabs[-1], bg=self.subtabs[-1]['bg'], text=l[3]))
            self.stats[-1].grid(row=l[2], column=l[1]*2+1, sticky="nw")
            Tooltip(self.stats[-1], self.raidfinder.translate(l[4]))

        # others
        self.statusLabel = Tk.Label(self, text=self.raidfinder.translate("Offline"), bg='#edc7c7') # for the offline/online text
        self.statusLabel.grid(row=0, column=9, sticky="ne")
        Tooltip(self.statusLabel, self.raidfinder.translate("Indicate if the Twitter Stream is connected."))
        self.timeLabel = Tk.Label(self, text="") # for the current time
        self.timeLabel.grid(row=2, column=9, sticky="ne")
        Tooltip(self.timeLabel, self.raidfinder.translate("Current time."))

        # make the window and bind the keyboard
        self.title(self.raidfinder.translate("Miza's Raidfinder v{}").format(version))
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
                self.mainframes[0].add(self.raids[-1], text=self.raidfinder.translate(p.get('name', '')))
                for r in p.get('list', []): # and add a checkbox for each raid
                    self.raidchilds.append(Tk.Checkbutton(self.raids[-1], bg=p.get('color', ''), text=self.raidfinder.translate(r.get('name', '')), variable=self.newTrackingVar(self.raidfinder.translate(r.get('name', ''))), command=lambda r=self.raidfinder.translate(r.get('name', '')): self.toggleRaid(r)))
                    self.raidchilds[-1].grid(row=r.get('posY', 0), column=r.get('posX', 0), stick=Tk.W)
            # add the custom tab
            self.raids.append(Tk.Frame(self.mainframes[0], background=raids['custom color']))
            self.mainframes[0].add(self.raids[-1], text=self.raidfinder.translate("Custom"))
            self.custom = []
            for i in range(0, len(custom)): # same thing, with an extra Edit button
                self.raidchilds.append(Tk.Button(self.raids[-1], text=self.raidfinder.translate("Edit"), command=lambda i=i: self.editCustom(i)))
                self.raidchilds[-1].grid(row=i%6, column=(i//6)*2, sticky='ews')
                Tooltip(self.raidchilds[-1], self.raidfinder.translate("Edit this raid entry."))
                self.custom.append(Tk.Checkbutton(self.raids[-1], bg=raids['custom color'], text=custom[i][0], variable=self.newTrackingVar(custom[i][0]), command=lambda r=custom[i][0]: self.toggleRaid(r)))
                self.custom[-1].grid(row=i%6, column=1+(i//6)*2, stick=Tk.W)
            # select the last tab used
            self.mainframes[0].select(self.raidfinder.lasttab)
        except Exception as e:
            self.log(self.raidfinder.translate("[Error] Something went wrong while building the raid UI"))
            self.log(self.raidfinder.translate("Exception: {}").format(e))

    def toggleRaid(self, r): # called when un/checking a raid
        state = self.tracking[r].get()
        self.readonly[r] = state
        if state: self.log(self.raidfinder.translate('[Raid] Now tracking {}').format(r))
        else: self.log(self.raidfinder.translate('[Raid] Stopped tracking of {}').format(r))

    def toggleMainSetting(self, n): # called when un/checking a main setting
        state = self.mainsett[n].get()
        if n == 0: self.raidfinder.paused = state
        elif n == 1: self.raidfinder.settings['jp'] = state
        elif n == 2: self.raidfinder.settings['en'] = state
        elif n == 3: self.raidfinder.settings['sound'] = state
        elif n == 4: self.raidfinder.settings['copy'] = state
        if state: self.log(self.raidfinder.translate("[Settings] '{}' is enabled").format(self.mainsett_tag[n]))
        else: self.log(self.raidfinder.translate("[Settings] '{}' is disabled").format(self.mainsett_tag[n]))

    def toggleAdvSetting(self, n): # called when un/checking an advanced setting
        global enableTooltip
        state = self.advsett[n].get()
        if n == 0: self.raidfinder.settings['dupe'] = state
        elif n == 1: self.raidfinder.settings['author'] = state
        elif n == 2: self.raidfinder.settings['blacklist'] = state
        elif n == 3: self.raidfinder.settings['delay'] = state
        elif n == 4: self.raidfinder.settings['time_mode'] = state
        elif n == 5: self.raidfinder.settings['jst'] = state
        elif n == 6: enableTooltip = state

    def lang_changed(self, *args):
        messagebox.showinfo("Info", self.raidfinder.translate("The Raidfinder language has been changed.\nPlease restart the application."))

    def editCustom(self, i): # called when editing a custom raid
        self.inputting = True # to disable the keyboard shortcuts
        tmp = self.raidfinder.paused # save the pause setting
        self.raidfinder.paused = True # pause the app
        customEntry = self.raidfinder.custom[i]
        v1 = simpledialog.askstring(self.raidfinder.translate("Edit custom raid"), self.raidfinder.translate("input a name"), initialvalue=customEntry[0]) # ask for user input
        if v1 == None: # if the user cancelled
            self.inputting = False
            self.raidfinder.paused = tmp
            return # we return
        v2 = simpledialog.askstring(self.raidfinder.translate("Edit custom raid"), self.raidfinder.translate("input the english code"), initialvalue=customEntry[1])
        if v2 == None: # same thing
            self.inputting = False
            self.raidfinder.paused = tmp
            return
        v3 = simpledialog.askstring(self.raidfinder.translate("Edit custom raid"), self.raidfinder.translate("input the japanese code"), initialvalue=customEntry[2])
        if v3 == None: # same thing
            self.inputting = False
            self.raidfinder.paused = tmp
            return
        self.inputting = False # re-enable keyboard shortcuts

        self.raidfinder.custom[i] = [v1, v2, v3] # save the user inputs

        # reload list
        self.reloadRaidList(False)

        # log and end
        self.log(self.raidfinder.translate("[System] {} saved in slot {}").format(v1, i+1)) # logging for the user to check any mistake
        self.log(self.raidfinder.translate("code EN : {}").format(v2))
        self.log(self.raidfinder.translate("code JP : {}").format(v3))

        self.raidfinder.paused = tmp # restore the pause setting

    def key(self, event): # key event for setting shortcuts
        if not self.raidfinder.apprunning or event.type != '2' or self.inputting: # 2 is KeyPress
            return
        numKey = event.keycode - 48 # 48 is the 0 key
        if numKey < 0 or numKey > self.lastSettingNum:
            numKey = event.keycode - 96 # 96 is the 0 numpad key
        if numKey < 0 or numKey > self.lastSettingNum:
            return # not a number, so return
        if numKey == self.lastSettingNum:
            self.copyLatest() # copy last button
        else:
            self.mainsett_b[numKey].toggle() # toggle the checkbox
            self.toggleMainSetting(numKey) # call the event

    def close(self): # called by the app when closed
        self.raidfinder.saveConfig() # update config file
        self.raidfinder.apprunning = False
        self.destroy() # destroy the window

    def log(self, msg):
        self.logQueue.put(msg) # add a message to the log queue

    def reloadBlacklist(self): # reload the blacklist
        self.raidfinder.loadBlacklist()
        messagebox.showinfo(self.raidfinder.translate("Info"), self.raidfinder.translate("'blacklist.txt' has been reloaded.\n{} entrie(s) found.").format(len(self.raidfinder.blacklist)))

    def reloadRaidList(self, prompt = True): # reload the raid list
        self.raidfinder.lasttab = self.mainframes[0].index(self.mainframes[0].select()) # memorize last used tab
        err = self.raidfinder.loadRaids() # reload the list
        self.log(self.raidfinder.translate("[System] Raid list have been reloaded"))
        if prompt:
            if err == "":
                messagebox.showinfo(self.raidfinder.translate("Info"), self.raidfinder.translate("'raid.json' has been reloaded.\n{} code(s) found.").format(len(self.raidfinder.raids)))
            else:
                messagebox.showinfo(self.raidfinder.translate("Error"), self.raidfinder.translate("Failed to reload 'raid.json'\nException: {}").format(err))

    def updateTweetThreadCount(self, entry):
        try: # validate the spinbox value
            n = int(entry)
            valid = n in range(1, self.raidfinder.THREAD_LIMIT)
        except ValueError:
            valid = False
        if valid: # update the threads
            self.raidfinder.settings['max_thread'] = n
            while n < len(self.raidfinder.tweetDaemon):
                self.raidfinder.tweetDaemon.pop()
            while n > len(self.raidfinder.tweetDaemon):
                self.raidfinder.tweetDaemon.append(threading.Thread(target=self.raidfinder.processTweet, args=[len(self.raidfinder.tweetDaemon)]))
                self.raidfinder.tweetDaemon[-1].setDaemon(True)
                self.raidfinder.tweetDaemon[-1].start()
        return valid

    def updateFilter(self, event):
        if not self.filterModified:
            self.raidfinder.filtervar = self.filter.get('0.0', 'end')[:-1]
        self.filterModified = not self.filterModified
        self.tk.call(self.filter, 'edit', 'modified', 0)

    def updateDelayLimit(self, entry):
        try: # validate the spinbox value
            n = int(entry)
            valid = n in range(60, 3600)
        except ValueError:
            valid = False
        if valid: # update the threads
            self.raidfinder.settings['delay_limit'] = n
        return valid

    def focusin(self, event): # event for managing a widget focus
        self.inputting = True

    def focusout(self, event): # event for managing a widget focus
        self.inputting = False

    def resetStats(self): # simply reset the stats
        self.raidfinder.stats = {'runtime':None, 'tweet':0, 'all tweet':0, 'dupe':0, 'blacklist':0, 'last':None, 'last tweet':None, 'delay':0, 'filtered':0}

    def openBrowser(self, n): # open the user web browser
        if n == 0: webbrowser.open('https://drive.google.com/file/d/0B9YhZA7dWJUsY1lKMXY4bV9nZUE/view?usp=sharing', new=2)
        elif n == 1: webbrowser.open('https://drive.google.com/file/d/1mq0zkMwqf6Uvem12gdoUIvSJhC_u7jDT/view?usp=sharing', new=2)
        elif n == 2: webbrowser.open('https://github.com/MizaGBF/Raidfinder', new=2)

    def startPing(self, n): # open the user web browser
        if n == 0: thread = threading.Thread(target=self.raidfinder.pingServer, args=["stream.twitter.com", 10])
        elif n == 1: thread = threading.Thread(target=self.raidfinder.pingServer, args=["game.granbluefantasy.jp", 10])
        else: return
        thread.setDaemon(True)
        thread.start()

    def copyLatest(self):
        if self.lastCode != None:
            pyperclip.copy(self.lastCode)
            self.log(self.raidfinder.translate("[System] Code {} has been put in the clipboard").format(self.lastCode))

    def formatStat(self, v):
        if v > 1000000: return str(v // 1000000) + "M"
        elif v > 1000: return str(v // 1000) + "K"
        return v

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
        self.stats[1].config(text="{}".format(self.formatStat(self.raidfinder.stats['all tweet'])))
        self.stats[2].config(text="{}".format(self.formatStat(self.raidfinder.stats['tweet'])))
        if self.raidfinder.stats['all tweet'] == 0: self.stats[3].config(text="0%")
        else: self.stats[3].config(text="{:.2f}%".format(100*self.raidfinder.stats['tweet']/self.raidfinder.stats['all tweet']))
        try: self.stats[4].config(text="{:.2f}/s".format(self.raidfinder.stats['all tweet']/self.raidfinder.stats['runtime']))
        except: self.stats[4].config(text="0/s")
        try: self.stats[5].config(text="{:.2f}/s".format(self.raidfinder.stats['tweet']/self.raidfinder.stats['runtime']))
        except: self.stats[5].config(text="0/s")
        self.stats[6].config(text="{}".format(self.formatStat(self.raidfinder.stats['blacklist'])))
        self.stats[7].config(text="{}".format(self.formatStat(self.raidfinder.stats['dupe'])))
        if self.raidfinder.stats['last'] is not None:
            self.stats[8].config(text="{:.2f}s".format(time.time() - self.raidfinder.stats['last']))
        else: 
            self.stats[8].config(text="0.00s")
        if self.raidfinder.stats['last tweet'] is not None:
            self.stats[9].config(text="{:.2f}s".format(time.time() - self.raidfinder.stats['last tweet']))
        else: 
            self.stats[9].config(text="0.00s")
        self.stats[10].config(text="{}".format(self.raidfinder.tweetQueue.qsize()))
        self.stats[11].config(text="{}s".format(self.raidfinder.stats['delay']))
        self.stats[12].config(text="{}".format(self.formatStat(self.raidfinder.stats['filtered'])))
        
        # update the time and online indicator
        if self.raidfinder.settings['jst']:
            d = datetime.datetime.utcnow() + datetime.timedelta(seconds=32400)
            self.timeLabel.config(text=d.strftime("%H:%M:%S JST"))
        else: self.timeLabel.config(text=strftime("%H:%M:%S"))
        if self.raidfinder.connected: self.statusLabel.config(text=self.raidfinder.translate("Online"), background='#c7edcd')
        else: self.statusLabel.config(text=self.raidfinder.translate("Offline"), background='#edc7c7')

        if len(self.raidfinder.filtervar) > 0:
            self.filterlabel.config(background='#c7edcd')
        else:
            self.filterlabel.config(background=self.filterlabeloriginal)

        # update tkinter
        self.update()

# entry point
if __name__ == "__main__":
    r = Raidfinder()
    r.runRaidfinder()