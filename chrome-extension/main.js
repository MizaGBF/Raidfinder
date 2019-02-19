var apiUrl = "chrome-extension://fgpokpknehglcioijejfeebigdnbnokj/content/api.html"; // viramate api

var isApiLoaded = false;
var apiHost = null;
var pendingRequests = {};
var nextRequestId = 1;

var re = new RegExp('^([a-fA-F0-9]{8})');

var previousCode = "";
var BPrefill = false;

function onLoad () { // will be called once the DOM is loaded (see the last line)
    window.addEventListener("message", onMessage, false); // will listen to received message (from the viramate API)
    tryLoadApi(); // try to load
    window.setInterval(refreshCombatState, 1000); // will run this function once per second
};

function tryLoadApi () {
    console.log("Loading API");
    apiHost = document.querySelector("iframe#api_host");

    apiHost.addEventListener("load", onApiLoaded, false); // called once the api is loaded
    apiHost.src = apiUrl; // the loading happens
};

function onApiLoaded () {
    document.querySelector("span#api_status").textContent = "Connected and Running"; // set the status
    console.log("API loaded");
    isApiLoaded = true;
};

function onMessage (evt) {
    if (evt.data.type !== "result") // we only check result messages
        return;

    if (evt.data.result && evt.data.result.error) {
        document.querySelector("span#api_status").textContent = evt.data.result.error; // we change the text to the error message
        return;
    } else {
        document.querySelector("span#api_status").textContent = "Connected and Running"; // // everything is ok
    }

    var callback = pendingRequests[evt.data.id]; // check for message and call the callback function is any
    if (!callback)
        return;

    callback(evt.data.result);
};

function sendApiRequest (request, callback) { // to send a request to the viramate API
    if (!isApiLoaded) {
        console.log("API not loaded");
        callback({error: "api not loaded"});
        return;
    }

    var id = nextRequestId++;
    request.id = id;
    pendingRequests[id] = callback;

    apiHost.contentWindow.postMessage(
        request, "*"
    );
};

function getCode () { // check the clipboard for a raid code
    codeArea = document.createElement("textarea"); // textarea used to paste the clipboard content
    codeArea.style = "resize:none;margin:0;padding:0;outline:0;width:0px;height:0px";
    document.body.appendChild(codeArea); // append to the html

    var range = document.createRange(); // not sure if useful
    range.selectNode(codeArea); // select my invisible textarea
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    codeArea.focus(); // focus
    //codeArea.value = ""; // clear it (or codes will append to the past ones
    document.execCommand("Paste"); // paste
    var code = codeArea.value; // and read the content
    match = re.exec(code); // check if the code is valid

    codeArea. parentNode. removeChild(codeArea)

    if (match != null) { // if yes, we return
        return match[0];
    }
    else { // if not, we return an empty string
        return "";
    }
}

function updateCode(code) {
    previousCode = code; // and keep the new code in memory
    var previousCodeSpan = document.querySelector("span#previous_code"); // update the html span
    previousCodeSpan.textContent = previousCode;
}

function checkCode() {
    chrome.tabs.query({'active': true, 'lastFocusedWindow': true}, function (tabs) { // we query for the current tabs (kinda disgusting looking but it works)
        if (tabs === undefined || tabs.length == 0) { // if the tabs array is undefined or empty, we do nothing
            return;
        }
        var url = tabs[0].url;
        if (url.search("http://game.granbluefantasy.jp/#quest/supporter") == -1 // we do nothing if we are on these pages (summon screen)
            && url.search("http://game.granbluefantasy.jp/#raid") == -1 // (battle screen)
            && url.search("http://game.granbluefantasy.jp/#quest/assist/unclaimed") == -1 // (pending battles screen)
            && url.search("http://game.granbluefantasy.jp/#result") == -1 // (result screen)
            && url.search("http://game.granbluefantasy.jp/#arcarum2/supporter/") == -1 // (arcarum summon screen)
            && url.search("http://game.granbluefantasy.jp/#arcarum2/stage") == -1 // (arcarum loading screen)
            && url.search("http://game.granbluefantasy.jp/#quest/stage") == -1 // (loading screen)
            && url.search("http://game.granbluefantasy.jp") == 0) // and we must be on the game tab
        {
            var code = getCode(); // get the code in the clipboard
            if (code != "" && code != previousCode) { // if we have a valid code different of the previous one
                sendApiRequest({type: "tryJoinRaid", raidCode: code}, function (result) {
                    if (result == "ok") {
                        BPrefill = false;
                        updateCode(code);
                    }
                    else if (result == "popup: Check your pending battles.") { // go to pending battles
                        chrome.tabs.update(undefined, {url: 'http://game.granbluefantasy.jp/#quest/assist/unclaimed'}); // undefined = active tab
                    }
                    else if (result == "refill required") {
                        if (!BPrefill) {
                            chrome.tabs.executeScript(undefined, {code: "alert(\"Please refill your BP.\");"}); // undefined = active tab
                            BPrefill = true;
                            updateCode(code);
                        }
                    }
                    else if (result == "popup: You can only provide backup in up to three raid battles at once.") {
                        chrome.tabs.update(undefined, {url: 'http://game.granbluefantasy.jp/#quest/assist/unclaimed'}); // undefined = active tab
                        chrome.tabs.executeScript(undefined, {code: "alert(\"You can only provide backup in up to three raid battles at once.\");"}); // undefined = active tab
                    }
                    else if (result == "popup: This raid battle is full. You can't participate.") {
                        updateCode(code);
                    }
                    else if (result == "popup: The number that you entered doesn't match any battle.") {
                        updateCode(code);
                    }
                    else if (result == "no response from server") {
                        console.log(result);
                    }
                    else if (result == null) {
                        console.log("the return value is null"); 
                    }
                    else { // others
                        console.log(result);
                        updateCode(code);
                    }
                }); // send a request
            }
        }
    });
};

function refreshCombatState () { // not really used
    sendApiRequest({type: "getCombatState"}, function (combatState) {
        var raidCodeSpan = document.querySelector("span#current_raid_code");
        if (combatState) { // we are in a battle
            return; // we do nothing
        } else { // we aren't
            checkCode(); // we check the clipboard and try to join a raid
        }
    });
};

window.addEventListener("DOMContentLoaded", onLoad, false); // call onLoad once the DOM is loaded