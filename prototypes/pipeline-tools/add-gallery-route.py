from pathlib import Path
p=Path('../pipeline-hifi/src/app.tsx');s=p.read_text()
s=s.replace("const sessionKey=","const ComponentGallery=lazy(()=>import('./Gallery').then(m=>({default:m.ComponentGallery})));\nconst sessionKey=",1)
s=s.replace(" if(!views.includes(name as View))return"," if(name==='__components')return <Suspense fallback={<p>Loading component gallery</p>}><ComponentGallery/></Suspense>;\n if(!views.includes(name as View))return",1)
p.write_text(s)
p=Path('../pipeline-hifi/src/tokens.css');s=p.read_text().replace('--control-border:var(--steel);','--gallery-width:1040px; --control-border:var(--steel);',1);p.write_text(s)
