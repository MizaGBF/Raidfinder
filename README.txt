== INSTALLATION ==
1) Download and Install Python 3.10 or higher from https://www.python.org/ .
2) During the installation, leave the "install tkinter/ttk" option (or similar) enabled.
3) You are done.

Required modules will be installed/updated automatically on startup.
If it fails or you want to do it manually, run in a command prompt this command:
python -m pip install -r requirements.txt
in the folder where requiremnts.txt is.

== SET YOUR TOKEN ==
Before starting, close the Raidfinder if you haven't.
1) Go to https://developer.twitter.com/en/docs/developer-portal/overview
2) Sign in and fill the required informations (if asked)
3) In the Dashboard, go to your Projects (or Apps depending on what's displayed)
4) Click the Add App Button
5) Select Create New App
6) App Environment doesn't matter, pick whatever and click Next
7) Input an App Name
8) Copy the Bearer Token
9) Open the file 'gbfraidcopier.cfg' and paste the token after "bearer_token = ", under [Twitter]
Don't share this token with anyone.
If you need to, you can, in the project settings, revoke the token and generate a new one. You'll have to update the token in 'gbfraidcopier.cfg', if you do.

== TWITTER V2 LIMITS ==
IMPORTANT!!
The new Twitter API is quite limited:
- 500,000 tweets per month
- 5 rules (search queries) of 512 characters each
For this reason, a new setting has been added to limit tweet usage. It's enabled by default and I don't recommend turning it off.
If you happen to have an elevated Dev Account (or higher tier), you can raise the 5 rules and 512 characters limitations in 'gbfraidcopier.cfg'.
Refer to https://developer.twitter.com/en/docs/twitter-api/tweets/filtered-stream/api-reference/post-tweets-search-stream-rules

== UPDATE THE RAIDFINDER ==
Download the latest version and overwrite the files with the new ones.
Alternatively, make a new folder BUT KEEP gbfraidcopier.cfg to not lose your settings, and delete the old files.

== UPDATE THE RAID LIST ==
Simply grab the latest raid.json file from Github or the download folder and replace it.

== MODDING ==
The following explanations are for modding the raidfinder.
Relevant resources: https://www.json.org/json-en.html

== CUSTOM LANGUAGE ==
To add a new language, make a new JSON file in the "lang" folder.
Make sure the file is saved as UTF-8 encoded.
You can also copy and edit an existing one.
The JSON object is structured as follow:
{
  "key": "translated string",
  ...
}
"key" are keywords used in the code and "translated string" will be what appear when the "key" is encountered.
For example, the Reset button has the key "reset". Translating it in french would be adding "reset": "Réinitialiser",
To translate Raid page names, the key to set is the Page name set in raid.json (see below).
In the same way, to translate raid name, the key to set is the Raid name.
Check jp.json to see how the raid names are translated in japanese.

== CUSTOM RAID LIST ==
You can edit the raid.json to change how the raid list is displayed.
First, make sure to disable auto updates to not lose your custom raid.json.
The JSON object is structured as follow:
{
  "filters" : ["english_filter", "japanese_filter"],
  "custom color": "custom page background color in hexadecimal",
  "pages": [
    {
      "name": "Page name",
      "color": "page background color in hexadecimal",
      "list": [
        {
          "name": "Raid Name",
          "en": "English Code",
          "jp": "Japanese Code",
          "posX": "Horizontal Position on the UI",
          "posY": "Vertical Position on the UI"
        },
      ],
      "decorator": [
      ]
    }
    ...
  ]
}

"filters" is the base filter used when the tweet usage limit is off, it's also here for backward compatibility with older versions.
To generate color codes, just google "color picker", get the color you want and grab the EX code (example: #71eb34).
"decorator" is used to add lines, to make the UI fanciers.