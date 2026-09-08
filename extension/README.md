# Guidefold GitHub Import extension

This is a Manifest V3 thin client. It opens the hosted Guidefold import flow; the browser never receives a GitHub client secret or repository token. Load `extension/` with **Load unpacked** in `chrome://extensions`.

The local flow uses Guidefold's existing session login. Production direct repository discovery requires a server-side GitHub App OAuth callback and repository reader. The callback must be registered exactly, and the server must exchange the authorization code and keep provider credentials server-side.

Configure the hosted URL from the extension's options page. No secret belongs in this directory or in `chrome.storage`.
