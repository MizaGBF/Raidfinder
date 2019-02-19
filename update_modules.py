# -*- coding: utf-8 -*-
import time

try:
    try:
        from pip import main as pipmain
    except:
        from pip._internal import main as pipmain
    hasPip = True
except ImportError:
    print "Error: pip not found"
    hasPip = False

if hasPip:
    try:
        pipmain(['install', 'ttk', '--upgrade'])
        pipmain(['install', 'tweepy', '--upgrade'])
        pipmain(['install', 'pyperclip', '--upgrade'])
        pipmain(['install', 'winsound', '--upgrade'])
        pipmain(['install', 'pip', '--upgrade'])
        print "Done!"
    except Exception, e:
        print "An issue occurred:"
        print e

print "Closing in 10 seconds"
time.sleep(10)