/**
 * Reproduce the authored UI copy inventory without rendering data/fixture.json.
 * Run from the repository root:
 *   node prototypes/pipeline-tools/inventory-hifi-copy.mjs
 * Uses the TypeScript 7 AST API already installed by pipeline-hifi; no extra deps.
 * Classification is syntactic and accompanied by an excluded-literal ledger.
 * The synthetic editorial verdicts are a recorded review, not a claim of audio
 * playback, speech recognition, human research, or automatic language quality.
 */
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {resolve,dirname,relative} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {API} from '../pipeline-hifi/node_modules/typescript/dist/api/sync/api.js';
import {SyntaxKind as K} from '../pipeline-hifi/node_modules/typescript/dist/ast/index.js';

const repo=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const app=resolve(repo,'prototypes/pipeline-hifi');
const api=new API();
const snapshot=api.updateSnapshot({openProjects:[resolve(app,'tsconfig.json')]});
const project=snapshot.getProject(resolve(app,'tsconfig.json'));
if(!project)throw new Error('TypeScript project unavailable; run pnpm install in pipeline-hifi.');
const files=[];
async function walk(path){for(const e of await readdir(path,{withFileTypes:true})){const p=resolve(path,e.name);if(e.isDirectory())await walk(p);else if(e.name.endsWith('.tsx')||e.name==='data.ts')files.push(p);}}
await walk(resolve(app,'src'));
files.sort();
const entries=[],excluded=[],sources=[];
let previousReport={entries:[]};
try{previousReport=JSON.parse(await readFile(resolve(app,'qa/copy-review.json'),'utf8'));}catch{}
const reviewedCopy=new Map(previousReport.entries.filter(e=>e.readAloud?.verdict!=='requires editorial review').map(e=>[e.text,e.readAloud]));

const normalize=s=>s.replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/\s+/g,' ').trim();
const visibleAttrs=new Set(['title','description','label','hint','error','placeholder','alt','aria-label','caption','headings','eyebrow']);
const visibleFields=new Set(['label','title','description','detail','caption','headings','eyebrow','hint','error','message']);
const visibleMaps=new Set(['stageNames','jumpLabels','evidenceRows','originNames','steps','filterFields','decisionOptions','importCommands','commands','viewInfo','empty']);
const messageCalls=/^(set(?:Status|Notice|Error|Message|MemberError|MemberStatus|IntegrationStatus)|fail)$/;
const semanticTags=new Set(['p','button','a','Link','ActionButton','summary','h1','h2','h3','h4','h5','h6','legend','label','dt','dd','td','th','li','small','span','StateBadge','strong','code','pre','option','footer']);
function ancestry(node){const items=[];for(let p=node.parent;p&&p!==node;p=p.parent){items.push(p);if(p.kind===K.SourceFile)break;}return items;}
function varName(node){const a=[node,...ancestry(node)].find(p=>p.kind===K.VariableDeclaration);return a?.name?.getText()||'';}
function property(node){return [node,...ancestry(node)].find(p=>p.kind===K.PropertyAssignment);}
function attribute(node){return [node,...ancestry(node)].find(p=>p.kind===K.JsxAttribute);}
function callName(node){const call=ancestry(node).find(p=>p.kind===K.CallExpression);return call?.expression?.getText()||'';}
function nameOf(node){return node?.name?.getText().replace(/^['"]|['"]$/g,'')||'';}
function elementName(node){return node?.openingElement?.tagName?.getText()||node?.tagName?.getText()||'';}
function surface(node){
 const a=attribute(node);
 if(a)return 'attribute:'+nameOf(a);
 const p=property(node);if(p)return 'data-field:'+nameOf(p);
 const v=varName(node);if(v)return 'copy-map:'+v;
 return ancestry(node).find(p=>p.kind===K.JsxElement)?'rendered-branch':'message';
}
function classify(node,text,file){
 const ancestors=ancestry(node);
 if(!normalize(text))return 'empty or whitespace';
 if(ancestors.some(p=>[K.ImportDeclaration,K.ExportDeclaration,K.ImportType,K.LiteralType,K.TypeAliasDeclaration,K.InterfaceDeclaration].includes(p.kind)))return 'module or type syntax';
 if(node.parent?.kind===K.PropertyAssignment&&node.parent.name===node)return 'object key';
 if(node.parent?.kind===K.BinaryExpression&&['===','!==','==','!='].includes(node.parent.operatorToken?.getText()))return 'comparison value';
 const attr=attribute(node);
 const nearestCall=callName(node);
 if(nearestCall.endsWith('.join')||nearestCall.endsWith('.split')||nearestCall.endsWith('.toLocaleString'))return 'formatting helper argument';
 if(messageCalls.test(nearestCall))return null;
 const attrIndex=attr?ancestors.indexOf(attr):-1;
 const nestedRender=attrIndex>=0&&ancestors.slice(0,attrIndex).some(p=>p.kind===K.JsxElement);
 const propEarly=property(node),propName=nameOf(propEarly);
 const structured=attr&&['entries','items'].includes(nameOf(attr));
 if(structured&&visibleFields.has(propName))return null;
 if(structured&&propName==='value'&&!/\.get$|\.set$/.test(nearestCall))return null;
 if(attr&&!visibleAttrs.has(nameOf(attr))&&!nestedRender&&!structured)return 'non-copy JSX attribute '+nameOf(attr);
 if(file.endsWith('/data.ts'))return text==='No text changes'?null:'data helper or diff syntax';
 // Values compared with state, paths or identifiers select a branch; they are not copy.
 if(node.parent?.kind===K.BinaryExpression&&['===','!==','==','!='].includes(node.parent.operatorToken?.getText()))return 'comparison value';
 if(node.parent?.kind===K.ElementAccessExpression&&node.parent.argumentExpression===node)return 'object lookup key';
 if(attr&&visibleAttrs.has(nameOf(attr)))return null;
 const call=callName(node);
 if(messageCalls.test(call))return null;
 if(call==='useState'&&normalize(text))return /^[A-Z]/.test(text)?null:'state identifier';
 if(call==='setProvider')return 'provider state identifier (visible label inventoried separately)';
 if(call==='setAttribute'||call==='document.createElement'||call==='document.execCommand'||call==='document.getElementById')return 'DOM operation syntax';
 if(call==='ctx.href'||call==='ctx.go'||call==='ctx.save'||/\.get$|\.set$|\.has$|\.delete$/.test(call))return 'routing, form or storage syntax';
 const prop=property(node),pn=nameOf(prop);
 if(visibleFields.has(pn))return null;
 if(pn==='value'&&ancestors.some(p=>p.kind===K.JsxAttribute&&nameOf(p)==='entries'))return null;
 if(pn==='value'&&ancestors.some(p=>p.kind===K.PropertyAssignment&&nameOf(p)==='entries'))return null;
 if(pn==='value'&&ancestors.some(p=>p.kind===K.JsxElement||p.kind===K.JsxSelfClosingElement)&&!['approve','edit','reject'].includes(text))return null;
 const variable=varName(node);
 if(variable==='subject')return null;
 if(ancestry(node).some(p=>p.kind===K.BinaryExpression&&p.left?.getText()==='document.title'))return null;
 if(visibleMaps.has(variable)&&!['id','key','field','view','params','value','step','tab','from','return_tab','role'].includes(pn))return null;
 if(['requires','refines'].includes(text)&&node.parent?.kind===K.ArrayLiteralExpression&&file.endsWith('CatalogRoutes.tsx'))return null;
 if(ancestors.some(p=>p.kind===K.JsxExpression)){
   if(/^[\s/+:#.,·−-]*$/.test(text))return 'joiner or punctuation (retained in contextual template)';
   // Nested state arrays/param keys are excluded; output branches and fallbacks remain.
   if(node.parent?.kind===K.ArrayLiteralExpression&&!ancestors.some(p=>p.kind===K.JsxAttribute&&visibleAttrs.has(nameOf(p))))return 'control array (labels inventoried separately)';
   if(node.parent?.kind===K.CallExpression&&!['setNotice','setStatus','setMessage','setError','setMemberError','setMemberStatus','setIntegrationStatus'].includes(call))return 'helper call argument';
   if(['neutral','human','system','warning','error','ready','partial','degraded','restricted','loading','empty','step','page','polite','true','false'].includes(text))return 'state, style or ARIA token';
   if(pn&&['id','href','key','from','return_tab','tab','skill','scope','state','stage','type','role'].includes(pn))return 'configuration identifier';
   return null;
 }
 if(variable==='message')return null;
 if(variable==='commands'||variable==='importCommands')return null;
 return 'implementation literal';
}
function spokenContext(node){
 let el=ancestry(node).find(p=>p.kind===K.JsxElement&&semanticTags.has(elementName(p)));
 if(!el)return undefined;
 const slots=[];
 function flatten(p){
  if(p.kind===K.JsxText)return p.text;
  if(p.kind===K.JsxExpression){
   if(!p.expression)return '';
   const exp=p.expression;
   if(exp.kind===K.StringLiteral||exp.kind===K.NoSubstitutionTemplateLiteral)return exp.text;
   const slot='runtime_'+(slots.length+1);slots.push({slot,expression:exp.getText()});return '{'+slot+'}';
  }
  if(p.kind===K.JsxElement||p.kind===K.JsxFragment)return (p.children||[]).map(flatten).join('');
  return '';
 }
 return {tag:elementName(el),template:normalize(flatten(el)),interpolations:slots};
}
const findings=[
 {id:'copy-01',priority:'P2',match:'Simulate member invitation',suggestion:'Add local member',reason:'The action adds a local label and sends no invitation; name the actual result.'},
 {id:'copy-02',priority:'P2',match:'Review the existing source as a package candidate. This fixture introduces no new procedure and claims no source problem.',suggestion:'Review the existing skill file as a candidate revision. This fixture introduces no new procedure and claims no source problem.',reason:'Only SKILL.md is exported; package candidate overstates the artifact.'},
 {id:'copy-03',priority:'P2',match:'Source author: fixture · Viewer: Fixture operator (',suggestion:'Source: Meridian fixture · Reviewer: Fixture operator (',reason:'A fixture is a data source, not an identified source author.'},
 {id:'copy-04',priority:'P3',match:'This exercise stores one boolean scenario value.',suggestion:'Use this local exercise to preview token creation and revocation.',reason:'State representation is an implementation detail; explain the user-visible exercise.'}
];
function add(node,text,file,kind){
 const clean=normalize(text);if(!clean)return;
 const sf=node.getSourceFile();
 const pos=node.getStart(sf),line=sf.text.slice(0,pos).split('\n').length;
 const source={file:relative(repo,file).replaceAll('\\','/'),line,offset:pos};
 const finding=findings.find(f=>clean.includes(f.match));
 const recorded=reviewedCopy.has(clean)||findings.some(f=>clean.includes(f.suggestion))||['requires','refines'].includes(clean);
 const technical=/SHA-256|SKILL\.md|CODEOWNERS|download_verified|context_loaded|^requires$|^refines$|URN|^guidefold /.test(clean);
 const context=messageCalls.test(callName(node))?undefined:spokenContext(node);
 entries.push({
  id:createHash('sha256').update(source.file+':'+pos+':'+clean).digest('hex').slice(0,12),
  ...source,kind,text:clean,sourceText:text,surface:node.kind===K.JsxText?'rendered text':surface(node),
  ...(context?{readAloudContext:context}:{}),
  runtimeInterpolation:node.kind===K.TemplateExpression||!!context?.interpolations.length,
  readAloud:{
   method:'synthetic editorial read-through in rendered sentence context; no audio playback or human participant',
   ...(technical?{pronunciation:clean.replaceAll('SHA-256','S H A two fifty-six').replaceAll('SKILL.md','skill dot M D').replaceAll('CODEOWNERS','code owners').replaceAll('download_verified','download verified').replaceAll('context_loaded','context loaded').replaceAll('URN','U R N')}:{}),
   verdict:finding?'revise':!recorded?'requires editorial review':technical?'clear technical label':'clear in context',
   rationale:finding?.reason||(!recorded?'New or changed copy has not yet received an editorial verdict.':technical?'Keep exact domain/file/event terminology; surrounding text explains the meaning.':'Action, object and local-simulation status are understandable when read with adjacent text and runtime values.'),
   ...(finding?{finding:finding.id,suggestedText:finding.suggestion}:{})
  }
 });
}
try{
 for(const file of files){
  const raw=await readFile(file,'utf8'),sf=project.program.getSourceFile(file);
  if(!sf)throw new Error('Missing AST: '+file);
  sources.push({file:relative(repo,file).replaceAll('\\','/'),sha256:createHash('sha256').update(raw).digest('hex')});
  function visit(node){
   if(node.kind===K.JsxText){add(node,node.text,file,'JSX text fragment');}
   else if(node.kind===K.StringLiteral||node.kind===K.NoSubstitutionTemplateLiteral||node.kind===K.TemplateExpression){
    const text=node.kind===K.TemplateExpression?node.getText().slice(1,-1):(node.text??'');
    const why=classify(node,text,file);
    if(why){if(normalize(text))excluded.push({file:relative(repo,file).replaceAll('\\','/'),line:raw.slice(0,node.getStart(sf)).split('\n').length,text:normalize(text),reason:why});}
    else add(node,text,file,node.kind===K.TemplateExpression?'runtime template':'string literal');
   }
   node.forEachChild(visit);
  }
  visit(sf);
 }
}finally{snapshot.dispose();api.close();}
const openFindings=findings.map(f=>({...f,status:entries.some(e=>e.readAloud.finding===f.id)?'open':'resolved in current source',replacementObserved:entries.some(e=>e.text.includes(f.suggestion))}));
const report={
 schemaVersion:1,reviewDate:'2026-09-06',stage:6,
 purpose:'Exhaustive authored UI-copy inventory across TSX branches plus data.ts static messages.',
 methodology:{
  extraction:'TypeScript AST scans every TSX source and data.ts. Includes JSX text, visible/accessibility attributes, copy-map literals, status/errors, lifecycle alternatives and runtime templates. Non-copy literals are retained in an exclusion ledger.',
  review:'Synthetic editorial read-aloud simulation: recorded verdicts evaluate the sentence/control context, action/object clarity, exact technical names and fixture-vs-production truthfulness. No human audio session was conducted. Regeneration preserves recorded exact-text verdicts from this report and flags new copy as requires editorial review; accepted finding replacements are pre-reviewed.',
  runtime:'Expressions are marked as runtime values. Identifier/path/revision content comes from the fixture or user input; its formatting and interpolation context are reviewed, not invented values.',
  excluded:'Fixture Markdown procedures/raw files and fixture.json data are source content, not authored interface copy. CSS, imports, API identifiers, route keys, DOM/ARIA tokens and comparison values are excluded.',
  limits:'This is a source-complete editorial inventory, not evidence that every branch was exercised in a browser or that humans understood the copy. Browser QA and formal reviews remain separate.'
 },
 sources,totals:{authoredEntries:entries.length,unreviewedEntries:entries.filter(e=>e.readAloud.verdict==='requires editorial review').length,runtimeEntries:entries.filter(e=>e.runtimeInterpolation).length,excludedLiterals:excluded.length,openFindings:openFindings.filter(f=>f.status==='open').length},
 findings:openFindings,entries,excludedLiterals:excluded
};
await mkdir(resolve(app,'qa'),{recursive:true});
await writeFile(resolve(app,'qa/copy-review.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({output:'prototypes/pipeline-hifi/qa/copy-review.json',...report.totals,findings:openFindings},null,2));
