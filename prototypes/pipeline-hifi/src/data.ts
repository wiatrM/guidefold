import rawFixture from './data/fixture.json';
import type {Fixture,Skill,Proposal,DataState} from './domain';
export const fixture=rawFixture as Fixture;
export const proposalSkill=fixture.skills.find(s=>s.name==='postgres-auth')!;
export const findSkill=(id:string|null|undefined)=>fixture.skills.find(s=>s.id===id);
export const visibleSkills=(state:DataState)=>state==='partial'?[proposalSkill,...fixture.skills.filter(s=>s.id!==proposalSkill.id).slice(0,7)]:fixture.skills;
export const sourceURL=(path:string)=>'https://github.com/wiatrM/guidefold/blob/'+fixture.commit+'/examples/monorepo/'+path;
export const defaultProposal=():Proposal=>({stage:'draft',candidate:proposalSkill.raw,digest:proposalSkill.revision,reason:''});
export const bodyPrefix=(s:Skill)=>s.raw.match(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n)+/)?.[0] ?? '';
export const digest=async(text:string)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),b=>b.toString(16).padStart(2,'0')).join('');
export function lineDiff(source:string,candidate:string):string{
 if(source===candidate)return 'No text changes';
 const a=source.split('\n'),b=candidate.split('\n');let first=0,lastA=a.length,lastB=b.length;
 while(first<Math.min(a.length,b.length)&&a[first]===b[first])first++;
 while(lastA>first&&lastB>first&&a[lastA-1]===b[lastB-1]){lastA--;lastB--;}
 const start=Math.max(0,first-2),endA=Math.min(a.length,lastA+2),endB=Math.min(b.length,lastB+2);
 return ['@@ -'+(start+1)+','+(endA-start)+' +'+(start+1)+','+(endB-start)+' @@',
 ...a.slice(start,first).map(x=>'  '+x),...a.slice(first,lastA).map(x=>'− '+x),
 ...b.slice(first,lastB).map(x=>'+ '+x),...a.slice(lastA,endA).map(x=>'  '+x)].join('\n');
}
