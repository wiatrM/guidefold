from pathlib import Path
p=Path('../pipeline-hifi/src/app.tsx');s=p.read_text()
start=s.index('<nav className={css.navigation}')
end=s.index('</nav>',start)+len('</nav>')
nav=s[start:end]
s=s[:start]+'<div className={css.desktopNavigation}>'+nav+'</div><details className={css.mobileNavigation}><summary>Navigate · {viewInfo[view].label}</summary>'+nav+'</details>'+s[end:]
p.write_text(s)
p=Path('../pipeline-hifi/src/tokens.css');s=p.read_text().replace('--rail-width:216px;','--desktop-display:block; --mobile-display:none; --rail-padding:24px 16px; --context-padding:16px 0; --rail-width:216px;')
s=s.replace('@media(max-width:720px){:root{','@media(max-width:720px){:root{--desktop-display:none;--mobile-display:block;--rail-padding:16px;--context-padding:8px 0;')
p.write_text(s)
p=Path('../pipeline-hifi/src/App.module.css');s=p.read_text().replace('padding:var(--space-4) var(--space-3);border-right','padding:var(--rail-padding);border-right').replace('.edition{','.edition{display:var(--desktop-display);').replace('padding:var(--space-3) var(--zero);font-size','padding:var(--context-padding);font-size').replace('.railFoot{display:flex;','.railFoot{display:var(--desktop-display);')
s+='\n.desktopNavigation{display:var(--desktop-display);}.mobileNavigation{display:var(--mobile-display);margin-top:var(--space-2);}.mobileNavigation summary{padding:var(--space-2);border:var(--border-width) solid var(--control-border);border-radius:var(--radius);color:var(--system-ink);}.mobileNavigation[open] summary{color:var(--stone-100);}\n'
p.write_text(s)
