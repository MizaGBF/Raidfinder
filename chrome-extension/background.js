chrome.browserAction.onClicked.addListener(function(activeTab)
{
    var newURL = "main.html";
    chrome.tabs.create({ url: newURL });
});