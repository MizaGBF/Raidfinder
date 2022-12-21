import json
import configparser
import time
import queue
import datetime
import base64
import tkinter as Tk
import tkinter.ttk as ttk
from tkinter import messagebox, simpledialog
import sys
import os
import platform
import subprocess
import webbrowser
from urllib import request
import re
import threading
import traceback

###########################################################################################################################
# version.json loading
###########################################################################################################################
try:
    with open('version.json', encoding="utf-8") as f:
        versions = json.load(f)
    for key in ["raidfinder", "raidlist", "tweepy", "pyperclip"]:
        if key not in versions:
            raise Exception()
except Exception as e:
    messagebox.showerror("Invalid version.json", "Consider redownloading a fresh copy of this raidfinder")
    raise Exception("Can't load 'version.json'") from e

###########################################################################################################################
# sound
###########################################################################################################################
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

###########################################################################################################################
# general utility
###########################################################################################################################
def cmpVer(mver, tver): # compare version strings, True if greater or equal, else False
    me = mver.split('.')
    te = tver.split('.')
    for i in range(0, min(len(me), len(te))):
        if int(me[i]) < int(te[i]):
            return False
    return True

###########################################################################################################################
# import tweepy and pyperclip and check their versions
###########################################################################################################################
if __name__ == "__main__":
    try: # try to import
        import tweepy
        import pyperclip
        # compare and check module versions
        if not cmpVer(tweepy.__version__, versions["tweepy"]) or not cmpVer(pyperclip.__version__, versions["pyperclip"]):
            raise Exception("outdated")
    except Exception as e: # failed, call pip to install
        root = Tk.Tk() # dummy window
        root.withdraw()
        if str(e) == "outdated": messagebox.showinfo("Outdated modules", "Modules will be updated")
        else: messagebox.showinfo("Missing modules", "Missing modules will be installed")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            import tweepy
            import pyperclip
        except: # failed again, we exit
            if sys.platform == "win32":
                import ctypes
                try: is_admin = ctypes.windll.shell32.IsUserAnAdmin()
                except: is_admin = False
                if is_admin:
                    messagebox.showerror("Installation failed", "Failed to install the missing modules, check your internet connection\nAlternatively, try to run this application as administrator to force the installation.\nOr try to run the command, in a command prompt, pip install -r requirements.txt")
                elif messagebox.askquestion ("Installation failed","Restart the application as an administrator to try again?") == "yes":
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            else:
                messagebox.showerror("Installation failed", "Failed to install the missing modules, check your internet connection\nAlternatively, try to run this application as a sudo user.\nOr try to run the command, in a command prompt, pip install -r requirements.txt")
            exit(0)
        root.destroy()
else:
    # this part only run if you import the raidfinder in another project
    import tweepy
    import pyperclip

###########################################################################################################################
# Raidfinder Class
###########################################################################################################################

class Raidfinder():
    def __init__(self, versions, use_ui=True):
        self.versions = versions
        self.settings = {'pause':0, 'jp':1, 'en':1, 'sound':1, 'copy':1, 'author':1, 'dupe':1, 'time':0, 'jst':0, 'lang':'en.json', 'update_raids':1, 'update_raidfinder':1, 'tooltip':1, 'second':0, 'limit':1, 'limit_rule':5, 'limit_char':512}
        self.langs = {}
        self.strings = {}
        self.raids = {}
        self.apprunning = True
        self.filter = ""
        self.stats = {"stat_time":None, "stat_received":0, "stat_matched":0, "stat_dupes":0, "stat_filter":0 ,"stat_delay":0 ,"stat_received_last":None ,"stat_matched_last":None}
        self.connected = False
        self.custom = []
        self.bearer_token = ""
        self.keys = {}
        self.tracked = {}
        self.statlock = threading.Lock()
        self.elapsed = 0
        self.time = time.time()
        self.lastcode = ""
        self.secondcode = ""
        self.log = Log()
        self.lasttab = 0
        
        self.loadSetting()
        self.initLangs()
        if not self.loadLanguage(self.settings.get("lang", self.settings.get('lang'))):
            self.loadLanguage('en.json')
        self.log.push(self.getString('news')) # to remove later

        self.checkUpdate()
        loadedRaid = self.loadRaids()
        self.stream = Stream(self)
        self.ui = (UI(self) if use_ui else None)
        
        if loadedRaid:
            self.ui.reloadRaids(self.raids, self.custom)
        else:
            self.log.push(self.getString("err_load_raid"))

        if use_ui and self.bearer_token == "":
            messagebox.showinfo("Info", self.getString("err_empty_token"))
            return

    def loadSetting(self):
        # load the .cfg with the Twitter API keys and settings
        config = configparser.RawConfigParser(strict=True)
        
        try:
            with open('gbfraidcopier.cfg', encoding="utf-8") as f:
                config.read_file(f)
        except:
            try:
                config['Twitter'] = {'bearer_token':''}
                with open('gbfraidcopier.cfg', mode='w', encoding="utf-8") as f:
                    config.write(f)
            except:
                pass

        # twitter access keys
        try: self.bearer_token = config['Twitter']['bearer_token']
        except: pass
        try: self.keys = config['Keys'] # for retrocompatibility, to remove in the future
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
            try: self.settings['dupe'] = int(config['Settings']['duplicate'])
            except: pass
            try: self.settings['time'] = int(config['Settings']['time'])
            except: pass
            try: self.settings['jst'] = int(config['Settings']['jst'])
            except: pass
            try: self.lasttab = int(config['Settings']['lasttab'])
            except: pass
            try: self.settings['tooltip'] = int(config['Settings']['tooltip'])
            except: pass
            try: self.filter = base64.b64decode(config['Settings']['filter']).decode('utf-8')
            except: pass
            try: self.settings['lang'] = base64.b64decode(config['Settings']['lang']).decode('utf-8')
            except: pass
            try: self.settings['update_raids'] = int(config['Settings']['check_raid_list'])
            except: pass
            try: self.settings['update_raidfinder'] = int(config['Settings']['check_raidfinder'])
            except: pass
            try: self.settings['second'] = int(config['Settings']['copy_second'])
            except: pass
            try: self.settings['limit'] = int(config['Settings']['limit'])
            except: pass
            try: self.settings['limit_rule'] = int(config['Settings']['limit_rule'])
            except: pass
            try: self.settings['limit_char'] = int(config['Settings']['limit_char'])
            except: pass

        # custom user raids
        if 'Raids' in config:
            for i in range(0, 27):
                self.custom.append(["My Raid {}".format(i+1), "Lvl 100 ???", "Lv100 ???"])
                try:
                    self.custom[i][0] = base64.b64decode(config['Raids']['savedName' + str(i)]).decode('utf-8')
                    self.custom[i][1] = base64.b64decode(config['Raids']['savedEN' + str(i)]).decode('utf-8')
                    self.custom[i][2] = base64.b64decode(config['Raids']['savedJP' + str(i)]).decode('utf-8')
                except:
                    pass

    def saveSetting(self): # called when quitting
        # update the values
        # NOTE : pause setting isn't saved !
        try:
            config = configparser.RawConfigParser()
            try: self.lasttab = self.ui.raidframe.index(self.ui.raidframe.select())
            except: self.lasttab = 0
            config['Settings'] = {
                'japanese': str(self.settings['jp']),
                'english': str(self.settings['en']),
                'sound': str(self.settings['sound']),
                'copy': str(self.settings['copy']),
                'author': str(self.settings['author']),
                'duplicate': str(self.settings['dupe']),
                'time_mode': str(self.settings['time']),
                'lasttab':str(self.lasttab),
                'jst':str(self.settings['jst']),
                'tooltip':str(self.settings['tooltip']),
                'check_raid_list':str(self.settings['update_raids']),
                'check_raidfinder':str(self.settings['update_raidfinder']),
                'copy_second':str(self.settings['second']),
                'limit':str(self.settings['limit']),
                'limit_rule':str(self.settings['limit_rule']),
                'limit_char':str(self.settings['limit_char']),
                'filter':base64.b64encode(self.filter.encode('utf-8')).decode('ascii'),
                'lang':base64.b64encode(self.lookupLangFile(self.ui.lang_var.get()).encode('utf-8')).decode('ascii')
            }

            config['Twitter'] = {'bearer_token':self.bearer_token}
            config['Keys'] = self.keys # to remove later

            config['Raids'] = {}
            for i in range(0, 27): # custom user raids
                if i>= len(self.custom):
                    config['Raids']['savedName' + str(i)] = base64.b64encode("Raid #{}".format(i+1).encode('utf-8')).decode('ascii') 
                    config['Raids']['savedEN' + str(i)] = base64.b64encode("Lvl 100 ???".encode('utf-8')).decode('ascii') 
                    config['Raids']['savedJP' + str(i)] = base64.b64encode("Lv100 ???".encode('utf-8')).decode('ascii') 
                else:
                    config['Raids']['savedName' + str(i)] = base64.b64encode(self.custom[i][0].encode('utf-8')).decode('ascii') 
                    config['Raids']['savedEN' + str(i)] = base64.b64encode(self.custom[i][1].encode('utf-8')).decode('ascii') 
                    config['Raids']['savedJP' + str(i)] = base64.b64encode(self.custom[i][2].encode('utf-8')).decode('ascii') 
            # Writing our configuration file
            with open('gbfraidcopier.cfg', 'w', encoding="utf-8") as configfile:
                 config.write(configfile)
        except:
            print("Failed to write 'gbfraidcopier.cfg'")

        return True

    def checkUpdate(self):
        errmsg = False
        try:
            if self.settings['update_raidfinder'] == 0 and self.settings['update_raids'] == 0:
                return
            root = Tk.Tk() # dummy window
            root.withdraw()
            # download the latest version.json
            req = request.Request("https://raw.githubusercontent.com/MizaGBF/Raidfinder/master/version.json")
            url_handle = request.urlopen(req, timeout=60)
            data = json.loads(url_handle.read())
            url_handle.close()
            errmsg = True

            # check raid list
            if self.settings['update_raids'] == 1 and not cmpVer(self.versions['raidlist'], data['raidlist']):
                res = messagebox.askyesno("Raid List Update", self.getString('update_raid'))
                if res:
                    req = request.Request("https://raw.githubusercontent.com/MizaGBF/Raidfinder/master/raid.json")
                    url_handle = request.urlopen(req, timeout=60)
                    with open("raid.json", mode="wb") as f:
                        f.write(url_handle.read())
                    url_handle.close()
                    self.versions['raidlist'] = data['raidlist']
                    with open('version.json', mode='w', encoding="utf-8") as f: # update our version.json
                        json.dump(self.versions, f)
                    messagebox.showinfo("Raid List Update", self.getString('update_raid_success'))

            # check general version
            if self.settings['update_raidfinder'] == 1 and not cmpVer(self.versions['raidfinder'], data['raidfinder']):
                res = messagebox.askyesno("Update available", self.getString('update_main').format(data['raidfinder']))
                if res:
                    webbrowser.open('https://drive.google.com/drive/folders/0B9YhZA7dWJUsNzk4YU5Wd3RyZE0?resourcekey=0-dG3yEfxTyrq7j-fO4Yen0g', new=2)
        except:
            if errmsg: messagebox.showinfo("Update Error", self.getString('update_error'))
            try: url_handle.close()
            except: pass
        root.destroy()

    def initLangs(self):
        files = [f for f in os.listdir("lang") if os.path.isfile(os.path.join("lang", f))]
        for js in files:
            try:
                with open("lang/" + js, mode="r", encoding="utf-8") as f:
                    data = json.load(f)
                self.langs[js] = data['name']
            except Exception as e:
                self.log.push("Lang File error for '{}'\n{}".format(js, e))

    def loadLanguage(self, lang_file):
        try:
            with open("lang/en.json", mode="r", encoding="utf-8") as f:
                strings = json.load(f)
        except:
            self.log.push("Can't find 'lang/en.json'")
            return False
        if lang_file != "en.json":
            try:
                with open("lang/" + lang_file, mode="r", encoding="utf-8") as f:
                    overwrite = json.load(f)
            except:
                self.log.push("Can't find 'lang/{}'".format(lang_file))
                return False
            self.strings = {**strings, **overwrite}
        else:
            self.strings = strings
        self.settings['lang'] = lang_file
        return True

    def lookupLangFile(self, lang_name):
        for key in self.langs:
            if self.langs[key] == lang_name:
                return key
        return None

    def getString(self, key):
        return self.strings.get(key, key)

    def loadRaids(self):
        raids = {
            'en':{},
            'jp':{},
            'index':{},
            'pages':[],
            'filters':[]
        }
        try:
            with open("raid.json", mode="r", encoding="utf-8") as f:
                data = json.load(f)
            for p in data['pages']:
                for r in p['list']:
                    raids['index'][r['name']] = {'X':r['posX'], 'Y':r['posY'], 'page':len(raids['pages']), 'tracked':False}
                    raids['en'][r['name']] = r['en']
                    raids['jp'][r['name']] = r['jp']
                raids['pages'].append({'name':p['name'], 'color':p['color'], 'decorator':p.get('decorator', [])})
            raids['pages'].append({'name':'Custom', 'color':data['custom color'], 'decorator':[]})
            raids['filters'] = data['filters']
            for c in self.custom:
                if c[0] not in raids['en']:
                    raids['en'][c[0]] = c[1]
                    raids['jp'][c[0]] = c[2]
            self.raids = raids
        except Exception as e:
            print(e)
            self.log.push(self.getString('err_raid_load').format(e))
            return False
        return True

    def run(self):
        while self.apprunning:
            self.elapsed = time.time() - self.time # measure elapsed time
            self.time = time.time()
            if not self.settings['pause'] and self.connected:
                with self.statlock:
                    if self.stats['stat_time'] is None: self.stats['stat_time'] = self.elapsed
                    else: self.stats['stat_time'] += self.elapsed
            if self.ui:
                self.ui.run()
            else:
                for l in self.log.empty():
                    print(l)
            time.sleep(0.02)

    def lastCode(self):
        return self.secondcode if self.settings['second'] else self.lastcode

    def updateStreamTracking(self, raids):
        self.stream.tracked.put(raids)

###########################################################################################################################
# Log
###########################################################################################################################
class Log():
    def __init__(self):
        self.queue = queue.Queue()
        self.size = 0

    def push(self, msg):
        self.queue.put(msg)

    def empty(self):
        strings = []
        while not self.queue.empty():
            strings.append(self.queue.get())
        return strings

###########################################################################################################################
# Twitter Streaming Wrapper
###########################################################################################################################
class Stream(tweepy.StreamingClient):
    def __init__(self, parent):
        self.raidfinder = parent
        self.tweetQueue = queue.Queue()
        self.idregex = re.compile('([A-F0-9]{8}) :')
        super().__init__(bearer_token=self.raidfinder.bearer_token, return_type=dict, wait_on_rate_limit=True, daemon=True)
        self.myrules = {}
        self.trashrules = {}
        self.rulelock = threading.Lock()
        self.tracked = queue.Queue()
        self.restart_delay = 0
        if not self.clearRules():
            self.raidfinder.log.push(self.raidfinder.getString("err_auth"))
            return
        if not self.raidfinder.settings['limit']:
            if self.buildRules(self.raidfinder.raids['filters']):
                if not self.applyRules():
                    self.raidfinder.log.push(self.raidfinder.getString("err_unknown"))
                    return
            else:
                self.raidfinder.log.push(self.raidfinder.getString("err_unknown"))
                return
        else:
            self.raidfinder.log.push(self.raidfinder.getString("limit_info"))
        self.thread_ruleupdater = threading.Thread(target=self.ruleupdater)
        self.thread_ruleupdater.daemon = True
        self.thread_ruleupdater.start()
        self.thread_watchdog = threading.Thread(target=self.watchdog)
        self.thread_watchdog.daemon = True
        self.thread_watchdog.start()

    def clearRules(self):
        try:
            current_rules = self.get_rules()
            ids = []
            if 'data' in current_rules:
                for r in current_rules['data']:
                    ids.append(r['id'])
                if len(ids) > 0:
                    self.delete_rules(ids)
            return True
        except:
            return False

    def buildRules(self, filters):
        try:
            new_rules = []
            s = ""
            for i, f in enumerate(filters):
                if s != "":
                    if len(f) + len(" OR ") + len(s) >= 512:
                        new_rules.append(s)
                        if len(new_rules) >= 5: break
                        s = ""
                    else:
                        s += " OR "
                s += '"' + f + '"'
            if s != "":
                new_rules.append(s)
            newmyrules = {}
            with self.rulelock:
                for r in new_rules:
                    if r in self.myrules:
                        newmyrules[r] = self.myrules[r]
                    else:
                        newmyrules[r] = None
                for r in self.myrules:
                    if r not in newmyrules:
                        self.trashrules[r] = self.myrules[r]
                self.myrules = newmyrules
            return True
        except:
            return False

    def applyRules(self):
        try:
            rules = []
            with self.rulelock:
                for r, id in self.myrules.items():
                    if id is None:
                        rules.append(tweepy.StreamRule(value=r))
            
            while len(rules) > 0 or len(self.trashrules) > 0:
                if len(rules) > 0 and len(self.trashrules) < 5:
                    resp = self.add_rules(rules[-1])
                    if 'data' in resp:
                        for k in resp['data']:
                            self.myrules[k['value']] = k['id']
                    rules.pop()
                with self.rulelock:
                    if len(self.trashrules) > 0:
                        k = list(self.trashrules.keys())[0]
                        if self.trashrules[k] is not None:
                            self.delete_rules(self.trashrules[k])
                        self.trashrules.pop(k)
            return True
        except:
            return False

    def start_streaming(self):
        try:
            while self.raidfinder.settings['limit'] and len(self.myrules) == 0:
                time.sleep(0.01)
            self.applyRules()
            self.filter(tweet_fields=['source', 'created_at'], threaded=True)
        except Exception as e:
            self.raidfinder.log.push(self.raidfinder.getString("err_filter_error").format(e))
        # https://docs.tweepy.org/en/latest/streamingclient.html

    def on_data(self, raw_data):
        self.tweetQueue.put((json.loads(raw_data.decode('utf8'))['data'], datetime.datetime.utcnow()))

    def on_exception(self, exception):
        self.restart_delay = 10
        print("on_exception():", traceback.format_exception(type(exception), exception, exception.__traceback__))
        s = str(exception)
        if self.raidfinder.connected: # exception happened while being connected
            if s.lower().find("timed out") != -1 or s.lower().find("connection broken") != -1:
                self.raidfinder.log.push(self.raidfinder.getString("exception_timeout"))
            else:
                self.raidfinder.log.push(self.raidfinder.getString("exception_general").format(exception))
            self.raidfinder.connected = False
        else: # else, unknown error
            self.raidfinder.log.push(self.raidfinder.getString("exception_unknown").format(exception))
            self.raidfinder.connected = False
        self.raidfinder.log.push(self.raidfinder.getString("twitter_restart"))

    def on_connect(self):
        if not self.raidfinder.connected:
            self.raidfinder.log.push(self.raidfinder.getString('twitter_connected'))
        self.raidfinder.connected = True

    def on_disconnect(self):
        if self.raidfinder.connected:
            self.raidfinder.log.push(self.raidfinder.getString('twitter_disconnected'))
        self.raidfinder.connected = False

    def ruleupdater(self):
        while self.raidfinder.apprunning:
            if not self.tracked.empty():
                try:
                    raids = None
                    while not self.tracked.empty():
                        raids = self.tracked.get()
                    if raids is not None:
                        self.buildRules(raids)
                        self.applyRules()
                except:
                    pass
            time.sleep(0.5)

    def watchdog(self):
        time.sleep(5)
        stats = {}
        dupes = set()
        while self.raidfinder.apprunning:
            try:
                with self.raidfinder.statlock:
                    self.raidfinder.stats['stat_received'] += stats.get('stat_received', 0)
                    self.raidfinder.stats['stat_matched'] += stats.get('stat_matched', 0)
                    self.raidfinder.stats['stat_dupes'] += stats.get('stat_dupes', 0)
                    self.raidfinder.stats['stat_filter'] += stats.get('stat_filter', 0)
                    self.raidfinder.stats['stat_delay'] = stats.get('stat_delay', self.raidfinder.stats['stat_delay'])
                    self.raidfinder.stats['stat_received_last'] = stats.get('stat_received_last', self.raidfinder.stats['stat_received_last'])
                    self.raidfinder.stats['stat_matched_last'] = stats.get('stat_matched_last', self.raidfinder.stats['stat_matched_last'])
                stats = {}
                try:
                    data, reception_time = self.tweetQueue.get(block=True, timeout=0.01) # retrieve next tweet and its reception time
                except:
                    time.sleep(0.001)
                    if not self.running:
                        if self.restart_delay > 0:
                            time.sleep(self.restart_delay)
                            self.restart_delay = 0
                        self.start_streaming()
                    continue
                if self.raidfinder.settings['pause']:
                    continue
                created_at = datetime.datetime.strptime(data['created_at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                st = data['text']
                m = self.idregex.search(st)
                if not m:
                    continue # not found, we skip
                code = m.group(1) # get the code
                stats = {'stat_delay':(reception_time - created_at).seconds, 'stat_received_last':time.time(), 'stat_received':1}

                p = st.rfind("参加者募集！\n") # search the japanese 'I need backup' first (because it's most likely to be a japanese tweet
                lg = '(JP)'
                mp = 0 # minimal position of I need backup + raidname (used later to retrive the author comment if any)
                if p != -1 and p >= 15: # check the minimal position for jp
                    if not self.raidfinder.settings['jp']: continue
                    p += 7 # valid, add the size of JP I need backup. p nows points to the raid name
                    mp = 22
                else:
                    p = st.rfind("I need backup!\n") # same thing but for english
                    if p < 20 or not self.raidfinder.settings['en']: continue # english isn't valid, so is JP, we skip
                    p += 15 # size of I need backup
                    mp = 35
                    lg = '(EN)'

                raidname = st[p:].rsplit('\nhttp', 1)[0]

                r = self.raidfinder.tracked.get(raidname, None)
                if r is None:
                    continue
                stats['stat_matched'] = 1

                comment = "" # build the author comment
                for c in range(0, p-mp): # ignoring out of range characters
                    if ord(st[c]) in range(65536):
                        comment += st[c]

                stats['stat_matched_last'] = stats['stat_received_last']

                if self.raidfinder.filter != "" and self.raidfinder.filter.lower() not in comment.lower():
                    stats['stat_filter'] = 1
                    continue

                if code in dupes:
                    stats['stat_dupe'] = 1
                    continue

                if self.raidfinder.settings['copy']:
                    pyperclip.copy(self.raidfinder.lastcode if self.raidfinder.settings['second'] else code) # copy if enabled
                if self.raidfinder.settings['sound']:
                    playsound() # play a sound if enabled
                # write to the log
                if self.raidfinder.settings['time']:
                    if self.raidfinder.settings['jst']:
                        t = (created_at + datetime.timedelta(seconds=32400)).strftime("%H:%M:%S")
                    else:
                        t = created_at.strftime("%H:%M:%S UTC")
                else:
                    if self.raidfinder.settings['jst']:
                        t = (datetime.datetime.utcnow() + datetime.timedelta(seconds=32400)).strftime("%H:%M:%S JST")
                    else:
                        t = datetime.datetime.now().strftime("%H:%M:%S")
                dupes.add(code)
                self.raidfinder.secondcode = self.raidfinder.lastcode
                self.raidfinder.lastcode = code
                self.raidfinder.log.push('[{}] {} : {} {} {}'.format(t, r, code, lg, comment))
                
                if len(dupes) >= 500:
                    keep = list(dupes)
                    dupes = set()
                    for i in range(250, len(keep)):
                        dupes.add(keep[i])
            except Exception as te:
                print("TEST:", data)

###########################################################################################################################
# Custom UI ToolTip
###########################################################################################################################
class Tooltip():
    def __init__(self, parent, raidfinder, translate_key): # create a tooltip for the parent widget, with the associated text
        self.parent = parent
        self.raidfinder = raidfinder
        self.tip = None
        self.text = raidfinder.getString(translate_key)
        if parent:
            self.parent.bind('<Enter>', self.show) # bind to hover
            self.parent.bind('<Leave>', self.hide) # bind to not-hover

    def show(self, event): # called by the enter event, show the text
        if not self.raidfinder.settings.get('tooltip', True) or self.tip or not self.text: # don't show twice or if no text
            return
        x, y, cx, cy = self.parent.bbox("insert") # bound box
        x = x + self.parent.winfo_rootx()
        y = y + cy + self.parent.winfo_rooty() + 40 # 40px lower
        self.tip = Tk.Toplevel(self.parent)
        self.tip.wm_overrideredirect(1)
        self.tip.wm_geometry("+%d+%d" % (x, y))
        label = Tk.Label(self.tip, text=self.text, justify=Tk.LEFT, background="#ffffe0", relief=Tk.SOLID, borderwidth=1)
        label.pack(ipadx=1)

    def hide(self, event): # called by the leave event, destroy the label
        tmp = self.tip
        self.tip = None
        if tmp: tmp.destroy()

###########################################################################################################################
# UI
###########################################################################################################################
class UI(Tk.Tk):
    def __init__(self, raidfinder): # the UI is built here
        Tk.Tk.__init__(self,None)
        # variables
        self.parent = None
        self.raidfinder = raidfinder # Raidfinder class
        self.tracking = {}
        self.readonly = {}
        self.iconbitmap('favicon.ico')
        self.inputting = False
        self.mainsett = []
        self.advsett = []
        self.lang_var = Tk.StringVar()
        try: self.lang_var.set(self.raidfinder.langs[self.raidfinder.settings.get('lang', 'en.json')])
        except: pass

        COLUMNSPAN = 4

        # building the UI
        ## raid part
        mainframes = []
        s = ttk.Separator(self, orient=Tk.HORIZONTAL)
        s.grid(row=0, column=0, columnspan=COLUMNSPAN, sticky="we")
        self.raidframe = ttk.Notebook(self)
        mainframes.append(self.raidframe)
        mainframes[-1].grid(row=1, column=0, columnspan=COLUMNSPAN, sticky="we")
        self.raids = [] # empty for now
        self.raidchilds = []
        self.custom = []
        self.decorators = []
        
        ## tweet filter
        mainframes.append(ttk.Frame(self))
        mainframes[-1].grid(row=2, column=0, rowspan=1, columnspan=COLUMNSPAN, sticky="we")
        self.filterlabel = Tk.Label(mainframes[-1], text=self.raidfinder.getString("filter"))
        self.filterlabel.pack(side=Tk.LEFT)
        Tooltip(self.filterlabel, self.raidfinder, "filter_desc")
        self.filterlabeloriginal = self.filterlabel.cget("background")
        self.filter=Tk.Text(mainframes[-1], height=1, width=35)
        self.filter.pack(side=Tk.LEFT, fill=Tk.X)
        self.filter.insert(Tk.END, self.raidfinder.filter)
        self.filter.bind("<FocusIn>", self.focusin)
        self.filter.bind("<FocusOut>", self.focusout)
        self.filter.bind('<<Modified>>', self.updateFilter)
        self.filterModified = False
        ttk.Separator(mainframes[-1], orient=Tk.HORIZONTAL).pack(side=Tk.BOTTOM, fill=Tk.X)

        ## main settings
        s = ttk.Separator(self, orient=Tk.HORIZONTAL)
        s.grid(row=3, column=0, columnspan=COLUMNSPAN, sticky="we")
        mainframes.append(ttk.Frame(self))
        mainframes[-1].grid(row=4, column=0, columnspan=COLUMNSPAN, sticky="we")
        self.mainsett_b = []
        for count, key in enumerate(["pause","jp","en","sound","copy"]):
            self.mainsett_b.append(Tk.Checkbutton(mainframes[-1], text="[{}] {}".format(count, self.raidfinder.getString("setting_" + key)), variable=self.newIntVar(self.mainsett, self.raidfinder.settings.get(key, 0)), command=lambda n=count, k=key: self.toggleSetting(n, k)))
            self.mainsett_b[-1].grid(row=1+count // 3, column=count % 3, sticky="ws")
            Tooltip(self.mainsett_b[-1], self.raidfinder, "setting_" + key + "_desc")
        count += 1
        self.mainsett_b.append(Tk.Button(mainframes[-1], text=self.raidfinder.getString("[{}] {}").format(count, self.raidfinder.getString("button_last")), command=self.copyLatest))
        self.lastSettingNum = count
        self.mainsett_b[-1].grid(row=1+count // 3, column=count % 3, sticky="ews")
        Tooltip(self.mainsett_b[-1], self.raidfinder, "button_last_desc")
        #### others
        self.statusLabel = Tk.Label(mainframes[-1], text=self.raidfinder.getString("offline"), bg='#edc7c7') # for the offline/online text
        self.statusLabel.grid(row=1, column=3, sticky="ews")
        Tooltip(self.statusLabel, self.raidfinder, "status_desc")
        self.timeLabel = Tk.Label(mainframes[-1], text="00:00:00") # for the current time
        self.timeLabel.grid(row=2, column=3, sticky="ews")
        Tooltip(self.timeLabel, self.raidfinder, "clock_desc")

        ## bottomn (log / advanced setting / stats)
        s = ttk.Separator(self, orient=Tk.HORIZONTAL)
        s.grid(row=5, column=0, columnspan=COLUMNSPAN, sticky="we")
        mainframes.append(ttk.Notebook(self))
        mainframes[-1].grid(row=6, column=0, columnspan=COLUMNSPAN, sticky="we")
        subtabs = []
        ### log
        subtabs.append(ttk.Frame(mainframes[-1]))
        mainframes[-1].add(subtabs[-1], text=self.raidfinder.getString('log'))
        scrollbar = Tk.Scrollbar(subtabs[-1]) # the scroll bar
        scrollbar.pack(side=Tk.RIGHT, fill=Tk.Y)
        self.logtext = Tk.Text(subtabs[-1], state=Tk.DISABLED, yscrollcommand=scrollbar.set, height=10, width=35, bg='#f8f8f8', wrap=Tk.WORD) # the log box itself, with a height limit
        self.logtext.pack(fill=Tk.BOTH, expand=1, side=Tk.LEFT)
        scrollbar.config(command=self.logtext.yview)
        ### advanced settings
        subtabs.append(Tk.Frame(mainframes[-1], bg='#dfe5d7')) # setting frame
        mainframes[-1].add(subtabs[-1], text=self.raidfinder.getString("advanced")) # tab
        ####### check buttons
        for count, val in enumerate([('dupe', 0, 0), ('jst', 1, 0), ('time', 2, 0), ('tooltip', 3, 0), ('update_raids', 4, 0), ('update_raidfinder', 5, 0), ('second', 0, 1), ('limit', 1, 1)]):
            b = Tk.Checkbutton(subtabs[-1], bg=subtabs[-1]['bg'], text=self.raidfinder.getString("setting_" + val[0]), variable=self.newIntVar(self.advsett, self.raidfinder.settings.get(val[0], 0)), command=lambda n=count, k=val[0]: self.toggleAdvSetting(n, k))
            b.grid(row=val[1], column=val[2], stick=Tk.W)
            Tooltip(b, self.raidfinder, "setting_" + val[0] + "_desc")
        ####### buttons
        for count, val in enumerate([('button_raidlist', 0, 2), ('button_version', 1, 2), ('button_github', 2, 2)]):
            b = Tk.Button(subtabs[-1], text=self.raidfinder.getString(val[0]), command=lambda n=count: self.buttonCallback(n))
            b.grid(row=val[1], column=val[2], sticky="ews")
            Tooltip(b, self.raidfinder, val[0] + '_desc')

        # language choice
        l = Tk.Label(subtabs[-1], bg=subtabs[-1]['bg'], text=self.raidfinder.getString('language')) # for the current time
        l.grid(row=3, column=2, sticky="wse")
        b = Tk.OptionMenu(subtabs[-1], self.lang_var, *list(self.raidfinder.langs.values()), command=self.lang_changed)
        b.grid(row=4, column=2, stick="ws")
        Tooltip(b, self.raidfinder, "lang_desc")

        ### stats
        # mostly text labels, you can skip over it
        subtabs.append(Tk.Frame(mainframes[-1], bg='#e5e0d7'))
        mainframes[-1].add(subtabs[-1], text=self.raidfinder.getString("stat"))
        self.stats = {}
        Tk.Button(subtabs[-1], text=self.raidfinder.getString("reset"), command=self.resetStats).grid(row=4, column=0, sticky="ews") # reset button
        # all stats to be displayed (Label Text, Position X, Position Y, Default Text)
        for count, val in enumerate([('stat_time', 0, 0, "0:00:00"), ('stat_received', 0, 1, "0"), ('stat_matched', 0, 2, "0"), ('stat_ratio', 0, 3, "0.00%"), ('stat_received_rate', 1, 1, "0/s"), ('stat_matched_rate', 1, 2, "0/s"), ('stat_dupes', 1, 0, "0"), ('stat_received_last',  2, 1, "?"), ('stat_matched_last', 2, 2, "?"), ('stat_filter', 1, 3, "0"), ('stat_delay', 2, 3, "0s")]):
            b = Tk.Label(subtabs[-1], bg=subtabs[-1]['bg'], text=self.raidfinder.getString(val[0]))
            b.grid(row=val[2], column=val[1]*2, sticky="ws")
            Tooltip(b, self.raidfinder, val[0] + '_desc')
            self.stats[val[0]] = Tk.Label(subtabs[-1], bg=subtabs[-1]['bg'], text=val[3])
            self.stats[val[0]].grid(row=val[2], column=val[1]*2+1, sticky="nw")
            Tooltip(self.stats[val[0]], self.raidfinder, val[0] + '_desc')

        # make the window and bind the keyboard
        self.title(self.raidfinder.getString("title") + self.raidfinder.versions['raidfinder'])
        self.resizable(width=False, height=False) # not resizable
        self.protocol("WM_DELETE_WINDOW", self.close) # call close() if we close the window
        self.bind_all("<Key>", self.key)

    def close(self): # called by the app when closed
        self.raidfinder.saveSetting() # update config file
        self.raidfinder.apprunning = False
        self.destroy() # destroy the window

    def focusin(self, event): # event for managing a widget focus
        self.inputting = True

    def focusout(self, event): # event for managing a widget focus
        self.inputting = False

    def updateFilter(self, event):
        if not self.filterModified:
            self.raidfinder.filter = self.filter.get('0.0', 'end')[:-1]
        self.filterModified = not self.filterModified
        self.tk.call(self.filter, 'edit', 'modified', 0)

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
            self.toggleSetting(numKey, ["pause","jp","en","sound","copy"][numKey]) # call the event

    def toggleSetting(self, n, k): # called when un/checking a main setting
        state = self.mainsett[n].get()
        if k in self.raidfinder.settings:
            self.raidfinder.settings[k] = state
            if state: self.raidfinder.log.push(self.raidfinder.getString("setting_enable").format(self.raidfinder.getString("setting_"+k)))
            else: self.raidfinder.log.push(self.raidfinder.getString("setting_disable").format(self.raidfinder.getString("setting_"+k)))
            if k == 'pause':
                if state:
                    self.raidfinder.updateStreamTracking([])
                elif self.raidfinder.settings['limit']:
                    self.raidfinder.updateStreamTracking(list(self.raidfinder.tracked.keys()))
                else:
                    self.raidfinder.updateStreamTracking(self.raidfinder.raids['filters'])

    def toggleAdvSetting(self, n, k): # called when un/checking an advanced setting
        state = self.advsett[n].get()
        if k in self.raidfinder.settings:
            self.raidfinder.settings[k] = state
            if k == 'limit':
                if self.raidfinder.settings['pause']:
                    pass
                elif state:
                    self.raidfinder.updateStreamTracking(list(self.raidfinder.tracked.keys()))
                else:
                    self.raidfinder.updateStreamTracking(self.raidfinder.raids['filters'])

    def buttonCallback(self, n): # called when an advanced setting button is pressed
        if n == 0:
            if self.raidfinder.loadRaids():
                messagebox.showinfo("Info", self.raidfinder.getString("raid_reload"))
                self.raidfinder.updateStreamTracking([])
                self.reloadRaids(self.raidfinder.raids, self.raidfinder.custom)
            else:
                messagebox.showerror("Error", self.raidfinder.getString("raid_reload_err"))
        elif n == 1:
            webbrowser.open('https://github.com/MizaGBF/Raidfinder/archive/refs/heads/master.zip', new=2)
        elif n == 2:
            webbrowser.open('https://github.com/MizaGBF/Raidfinder', new=2)

    def copyLatest(self):
        code = self.raidfinder.lastCode()
        if code is not None:
            pyperclip.copy(code)
            self.raidfinder.log.push(self.raidfinder.getString("lastcode").format(code))

    def lang_changed(self, *args):
        messagebox.showinfo("Info", self.raidfinder.getString("lang_msg"))

    def resetStats(self): # simply reset the stats
        self.raidfinder.stats = {"stat_time":None, "stat_received":0, "stat_matched":0, "stat_dupes":0, "stat_filter":0 ,"stat_delay":0 ,"stat_received_last":None ,"stat_matched_last":None}

    def toggleRaid(self, r): # called when un/checking a raid
        state = self.tracking[r].get()
        self.readonly[r] = state
        tr = self.raidfinder.getString(r)
        if state:
            self.raidfinder.tracked[self.raidfinder.raids['en'][r]] = tr
            self.raidfinder.tracked[self.raidfinder.raids['jp'][r]] = tr
            self.raidfinder.log.push(self.raidfinder.getString('track_on').format(tr))
        else:
            self.raidfinder.tracked.pop(self.raidfinder.raids['en'][r], None)
            self.raidfinder.tracked.pop(self.raidfinder.raids['jp'][r], None)
            self.raidfinder.log.push(self.raidfinder.getString('track_off').format(tr))
        if self.raidfinder.settings['limit'] and not self.raidfinder.settings['pause']:
            self.raidfinder.updateStreamTracking(list(self.raidfinder.tracked.keys()))

    def editCustom(self, i): # called when editing a custom raid
        self.inputting = True # to disable the keyboard shortcuts
        tmp = self.raidfinder.settings['pause'] # save the pause setting
        self.raidfinder.settings['pause'] = True # pause the app
        self.raidfinder.updateStreamTracking([])
        customEntry = self.raidfinder.custom[i]
        v1 = simpledialog.askstring(self.raidfinder.getString("edit_custom"), self.raidfinder.getString( "edit_custom_subA"), initialvalue=customEntry[0]) # ask for user input
        if v1 == None: # if the user cancelled
            self.inputting = False
            self.raidfinder.settings['pause'] = tmp
            if not tmp:
                self.raidfinder.updateStreamTracking(list(self.raidfinder.tracked.keys()))
            return # we return
        v2 = simpledialog.askstring(self.raidfinder.getString("edit_custom"), self.raidfinder.getString( "edit_custom_subB"), initialvalue=customEntry[1])
        if v2 == None: # same thing
            self.inputting = False
            self.raidfinder.settings['pause'] = tmp
            if not tmp:
                self.raidfinder.updateStreamTracking(list(self.raidfinder.tracked.keys()))
            return
        v3 = simpledialog.askstring(self.raidfinder.getString("edit_custom"), self.raidfinder.getString( "edit_custom_subC"), initialvalue=customEntry[2])
        if v3 == None: # same thing
            self.inputting = False
            self.raidfinder.settings['pause'] = tmp
            if not tmp:
                self.raidfinder.updateStreamTracking(list(self.raidfinder.tracked.keys()))
            return
        self.inputting = False # re-enable keyboard shortcuts

        self.raidfinder.custom[i] = [v1, v2, v3] # save the user inputs
        self.raidfinder.settings['pause'] = tmp # restore the pause setting
        if self.raidfinder.loadRaids():
            self.raidfinder.updateStreamTracking([])
            self.reloadRaids(self.raidfinder.raids, self.raidfinder.custom)
        else:
            messagebox.showerror("Error", self.raidfinder.getString("raid_reload_err"))
            return

        # log and end
        self.raidfinder.log.push(self.raidfinder.getString("[System] {} saved in slot {}").format(v1, i+1)) # logging for the user to check any mistake
        self.raidfinder.log.push("EN : {}".format(v2))
        self.raidfinder.log.push("JP : {}".format(v3))

    def newIntVar(self, array, init=0): # used by setting checkboxes
        array.append(Tk.IntVar(value=init))
        return array[-1]

    def newTrackingVar(self, key): # used by raid checkboxes
        if key not in self.tracking:
             self.tracking[key] = Tk.IntVar(value=0)
             self.readonly[key] = 0
        return self.tracking[key]

    def formatStat(self, v):
        if v > 1000000: return str(v // 1000000) + "M"
        elif v > 1000: return str(v // 1000) + "K"
        return v

    def reloadRaids(self, raids, custom):
        # clean stuff
        for c in self.raidchilds:
             c.destroy()
        for p in self.custom:
             p.destroy()
        for p in self.raids:
             p.destroy()
        for d in self.decorators:
             p.destroy()
        self.tracking = {}
        # build the raid UI
        try:
            self.raids = []
            for p in raids['pages']: # for each page
                self.raids.append(Tk.Frame(self.raidframe, background=p.get('color', ''))) # make a tab
                self.raidframe.add(self.raids[-1], text=self.raidfinder.getString(p.get('name', '')))
                for d in p['decorator']:
                    self.decorators.append(ttk.Separator(self.raids[-1], orient=d['orient']))
                    self.decorators[-1].grid(row=d['posY'], column=d['posX'], columnspan=d.get('columnspan', 1), rowspan=d.get('rowspan', 1), sticky=d.get('sticky', ''))
            for k, v in raids['index'].items():
                self.raidchilds.append(Tk.Checkbutton(self.raids[v['page']], bg=raids['pages'][v['page']].get('color', ''), text=self.raidfinder.getString(k), variable=self.newTrackingVar(self.raidfinder.getString(k)), command=lambda r=self.raidfinder.getString(k): self.toggleRaid(r)))
                self.raidchilds[-1].grid(row=v.get('Y', 0), column=v.get('X', 0), stick=Tk.W)
            # add the custom tab
            self.custom = []
            for i in range(0, len(custom)): # same thing, with an extra Edit button
                self.raidchilds.append(Tk.Button(self.raids[-1], text=self.raidfinder.getString("button_edit"), command=lambda i=i: self.editCustom(i)))
                self.raidchilds[-1].grid(row=i%9, column=(i//9)*2, sticky='ews')
                Tooltip(self.raidchilds[-1], self.raidfinder, "button_edit_desc")
                self.custom.append(Tk.Checkbutton(self.raids[-1], bg=raids['pages'][-1].get('color', ''), text=custom[i][0], variable=self.newTrackingVar(custom[i][0]), command=lambda r=custom[i][0]: self.toggleRaid(r)))
                self.custom[-1].grid(row=i%9, column=1+(i//9)*2, stick=Tk.W)
            # select the last tab used
            self.raidframe.select(self.raidfinder.lasttab)
        except Exception as e:
            self.raidfinder.log.push(self.raidfinder.getString("err_reload_raid_ui_1"))
            self.raidfinder.log.push(self.raidfinder.getString("err_reload_raid_ui_2").format(e))
        self.raidfinder.tracked = {}

    def run(self): # update the UI
        # update the log
        if self.raidfinder.log is not None:
            lines = self.raidfinder.log.empty()
            self.logtext.configure(state="normal")
            for l in lines:
                self.logtext.insert(Tk.END, l+"\n")
                if self.raidfinder.log.size >= 200: self.logtext.delete(1.0, 2.0)
                else: self.raidfinder.log.size += 1
            self.logtext.configure(state="disabled") # back to read only
            self.logtext.yview(Tk.END) # to the end of the text

        # update the stats
        with self.raidfinder.statlock:
            if self.raidfinder.stats['stat_time'] is not None:
                self.stats['stat_time'].config(text="{}".format(datetime.timedelta(seconds=round(self.raidfinder.stats['stat_time'], 0))))
            else:
                self.stats['stat_time'].config(text="0:00:00")
            self.stats['stat_received'].config(text="{}".format(self.formatStat(self.raidfinder.stats['stat_received'])))
            self.stats['stat_matched'].config(text="{}".format(self.formatStat(self.raidfinder.stats['stat_matched'])))
            if self.raidfinder.stats['stat_received'] == 0: self.stats['stat_ratio'].config(text="0%")
            else: self.stats['stat_ratio'].config(text="{:.2f}%".format(100*self.raidfinder.stats['stat_matched']/self.raidfinder.stats['stat_received']))
            try: self.stats['stat_received_rate'].config(text="{:.2f}/s".format(self.raidfinder.stats['stat_received']/self.raidfinder.stats['stat_time']))
            except: self.stats['stat_received_rate'].config(text="0/s")
            try: self.stats['stat_matched_rate'].config(text="{:.2f}/s".format(self.raidfinder.stats['"stat_matched":0, ']/self.raidfinder.stats['stat_time']))
            except: self.stats['stat_matched_rate'].config(text="0/s")
            self.stats['stat_dupes'].config(text="{}".format(self.formatStat(self.raidfinder.stats['stat_dupes'])))
            if self.raidfinder.stats['stat_received_last'] is not None:
                self.stats['stat_received_last'].config(text="{:.2f}s".format(time.time() - self.raidfinder.stats['stat_received_last']))
            else: 
                self.stats['stat_received_last'].config(text="0.00s")
            if self.raidfinder.stats['stat_matched_last'] is not None:
                self.stats['stat_matched_last'].config(text="{:.2f}s".format(time.time() - self.raidfinder.stats['stat_matched_last']))
            else: 
                self.stats['stat_matched_last'].config(text="0.00s")
            self.stats['stat_delay'].config(text="{}s".format(self.raidfinder.stats['stat_delay']))
            self.stats['stat_filter'].config(text="{}".format(self.formatStat(self.raidfinder.stats['stat_filter'])))
        
        # update the time and online indicator
        if self.raidfinder.settings.get('jst', 1):
            d = datetime.datetime.utcnow() + datetime.timedelta(seconds=32400)
            self.timeLabel.config(text=d.strftime("%H:%M:%S JST"))
        else: self.timeLabel.config(text=time.strftime("%H:%M:%S"))
        
        if self.raidfinder.settings['pause']: self.statusLabel.config(text=self.raidfinder.getString("paused"), background='#edd7c7')
        elif self.raidfinder.connected: self.statusLabel.config(text=self.raidfinder.getString("online"), background='#c7edcd')
        else: self.statusLabel.config(text=self.raidfinder.getString("offline"), background='#edc7c7')

        if len(self.raidfinder.filter) > 0:
            self.filterlabel.config(background='#c7edcd')
        else:
            self.filterlabel.config(background=self.filterlabeloriginal)

        # update tkinter
        self.update()

###########################################################################################################################
# Entry Point
###########################################################################################################################
if __name__ == "__main__":
    r = Raidfinder(versions)
    r.run()