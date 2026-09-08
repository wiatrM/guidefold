from pathlib import Path
p=Path('../pipeline-hifi/src/Shared.tsx')
s=p.read_text().replace("useId,useState,type ReactNode","useId,useState,cloneElement,isValidElement,type ReactElement,type ReactNode")
old="export function Field({id,label,hint,error,children}:{id:string;label:string;hint?:string;error?:string;children:ReactNode}){return <div className={css.field}><label htmlFor={id}>{label}</label>{children}{hint&&<small id={id+'-hint'}>{hint}</small>}{error&&<p id={id+'-error'} className={css.errorText} role=\"alert\">{error}</p>}</div>;}"
new="""export function Field({id,label,hint,error,children}:{id:string;label:string;hint?:string;error?:string;children:ReactElement<{id?:string;'aria-describedby'?:string;'aria-invalid'?:boolean}>}){
 const described=[children.props['aria-describedby'],hint?id+'-hint':null,error?id+'-error':null].filter(Boolean).join(' ')||undefined;
 const control=cloneElement(children,{id,'aria-describedby':described,'aria-invalid':error?true:children.props['aria-invalid']});
 return <div className={css.field}><label htmlFor={id}>{label}</label>{control}{hint&&<small id={id+'-hint'}>{hint}</small>}{error&&<p id={id+'-error'} className={css.errorText} role="alert">{error}</p>}</div>;
}"""
assert old in s
s=s.replace(old,new).replace("cloneElement,isValidElement","cloneElement")
s=s.replace("− Removed lines · Frontmatter unchanged","− Removed lines")
p.write_text(s)
p=Path('../pipeline-hifi/src/app.tsx');s=p.read_text().replace("useEffect,useRef,useState","useEffect,useRef,useState,lazy,Suspense")
for names,mod in [('LibraryRoute,MapRoute,SkillRoute','CatalogRoutes'),('ImportRoute,OrganizationRoute','OnboardingRoutes'),('ProposalsRoute,UsageRoute','ReviewRoutes')]:
 old="import {"+names+"} from './routes/"+mod+"';"
 new='\n'.join("const "+n+"=lazy(()=>import('./routes/"+mod+"').then(m=>({default:m."+n+"})));" for n in names.split(','))
 s=s.replace(old,new)
s=s.replace('<Content ctx={ctx}/>','<Suspense fallback={<RouteState state="loading" title="Loading view" description="Preparing the requested view."/>}><Content ctx={ctx}/></Suspense>')
p.write_text(s)
p=Path('../pipeline-hifi/src/main.tsx');s=p.read_text()
for family in ['inter','barlow-condensed']:
 for weight in [400,500,600,700]:
  s=s.replace('@fontsource/'+family+'/'+str(weight)+'.css','@fontsource/'+family+'/latin-'+str(weight)+'.css')
p.write_text(s)
p=Path('../pipeline-hifi/src/App.module.css');s=p.read_text().replace('z-index:100','z-index:var(--layer-skip)').replace('translateY(-200%)','translateY(var(--skip-hidden-offset))').replace('translateY(0)','translateY(var(--zero))');p.write_text(s)
p=Path('../pipeline-hifi/src/tokens.css');s=p.read_text().replace('--control-border:var(--steel);','--control-border:var(--steel); --layer-skip:100; --skip-hidden-offset:-200%;');p.write_text(s)
