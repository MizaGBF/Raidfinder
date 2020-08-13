== PYTHON 2 USERS ==
If you were using the previous python 2 version, this one is now using python 3.
You might want to uninstall python2 before installing python 3, as coexisting python installations can be a big pain in the butt.
(It will also fix your file association in windows explorer)

== INSTALLATION ==
1) Download and Install Python 3.7 https://www.python.org/ (I haven't tested on a further version)
2) Open a command prompt and type: python --version
2a) If it doesn't work, you might have to replace "python" with the full path (example for me: C:\Python36\python.exe --version )
2b) If it doesn't show version 3-something but 2 instead, another version is causing conflict so use the full path as above, too.
3) now install the required modules (use the full path if needed):
python -m pip install pyperclip
python -m pip install tweepy

bonus: The command to update pip is:
python -m pip install --upgrade pip

== UPDATE THE PACKAGES ==
Same commands as during the installation process

== TWITTER KEYS ==
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
Alternatively on Windows, shift+right click in the folder > "Open a command prompt here" > type the command "python gbfraidcopier.pyw" without the quotes. If python isn't in your PATH, you need to write its full path instead of just "python".

== BLACKLIST ==
If you need to blacklist twitter users, open blacklist.txt (create it if you deleted it or it's missing) and add the user twitter handle (without the @) in the file.
One handle by line.
You can also put your own twitter handle in, so you don't try to join your own raids by mistake.

== JSON ==
The 'raid.json' file is used to load all raids displayed on the ui and more. You can edit it to add/remove raids or change the presentation.
Always backup your file when editing. Also, if you encounter errors, check you didn't forget a comma between two objects.

Quick explanation:
* "custom color" if the Custom tab background color
* A page correspond to a tab:
    * "name" is its name
    * "color" is its background color
    * "list" contains all the raids to be displayed in this tab
    * A raid in the "list" has 5 fields:
        * its "name"
        * its "english" and "japanese" codes
        * its position on the tab, "posX" being the horizontal position and "posY" the vertical one. Just imagine the tab is a 2D grid.

== SOUND FILE (for Windows) ==
Just replace 'alert.wav' with another file if you want to change the sound effect.
It must be named 'alert.wav'

== LINUX AND MAC ==
The installation should be similar.
I didn't test on linux and mac but the sound part shouldn't work because the winsound lib is only for windows.
I'm using beep for linux, install it with 'apt-get install beep' or whatever your install software is.
I have no solution for mac. Feel free to edit the script if you have one, though.

== TROUBLESHOOTING ==
You can rename 'gbfraidcopier.pyw' into 'gbfraidcopier.py' to open the command prompt. An error message may appear on this.
Alternatively on Windows, shift+right click in the folder > "Open a command prompt here" > type the command "python gbfraidcopier.pyw" without the quotes. If python isn't in your PATH, you need to write its full path instead of just "python".