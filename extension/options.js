const url = document.querySelector('#url');
const status = document.querySelector('#status');
chrome.storage.local.get({ guidefoldUrl: 'http://127.0.0.1:4332' }).then(({ guidefoldUrl }) => { url.value = guidefoldUrl; });
document.querySelector('#save').addEventListener('click', async () => {
  try { await chrome.storage.local.set({ guidefoldUrl: new URL(url.value).origin }); status.textContent = 'Saved.'; }
  catch { status.textContent = 'Enter a valid Guidefold URL.'; }
});
