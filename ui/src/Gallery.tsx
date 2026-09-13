import {useState} from 'react';
import {ActionButton,BrandMark,Panel,StateBadge,RouteState,Tabs,ProvenanceTrail,ScopeTree,DataTable,SkillDiff,MetricRow,Urn,SkillContent,Field,PyramidChart,IconTile} from './Shared';
import {BooksIcon,GitPullRequestIcon,TreeStructureIcon,GithubLogoIcon,GitBranchIcon,CircleIcon} from '@phosphor-icons/react';
import {sampleCandidate,sampleCommit,sampleRepo,sampleSkill,sampleSkills,sampleSourceUrl} from './sample';
import {HeaderGlow,BorderBeam,ShineBorder,GlowSurface,GlowAction,ShaderField,GridField,NumberTicker,AnimatedList,Marquee,OrbitingCircles,AnimatedText,SuccessBurst,ShimmerSkeleton} from './components/effects';
import css from './Gallery.module.css';
export function ComponentGallery(){
 const [notice,setNotice]=useState(''),[reason,setReason]=useState('');
 const [replay,setReplay]=useState(0);
 const [success,setSuccess]=useState(false);
 const skill=sampleSkill,others=sampleSkills.slice(1),excerpt=skill.body.split('\n').slice(0,12).join('\n');
 const cases=[
 {name:'ActionButton',content:<div className={css.row}><ActionButton onClick={()=>setNotice('Decision saved in this browser only.')}>Inspect source</ActionButton><ActionButton tone="system" href="/library">Open Library</ActionButton><ActionButton tone="human" onClick={()=>setNotice('Decision saved in this browser only.')}>Record decision</ActionButton><ActionButton disabled>Export SKILL.md</ActionButton><p role="status">{notice}</p></div>},
 {name:'BrandMark',content:<BrandMark/>},
 {name:'IconTile',content:<div className={css.row}><IconTile icon={<BooksIcon weight="duotone"/>} size="sm"/><IconTile icon={<BooksIcon weight="duotone"/>}/><IconTile icon={<TreeStructureIcon weight="duotone"/>} size="lg" tone="human"/><IconTile icon={<GitPullRequestIcon weight="duotone"/>} size="xl" tone="neutral" label="Proposals"/></div>},
 {name:'Panel',content:<Panel title={skill.name} eyebrow="Exact imported revision"><p>{skill.description}</p></Panel>},
 {name:'StateBadge',content:<div className={css.row}><StateBadge>Unknown</StateBadge><StateBadge tone="system">{skill.sourceStatus}</StateBadge><StateBadge tone="human">Draft</StateBadge><StateBadge tone="warning">Partial</StateBadge><StateBadge tone="error">Could not load this view</StateBadge></div>},
 {name:'RouteState',content:<div className={css.stack}><RouteState state="empty" title="No observations" description="No adapter events or outcome assessments are available. Usefulness is Unknown."/><RouteState state="loading" title="Loading view" description="Waiting for the requested snapshot. No results are available yet."/><RouteState state="error" title="Could not load this view" description="No operation or publication is confirmed." action={<ActionButton>Retry view</ActionButton>}/></div>},
 {name:'Tabs',content:<Tabs label="Map axis" current="repository" items={[{id:'repository',label:'Repository',href:'/map?tab=repository'},{id:'scopes',label:'Scopes',href:'/map?tab=scopes'},{id:'pyramid',label:'Pyramid',href:'/map?tab=pyramid'}]}/>},
 {name:'ProvenanceTrail',content:<ProvenanceTrail entries={[{label:'Scope',value:skill.scope,code:true},{label:'Owner',value:skill.owner},{label:'Source path',value:skill.path,href:sampleSourceUrl(skill.path),code:true},{label:'Commit',value:sampleCommit,code:true}]}/>},
 {name:'ScopeTree',content:<ScopeTree label="Source excerpts" selected={skill.id} nodes={[{id:sampleRepo,label:sampleRepo,children:sampleSkills.map(s=>({id:s.id,label:s.name,detail:s.scope,href:'/skill?skill='+encodeURIComponent(s.id)}))}]}/>},
 {name:'DataTable',content:<DataTable caption="Sample source revisions" headings={['Skill','Scope','Source status']}>{sampleSkills.map(s=><tr key={s.id}><th scope="row">{s.name}</th><td>{s.scope}</td><td><StateBadge>{s.sourceStatus}</StateBadge></td></tr>)}</DataTable>},
 {name:'SkillDiff',content:<div className={css.stack}><SkillDiff source={skill.raw} candidate={skill.raw}/><SkillDiff source={skill.raw} candidate={sampleCandidate}/></div>},
 {name:'MetricRow',content:<MetricRow items={[{label:'Delivery',value:'Unknown',detail:'No adapter event ledger'},{label:'Helpfulness',value:'Unknown',detail:'No attributed assessments'},{label:'Observation coverage',value:'Unknown',detail:'Eligible episodes unavailable'}]}/>},
 {name:'Urn',content:<Urn value={skill.id}/>},
 {name:'SkillContent',content:<SkillContent content={excerpt}/>},
 {name:'Field',content:<Field id="gallery-reason" label="Reason for this decision" hint="Required for every decision." error={reason.trim()?undefined:'Choose a decision and explain your reason.'}><textarea id="gallery-reason" value={reason} onChange={e=>setReason(e.target.value)} /></Field>},
 {name:'PyramidChart',content:<PyramidChart selectedId={skill.id} bands={[
  {key:'abstract',label:'Abstract',description:'Concepts and domain knowledge',items:[{id:'parent',label:skill.scope}]},
  {key:'task',label:'Task',description:'Reusable capabilities and workflows',items:[{id:skill.id,label:skill.name,detail:skill.scope}]},
  {key:'atomic',label:'Atomic',description:'Concrete, executable elements',items:others.map(s=>({id:s.id,label:s.name}))},
 ]} edges={[{from:skill.id,to:'parent'},...others.map(s=>({from:s.id,to:skill.id}))]}/>},
 {name:'HeaderGlow',content:<HeaderGlow><IconTile icon={<BooksIcon weight="duotone"/>} size="lg"/></HeaderGlow>},
 {name:'BorderBeam',content:<BorderBeam><div className={css.demoPanel}><p>Skill library</p><p>Find an instruction and check its source, scope and revision.</p></div></BorderBeam>},
 {name:'ShineBorder',content:<div className={css.stack}><ShineBorder trigger={replay}><div className={css.demoPanel}><p>Import finished</p><p>4 skills added to the library.</p></div></ShineBorder><ActionButton onClick={()=>setReplay(r=>r+1)}>Replay sweep</ActionButton></div>},
 {name:'GlowSurface',content:<GlowSurface><div className={css.demoPanel}><p>Usage & quality</p><p>Hover to see the panel spotlight.</p></div></GlowSurface>},
 {name:'GlowAction',content:<div className={css.row}><GlowAction><ActionButton tone="human">Import repository</ActionButton></GlowAction><GlowAction tone="system"><ActionButton tone="system" href="/library">Open Library</ActionButton></GlowAction></div>},
 {name:'ShaderField',content:<div className={css.demoBox}><ShaderField/></div>},
 {name:'GridField',content:<div className={css.demoBox}><GridField/></div>},
 {name:'NumberTicker',content:<div className={css.row}><NumberTicker value={1284} suffix={' skills'}/><NumberTicker value={97} suffix="% coverage" locale/></div>},
 {name:'AnimatedList',content:<AnimatedList ariaLabel="Recent events" items={[{id:'e1',content:'Import finished: 4 skills added'},{id:'e2',content:'Sync started for wiatrM/guidefold'},{id:'e3',content:'Proposal opened for atlas.identity.turnstile'}]}/>},
 {name:'Marquee',content:<Marquee ariaLabel="Connected repositories">{sampleSkills.map(s=><span key={s.id} className={css.row}><GithubLogoIcon aria-hidden="true"/>{s.name}</span>)}</Marquee>},
 {name:'OrbitingCircles',content:<div className={css.demoOrbit}><OrbitingCircles center={<IconTile icon={<GitBranchIcon weight="duotone"/>} size="lg"/>} items={[<IconTile key="a" icon={<GithubLogoIcon weight="duotone"/>} size="sm" tone="neutral"/>,<IconTile key="b" icon={<CircleIcon weight="duotone"/>} size="sm" tone="human"/>,<IconTile key="c" icon={<BooksIcon weight="duotone"/>} size="sm"/>]}/></div>},
 {name:'AnimatedText',content:<AnimatedText text="Find an instruction and check its source, scope and revision."/>},
 {name:'SuccessBurst',content:<div className={css.stack}><SuccessBurst show={success} label="Import finished"/><ActionButton onClick={()=>setSuccess(s=>!s)}>{success?'Hide':'Show'} success moment</ActionButton></div>},
 {name:'ShimmerSkeleton',content:<ShimmerSkeleton lines={3}/>},
 ];
 return <main className={css.gallery} id="component-gallery"><header><h1>Component gallery</h1><p>Sample values from examples/monorepo. Component scenarios only. No product observations.</p><p>{sampleRepo}, source commit <code>{sampleCommit}</code></p></header>{cases.map(c=><section key={c.name} className={css.case} data-component={c.name} aria-labelledby={'case-'+c.name}><h2 id={'case-'+c.name}>{c.name}</h2><div>{c.content}</div></section>)}</main>;
}
