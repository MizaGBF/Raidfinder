Mod based on https://github.com/UmaiCake script

== INSTALLATION ==
1) Download and Install Python 2.7 https://www.python.org/
2) Click on the python script to start it (Required packages will be installed the first time, be patient)

== UPDATE THE PACKAGES ==
It may be good to update the used python modules from time to time (for reasons such a bugfixes).
Just run 'update_modules.py' to do it easily.
Don't panic if you see red messages.

== TWITTER KEYS ==
As of August 2018, Twitter changed their API and the way to request tokens for an application.
1) Go to https://developer.twitter.com/en/apply/account to apply for a Developper account.
You'll need a phone number linked to your account like in the past, but they also request a bit more informations to be sure you won't be misusing the API. You don't need to give personal informations.
2) Go to https://developer.twitter.com/en/apps to create a new App.
For the website URL, just put whatever you want (i.e. google.com), it doesn't matter.
Just ignore what isn't required.
3) In your app details, "Keys and tokens" tab, you'll find your consumer keys and access tokens (you may have to click create for these ones).
4) Put them into the 'gbfraidcopier.cfg' file
If you need to find your key later, the application you created should be listed at https://developer.twitter.com/en/apps

== USAGE ==
Just double click on 'gbfraidcopier.pyw', assuming you installed everything properly

== BLACKLIST ==
If you need to blacklist users, open blacklist.txt (create it if you deleted it or it's missing) and add the user twitter handle (without the @) in the file.
One handle by line.
You can also put your own twitter handle in, so you don't try to join your own raids by mistake.

== JSON ==
The 'raid.json' file is used to load all raids displayed on the ui and more. You can edit it to add/remove raids or change the presentation.

* The first array contains the raid list. Raids are loaded in order and displayed from left to right, top to bottom, up to 24 per tab. To skip a space, use the "dummy" keyword. To go early on the next tab, use the "next" keyword. The custom tab can't be modified.
* The second array contains data used to make the tab. A tab is composed of : color (in hexadecimal), name, number of labels at the top.

The custom tab is a special case, again. You can't set the number of labels at the top (as the number of raid is fixed) and it must always be the last one.
Always backup your file when editing. Also, if you encounter errors, check you didn't forget a comma between two objects.

== SOUND FILE (for Windows) ==
Just replace 'alert.wav' with another file if you want to change the sound effect.
It must be named 'alert.wav'

== CHROME EXTENSION ==
If you want to use the viramate auto-join feature, simply install the extension provided with this app.
Refer to manual.html for more informations.

== LINUX AND MAC ==
The installation should be similar.
I didn't test on linux and mac but the sound part shouldn't work because the winsound lib is only for windows.
I'm using beep for linux, install it with 'apt-get install beep' or whatever your install software is.
I have no solution for mac. Feel free to edit the script if you have one, though.

== TROUBLESHOOTING ==
* I'm using Python 3:
Add '#!/usr/bin/env python2' without the ' on the first line of gbfraidcopier.pyw (the 'coding: utf8' line will be second now).
Use notepad++ to edit the script.

* It doesn't start:
Make sure internet is working (the first time, it will download and install some needed modules).
If you are using Python 3, check above.
If you are using Python 2, something may be wrong with your installation (for example if you didn't install some of the optional modules coming with python).

Additionally, you can rename 'gbfraidcopier.pyw' into 'gbfraidcopier.py' to open the command prompt. An error message may appear on this.
You can also open a command prompt with shift + right click and start manually with the command "python gbfraidcopier.pyw". If python isn't in your PATH, you need to write its full path instead of just "python".

If you get the message "pip not found" the first time and it fails to install the other modules, install pip with this script: https://bootstrap.pypa.io/get-pip.py