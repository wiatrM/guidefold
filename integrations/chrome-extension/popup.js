const GUIDEfold_APP = 'https://app.guidefold.dev';
const context = document.getElementById('context');
const open = document.getElementById('open');
let repository = null;

function githubRepository(url) {
  try {
    const parsed = new URL(url);
    if (parsed.hostname !== 'github.com') return null;
    const parts = parsed.pathname.split('/').filter(Boolean);
    if (parts.length < 2) return null;
    return parts[0] + '/' + parts[1].replace(/\.git$/, '');
  } catch { return null; }
}

chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
  repository = githubRepository(tabs[0]?.url || '');
  if (!repository) {
    context.textContent = 'Open a GitHub repository first.';
    return;
  }
  context.textContent = 'Repository: ' + repository;
  open.disabled = false;
});

open.addEventListener('click', () => {
  if (!repository) return;
  const target = GUIDEfold_APP + '/import?step=preview&source=github&repo=' + encodeURIComponent(repository);
  chrome.tabs.create({ url: target });
  window.close();
});
