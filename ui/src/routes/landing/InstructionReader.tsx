import {lazy,Suspense,useState} from 'react';
import {Tabs} from '@base-ui/react/tabs';
import {ArrowUpRight,FileText} from '@phosphor-icons/react';
import {CodeBlock} from '../../components/spectrumui/blocks/ai-assistants/code-block';
import {instruction,fixtureSource} from './instruction';
import css from './landing.module.css';

const SkillContent=lazy(()=>import('../../components/SkillContent').then(m=>({default:m.SkillContent})));

/**
 * One bordered panel, two tabs, one document. It shows the actual thing being sold - a
 * real SKILL.md from the Meridian example repository - and nothing else. The beam
 * frame, the search field and the five-rule sidebar are gone; what is left is the
 * reader, the source view and the link to the file itself.
 */
export function InstructionReader(){
 const [view,setView]=useState('reader');
 return <section className={css.reader} aria-labelledby="reader-label" data-slot="instruction-reader">
  <div className={css.readerHead}>
   <p id="reader-label" className={css.panelLabel}>Read a real one</p>
   <p className={css.panelSubtitle}><code>postgres-auth</code>, from the Meridian example repository in this project. Not a live run.</p>
  </div>
  <div className={css.readerBody}>
   <div className={css.readerBar}>
    <span className={css.readerFile}><FileText aria-hidden="true"/>postgres-auth<span className={css.extension}> / SKILL.md</span></span>
    <span className={css.badge}>Repository source</span>
   </div>
   <Tabs.Root value={view} onValueChange={value=>setView(String(value))} className={css.tabs}>
    <Tabs.List className={css.tabList} aria-label="Instruction format">
     <Tabs.Tab value="reader" className={css.tab}>Read instruction</Tabs.Tab>
     <Tabs.Tab value="source" className={css.tab}>Markdown source</Tabs.Tab>
     <Tabs.Indicator className={css.indicator}/>
    </Tabs.List>
    <Tabs.Panel value="reader" className={css.tabPanel}>
     <Suspense fallback={<p role="status">Loading instruction…</p>}><SkillContent content={instruction}/></Suspense>
    </Tabs.Panel>
    <Tabs.Panel value="source" className={css.tabPanel}>
     <CodeBlock code={instruction} filename="postgres-auth / SKILL.md" language="markdown" collapsedLines={5} variant="Numbered" className={css.code}/>
    </Tabs.Panel>
   </Tabs.Root>
   <a className={css.textLink} href={fixtureSource} target="_blank" rel="noreferrer">Open the original file <ArrowUpRight aria-hidden="true"/></a>
  </div>
 </section>;
}
