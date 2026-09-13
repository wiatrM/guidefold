import type {OrgMembership} from '../api/decoders';
import type {Params} from '../domain';

/** GitHub-style sticky organisation (owner brief 2026-09-13): the URL is authoritative, but with
 * no `?org=` the console returns to the organisation this user chose last, not always `orgs[0]`.
 * `null` means "leave storage alone" — a stale or matching remembered value costs nothing to
 * repeat, but an unresolved `?org=` (a foreign address) must never overwrite a good remembered
 * value with garbage. */
export type OrgMemoryAction={type:'set';value:string}|{type:'clear'}|null;
export interface OrgResolution{membership:OrgMembership|null;action:OrgMemoryAction;}

const findOrg=(orgs:OrgMembership[],value:string|null)=>value?orgs.find(o=>o.slug===value||o.org_id===value)??null:null;

/**
 * Resolves which membership the shell renders and what (if anything) should be remembered for
 * next time. Pure and storage-free by design: Base UI's Menu hangs jsdom once opened
 * (docs/ui/pipeline/08-components.md §Refaktor), so the choice this menu makes has to be
 * verifiable without ever rendering it — every branch here is a plain Vitest assertion.
 *
 * - An explicit `requestedOrg` that matches a membership always wins and is remembered.
 * - An explicit `requestedOrg` that matches nothing resolves to no membership (the existing
 *   "foreign organisation" path in app.tsx) and never touches storage — a bad address must not
 *   overwrite a good remembered choice.
 * - With no `requestedOrg`, the `remembered` value is used if it still names a membership.
 * - A `remembered` value that names no membership is dropped (`action: {type:'clear'}`) and the
 *   fallback is the first membership, exactly like the account had no remembered choice at all.
 */
export function resolveOrg(orgs:OrgMembership[],requestedOrg:string|null,remembered:string|null):OrgResolution{
 if(requestedOrg){
  const membership=findOrg(orgs,requestedOrg);
  return {membership,action:membership?{type:'set',value:membership.slug}:null};
 }
 const fromMemory=findOrg(orgs,remembered);
 if(fromMemory)return {membership:fromMemory,action:null};
 return {membership:orgs[0]??null,action:remembered?{type:'clear'}:null};
}

const orgMemoryKey=(userId:string)=>'guidefold-last-org-v1:'+userId;

/** Reads the remembered organisation for one signed-in user. Storage is a device convenience,
 * never a grant: a private window, cleared site data or a blocked accessor all just mean "no
 * remembered organisation", not an error. */
export function readOrgMemory(userId:string):string|null{
 try{return window.localStorage.getItem(orgMemoryKey(userId));}
 catch{return null;}
}

/** Applies an `OrgResolution.action`. A no-op action or a throwing accessor both leave the
 * session working from the URL and `/me` alone. */
export function writeOrgMemory(userId:string,action:OrgMemoryAction):void{
 if(!action)return;
 try{
  if(action.type==='set')window.localStorage.setItem(orgMemoryKey(userId),action.value);
  else window.localStorage.removeItem(orgMemoryKey(userId));
 }catch{/* Best-effort device memory; the next render still resolves from the URL and orgs[0]. */}
}

export interface OrgSwitcherLink{org:OrgMembership;current:boolean;href:string;}

/** Shapes the switcher's menu rows: one link per membership, each carrying the address that
 * switching to it produces. `buildHref` is the shell's own `href(view, changes)` partially
 * applied to the current view, so the current view is kept and every other in-flight param
 * (tab, filters, one-shot `github` code) is preserved — only `org` changes and `repo` is
 * dropped, since a repository filter belongs to the organisation that had it (IA §4: a context
 * change clears the previous context's data). */
export function orgSwitcherLinks(orgs:OrgMembership[],current:OrgMembership|null,buildHref:(changes:Params)=>string):OrgSwitcherLink[]{
 return orgs.map(org=>({org,current:current?.org_id===org.org_id,href:buildHref({org:org.slug,repo:null})}));
}
