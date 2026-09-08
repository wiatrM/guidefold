const importButton = document.querySelector('#import');
const status = document.querySelector('#status');
importButton.addEventListener('click', async () => {
  importButton.disabled = true;
  status.textContent = 'Opening the secure Guidefold flow…';
  const { guidefoldUrl = 'http://127.0.0.1:4332' } = await chrome.storage.local.get('guidefoldUrl');
  await chrome.tabs.create({ url: `${guidefoldUrl.replace(/\/$/, '')}/import?step=login&source=extension` });
  window.close();
});
