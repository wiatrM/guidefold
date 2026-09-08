chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get('guidefoldUrl').then(({ guidefoldUrl }) => {
    if (!guidefoldUrl) chrome.storage.local.set({ guidefoldUrl: 'http://127.0.0.1:4332' });
  });
});
