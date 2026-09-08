from pathlib import Path
import shutil,json
src=Path('../pipeline-hifi');dst=Path('../../ui')
assert not dst.exists(),'ui already exists; do not overwrite'
(dst/'src/domain').mkdir(parents=True)
for name in ['domain.ts','global.css','App.module.css','Gallery.tsx','Gallery.module.css','main.tsx']:
 shutil.copy2(src/'src'/name,dst/'src'/name)
(dst/'src/tokens').mkdir()
shutil.copy2(src/'src/tokens.css',dst/'src/tokens/tokens.css')
shutil.copytree(src/'public',dst/'public')
for name in ['index.html','tsconfig.json']:shutil.copy2(src/name,dst/name)
p=dst/'src/main.tsx';p.write_text(p.read_text().replace("import './tokens.css'","import './tokens/tokens.css'"))
data=(src/'src/data.ts').read_text();diff=data[data.index('export function lineDiff'):];(dst/'src/domain/diff.ts').write_text(diff)
utils=data[data.index('export const bodyPrefix'):data.index('export function lineDiff')]
(dst/'src/domain/skill.ts').write_text("import type {Skill} from '../domain';\n"+utils)
names=['ActionButton','BrandMark','Panel','StateBadge','RouteState','Tabs','ProvenanceTrail','ScopeTree','DataTable','SkillDiff','MetricRow','Urn','SkillContent','Field']
(dst/'src/Shared.tsx').write_text('\n'.join("export {"+n+"} from './components/"+n+"';"for n in names)+'\n')
package=json.loads((src/'package.json').read_text());package['name']='guidefold-ui';package['scripts']={'dev':'vite --host 127.0.0.1 --port 4331','build':'tsc --noEmit && vite build','typecheck':'tsc --noEmit','preview':'vite preview --host 127.0.0.1 --port 4331','test':'vitest run','test:watch':'vitest','test:e2e':'playwright test','test:visual':'node qa/compare-gallery.mjs'}
package['devDependencies'].update({'vitest':'5.0.0','jsdom':'26.1.0','@testing-library/react':'16.3.3','@testing-library/user-event':'14.6.7','@testing-library/jest-dom':'7.0.1','@testing-library/dom':'10.4.1','@playwright/test':'1.63.0','axe-core':'4.13.0','pixelmatch':'7.1.0','pngjs':'7.0.0','@types/node':'22.19.15'})
(dst/'package.json').write_text(json.dumps(package,indent=2)+'\n')
(dst/'vite.config.ts').write_text("import {defineConfig} from 'vite';\nimport react from '@vitejs/plugin-react';\nexport default defineConfig({plugins:[react()],server:{host:'127.0.0.1',port:4331,strictPort:true},preview:{host:'127.0.0.1',port:4331,strictPort:true}});\n")
(dst/'vitest.config.ts').write_text("import {defineConfig} from 'vitest/config';\nimport react from '@vitejs/plugin-react';\nexport default defineConfig({plugins:[react()],test:{environment:'jsdom',setupFiles:['./src/test/setup.ts'],include:['src/**/*.test.{ts,tsx}'],css:true}});\n")
(dst/'src/test').mkdir();(dst/'src/test/setup.ts').write_text("import '@testing-library/jest-dom/vitest';\nimport {cleanup} from '@testing-library/react';\nimport {afterEach} from 'vitest';\nafterEach(()=>cleanup());\n")
(dst/'COMPONENT-CONTRACT.md').write_text("""# Extraction contract
Internal development coordination, stage 8; Meridian fixture only.
Root owns package/config/tokens/domain pure helpers/Gallery/QA. Port agent owns app/routes/data.
Component API and rendering match frozen hifi Shared.tsx. Each component gets index.tsx, Name.module.css, Name.test.tsx, Name.stories.tsx.
Imports: types from ../../domain; SkillDiff helper from ../../domain/diff. No component imports data.ts or JSON fixture.
Tests use Vitest, Testing Library, user-event; global cleanup already configured. Browser Router wrappers in tests/stories when links require them.
Stories are typed standard CSF objects with default {title,component}, named Fixture {args/render}; no Storybook runtime needed by the fixture gallery. Use actual fixture input imported ONLY in stories from ../../data/fixture.json.
CSS module must preserve source class rules relevant to the component, not copy all Shared CSS. All colors and dimensions use ../.. /tokens/tokens.css variables; no new raw sizes/colors outside tokens.
Do not modify frozen prototypes/pipeline-hifi/src or qa/baseline. Do not edit a neighbor's component or package/config.
""")
print('ui scaffold created; baseline remains independent')
