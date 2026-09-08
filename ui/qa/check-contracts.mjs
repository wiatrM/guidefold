/**
 * Stage 8 source-contract check. Run: cd ui && node qa/check-contracts.mjs.
 * Checks authored source; browser/behavior/visual checks remain separate.
 */
import {readFile,writeFile,readdir,stat} from 'node:fs/promises';
import {resolve,dirname,relative,extname} from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {API} from '../node_modules/typescript/dist/api/sync/api.js';
import {SyntaxKind as K} from '../node_modules/typescript/dist/ast/index.js';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..'),src=resolve(root,'src');
const tokenFile=resolve(src,'tokens/tokens.css');
const expected=['ActionButton','BrandMark','Panel','StateBadge','RouteState','Tabs','ProvenanceTrail','ScopeTree','DataTable','SkillDiff','MetricRow','Urn','SkillContent','Field','PyramidChart'];
const diagnostics=[],components=[],imports=new Map(),inlineStyles=[];
const pathLabel=p=>relative(root,p).replaceAll('\\','/');
const issue=(file,line,rule,message)=>diagnostics.push({file:pathLabel(file),line,rule,message});
const lineAt=(text,offset)=>text.slice(0,offset).split('\n').length;
const files=[];
async function walk(dir){for(const item of await readdir(dir,{withFileTypes:true})){const file=resolve(dir,item.name);if(item.isDirectory())await walk(file);else files.push(file);}}
await walk(src);
files.sort();
const texts=new Map(await Promise.all(files.filter(p=>/\.(?:css|tsx?)$/.test(p)).map(async p=>[p,await readFile(p,'utf8')])));
const cssFiles=[...texts.keys()].filter(p=>p.endsWith('.css'));
const tokens=new Set([...texts.get(tokenFile).matchAll(/(--[\w-]+)\s*:/g)].map(m=>m[1]));

// Parse declarations independently of selectors, quoted strings, nested blocks and
// function arguments. Build/typecheck handles syntax validity; this reads values.
function cssDeclarations(text){
 const results=[];let start=0,quote='',escaped=false,comment=false,paren=0;
 for(let i=0;i<text.length;i++){
  const ch=text[i],next=text[i+1];
  if(comment){if(ch==='*'&&next==='/'){comment=false;i++;}continue;}
  if(quote){if(escaped)escaped=false;else if(ch==='\\')escaped=true;else if(ch===quote)quote='';continue;}
  if(ch==='/'&&next==='*'){comment=true;i++;continue;}
  if(ch==='"'||ch==="'"){quote=ch;continue;}
  if(ch==='('||ch==='['){paren++;continue;}if(ch===')'||ch===']'){paren--;continue;}
  if(paren===0&&['{','}',';'].includes(ch)){
   if(ch!=='{'){
    const raw=text.slice(start,i).replace(/\/\*[\s\S]*?\*\//g,'');
    const match=/^\s*([-\w]+)\s*:\s*([\s\S]*?)\s*$/.exec(raw);
    if(match)results.push({property:match[1],value:match[2],offset:start+text.slice(start,i).search(/\S|$/)});
   }
   start=i+1;
  }
 }
 return results;
}
function withoutFunctions(value,names){
 let out='';for(let i=0;i<value.length;){
  const match=/^([-\w]+)\(/.exec(value.slice(i));
  if(match&&names.includes(match[1].toLowerCase())){
   let depth=1,quote='',j=i+match[0].length;
   for(;j<value.length&&depth;j++){
    const c=value[j];if(quote){if(c==='\\')j++;else if(c===quote)quote='';continue;}
    if(c==='"'||c==="'")quote=c;else if(c==='(')depth++;else if(c===')')depth--;
   }
   const call=value.slice(i+match[0].length,j-1);let fallback='',nested=0;
   if(match[1].toLowerCase()==='var')for(let k=0;k<call.length;k++){if(call[k]==='(')nested++;else if(call[k]===')')nested--;else if(call[k]===','&&nested===0){fallback=call.slice(k+1);break;}}
   out+=' TOKEN '+(fallback?withoutFunctions(fallback,names):'');i=j;
  }else out+=value[i++];
 }return out;
}
const dimensionProperties=/^(?:(?:min|max)-)?(?:width|height|inline-size|block-size)$|^(?:margin|padding|inset|gap|row-gap|column-gap|top|right|bottom|left|border|outline|font-size|line-height|letter-spacing|word-spacing|text-indent|text-underline-offset|vertical-align|perspective|translate|rotate|scale|transform|background-size|background-position|object-position|flex-basis|scroll-margin|scroll-padding)/;
const colorProperties=/(?:color$|^(?:background|border|outline)(?:-|$)|^(?:fill|stroke|box-shadow|text-shadow|accent-color|caret-color)$)/;
const keywordColors=new Set(('aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue slategray slategrey snow springgreen steelblue tan teal thistle tomato transparent turquoise violet wheat white whitesmoke yellow yellowgreen').split(' '));
function literalIssues(property,value){
 const found=[],clean=withoutFunctions(value,['var','url']).replace(/"(?:\\.|[^"])*"|'(?:\\.|[^'])*'/g,'');
 const dimension=/(?<![\w-])[-+]?(?:\d*\.?\d+)(?:px|r?em|ex|ch|lh|rlh|vw|vh|vi|vb|vmin|vmax|svw|svh|lvw|lvh|dvw|dvh|cm|mm|in|pt|pc|q|fr|%|ms|s|deg|rad|turn)\b|(?<![\w-])[-+]?(?:\d*\.?\d+)%/ig;
 for(const m of clean.matchAll(dimension))found.push('literal dimension '+m[0]);
 if(/#[\da-f]{3,8}\b|\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)\s*\(/i.test(clean))found.push('literal color');
 if(colorProperties.test(property))for(const word of clean.toLowerCase().match(/[a-z]+/g)||[])if(keywordColors.has(word))found.push('literal color '+word);
 // Unitless grid line numbers, repeat counts, flex factors, opacity and z-index
 // are not dimensions. Zero lengths and typographic weights still need tokens.
 if(dimensionProperties.test(property)&&/(?<![\w.-])0(?:\.0+)?(?![\w.-])/.test(clean))found.push('literal zero length');
 if((property==='font-weight'||property==='font')&&/(?<![\w.-])(?:[1-9]\d{0,2}|1000)(?![\w.-])/.test(clean))found.push('literal font weight');
 if(property==='font-weight'&&/\b(?:normal|bold|bolder|lighter)\b/.test(clean))found.push('literal font weight');
 if(property==='line-height'&&/(?<![\w.-])(?:\d*\.)?\d+(?![\w.-])/.test(clean))found.push('literal line height');
 return [...new Set(found)];
}
function tokenRefs(value){return [...value.matchAll(/\bvar\(\s*(--[\w-]+)/g)].map(m=>m[1]);}
function checkValue(file,line,property,value,allowLiterals=false){
 for(const name of tokenRefs(value))if(!tokens.has(name))issue(file,line,'unresolved-token',property+': '+name+' is not declared in src/tokens/tokens.css');
 if(!allowLiterals)for(const detail of literalIssues(property,value))issue(file,line,'token-value',property+': '+value+' ('+detail+')');
}
// Small diagnostic-parser checks: ensure selector/index numbers cannot satisfy
// or break the contract, and actual hardcoded values / missing refs are detectable.
assert.equal(cssDeclarations('.x:nth-child(2){grid-column:1/-1;color:var(--ink);padding:8px;}').length,3);
assert.deepEqual(literalIssues('grid-column','1/-1'),[]);
assert.deepEqual(literalIssues('flex','1'),[]);
assert.deepEqual(literalIssues('padding','var(--space-2)'),[]);
assert.ok(literalIssues('padding','0 8px').length===2);
assert.ok(literalIssues('font-weight','600').length===1);
assert.ok(literalIssues('padding','var(--space, 8px)').length===1);
assert.ok(literalIssues('border-bottom','1px solid red').length===2);
assert.ok(literalIssues('background','linear-gradient(#fff, red)').length===2);
assert.deepEqual(tokenRefs('var(--missing, var(--fallback))'),['--missing','--fallback']);
for(const file of cssFiles){
 const text=texts.get(file);
 for(const declaration of cssDeclarations(text)){
  const line=lineAt(text,declaration.offset);
  if(file!==tokenFile&&declaration.property.startsWith('--'))issue(file,line,'token-location','Custom property '+declaration.property+' must be declared in src/tokens/tokens.css');
  checkValue(file,line,declaration.property,declaration.value,file===tokenFile);
 }
 if(file!==tokenFile)for(const m of text.matchAll(/@(?:media|container)[^{]*\{/g)){
  if(literalIssues('width',m[0]).length)issue(file,lineAt(text,m.index),'token-media','Literal responsive boundary must live in src/tokens/tokens.css: '+m[0].trim());
 }
}
const dirs=(await readdir(resolve(src,'components'),{withFileTypes:true})).filter(d=>d.isDirectory()).map(d=>d.name).sort();
if(dirs.length!==15)issue(resolve(src,'components'),1,'component-count','Expected exactly 15 public component directories; found '+dirs.length);
for(const name of dirs)if(!expected.includes(name))issue(resolve(src,'components',name),1,'component-name','Unexpected public component '+name);
for(const name of expected){
 const folder=resolve(src,'components',name),required=['index.tsx',name+'.module.css',name+'.test.tsx',name+'.stories.tsx'];
 const record={name,files:required.map(n=>pathLabel(resolve(folder,n))),scenarios:[]};
 for(const f of required)if(!texts.has(resolve(folder,f)))issue(resolve(folder,f),1,'component-file','Required component artifact is missing');
 components.push(record);
}

const api=new API(),snapshot=api.updateSnapshot({openProjects:[resolve(root,'tsconfig.json')]});
const project=snapshot.getProject(resolve(root,'tsconfig.json'));
if(!project)throw new Error('TypeScript project unavailable; run pnpm install in ui.');
function exported(node){return node.modifiers?.some(m=>m.kind===K.ExportKeyword);}
function propertyName(node){return node.name?.getText().replace(/^['"]|['"]$/g,'')||'';}
function kebab(name){return name.replace(/[A-Z]/g,c=>'-'+c.toLowerCase());}
try{
 for(const [file,text] of texts){
  if(!/\.tsx?$/.test(file))continue;
  const sf=project.program.getSourceFile(file);if(!sf)throw new Error('Missing TypeScript AST for '+pathLabel(file));
  const dependencies=[];
  function visit(node){
   if((node.kind===K.ImportDeclaration||node.kind===K.ExportDeclaration)&&node.moduleSpecifier?.text){
    const typeOnly=node.isTypeOnly||node.importClause?.isTypeOnly||
      (node.importClause?.namedBindings?.elements?.length&&!node.importClause.name&&node.importClause.namedBindings.elements.every(e=>e.isTypeOnly));
    dependencies.push({specifier:node.moduleSpecifier.text,typeOnly:!!typeOnly,line:lineAt(text,node.getStart(sf))});
   }
   if(node.kind===K.CallExpression&&[K.ImportKeyword].includes(node.expression?.kind)&&node.arguments?.[0]?.text)
    dependencies.push({specifier:node.arguments[0].text,typeOnly:false,line:lineAt(text,node.getStart(sf))});
   if(node.kind===K.JsxAttribute&&node.name?.getText()==='style'){
    const expression=node.initializer?.expression;
    const line=lineAt(text,node.getStart(sf));
    if(expression?.kind!==K.ObjectLiteralExpression)issue(file,line,'inline-style','A nonliteral style object needs an auditable local declaration; move visual values to CSS tokens.');
    else for(const prop of expression.properties){
     if(prop.kind!==K.PropertyAssignment){issue(file,line,'inline-style','Style spread or shorthand prevents value auditing; move styles to the CSS module.');continue;}
     const name=kebab(propertyName(prop)),value=prop.initializer;
     if([K.StringLiteral,K.NoSubstitutionTemplateLiteral,K.NumericLiteral].includes(value.kind)){
      checkValue(file,line,name,value.text);
      if(value.kind===K.NumericLiteral&&dimensionProperties.test(name)&&!['line-height'].includes(name)&&Number(value.text)!==0)issue(file,line,'token-value','Inline '+name+': '+value.text+' is a literal dimension; use a CSS token.');
     }
     else issue(file,line,'inline-style','Dynamic '+name+' is not a statically auditable token reference; use a CSS class/token.');
     inlineStyles.push({file:pathLabel(file),line,property:name});
    }
   }
   node.forEachChild(visit);
  }
  visit(sf);imports.set(file,dependencies);
  if(file.endsWith('.stories.tsx')){
   const name=relative(resolve(src,'components'),file).split(/[\\/]/)[0],record=components.find(c=>c.name===name);
   if(record){
    let hasDefault=false;
    for(const statement of sf.statements){
     if(statement.kind===K.ExportAssignment&&!statement.isExportEquals)hasDefault=true;
     if(exported(statement)&&statement.kind===K.VariableStatement)
      for(const declaration of statement.declarationList.declarations)if(declaration.initializer)record.scenarios.push(declaration.name.getText());
     if(exported(statement)&&statement.kind===K.FunctionDeclaration&&statement.body&&statement.name)record.scenarios.push(statement.name.getText());
    }
    if(!hasDefault)issue(file,1,'story-default','A standard CSF story needs a default component descriptor.');
    if(!record.scenarios.length)issue(file,1,'story-scenario','At least one initialized named story scenario must be exported.');
   }
  }
 }
}finally{snapshot.dispose();api.close();}
async function resolveModule(file,specifier){
 if(!specifier.startsWith('.'))return null;
 const target=resolve(dirname(file),specifier);
 for(const candidate of [target,target+'.ts',target+'.tsx',resolve(target,'index.ts'),resolve(target,'index.tsx')]){
  try{if((await stat(candidate)).isFile())return candidate;}catch{}
 }return null;
}
const productionRoots=expected.map(name=>resolve(src,'components',name,'index.tsx')).concat(files.filter(p=>p.startsWith(resolve(src,'domain')+'/')&&/\.tsx?$/.test(p)));
const traversed=new Set(),typeOnlyEdges=[];
async function checkBoundary(file,chain=[]){
 if(traversed.has(file))return;traversed.add(file);
 for(const dep of imports.get(file)||[]){
  if(dep.typeOnly){typeOnlyEdges.push({file:pathLabel(file),specifier:dep.specifier});continue;}
  const target=await resolveModule(file,dep.specifier);if(!target)continue;
  if(target===resolve(src,'sample.ts')||target.startsWith(resolve(src,'data')+'/')||extname(target)==='.json'){
   issue(file,dep.line,'data-boundary','Reusable code imports a data adapter or sample values via '+[...chain,pathLabel(file),dep.specifier].join(' → '));continue;
  }
  await checkBoundary(target,[...chain,pathLabel(file)]);
 }
}
for(const file of productionRoots)await checkBoundary(file);
const report={
 schemaVersion:1,stage:8,capturedAt:new Date().toISOString(),command:'cd ui && node qa/check-contracts.mjs',
 purpose:'Public component shape, data-boundary separation and authored CSS/token source contracts.',
 dataBoundary:'The API adapter (src/data) and the gallery sample values (src/sample.ts) are composed by the entrypoint, the gallery and stories; never a runtime dependency of reusable components or pure domain functions.',
 result:diagnostics.length?'failed':'passed',
 totals:{components:components.length,cssFiles:cssFiles.length,tokens:tokens.size,productionFilesTraversed:traversed.size,inlineProperties: inlineStyles.length,diagnostics:diagnostics.length},
 components,typeOnlyEdges,inlineStyles,diagnostics,
 limits:[
  'Source check only; build, Vitest, keyboard behavior, axe and independent pixel comparison run separately.',
  'Type-only imports are erased and allowed; external package internals are outside this authored-source boundary.',
  'CSS declaration parsing ignores selectors, strings and URLs. Grid indices/repeat counts/flex factors are structural, not dimensions; literal dimensions, zero lengths, font weights, palette colors and responsive boundaries are checked.',
  'currentColor/inherit/unset/none express CSS inheritance or absence, not a new palette. Transparent is a literal color and belongs in tokens.',
  'Dynamic inline styles are rejected for review rather than assumed safe. Story export presence proves available scenarios, not their behavioral correctness.'
 ]
};
await writeFile(resolve(root,'qa/contracts.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({result:report.result,...report.totals,diagnostics},null,2));
process.exitCode=diagnostics.length?1:0;
