export type WaitlistAction='join'|'confirm'|'unsubscribe';
export class WaitlistError extends Error {
 constructor(public kind:'invalid'|'limited'|'unavailable'|'expired'){super(kind);}
}
/** Public endpoint: no management session, credentials or email in storage/logs. */
export async function submitWaitlist(action:WaitlistAction,payload:Record<string,unknown>,signal?:AbortSignal):Promise<void>{
 const base=import.meta.env.VITE_GUIDEFOLD_API?.replace(/\/$/,'')??'';
 const response=await fetch(base+'/api/v1/waitlist'+(action==='join'?'':'/'+action),{
  method:'POST',credentials:'omit',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal,
 });
 if(!response.ok)throw new WaitlistError(response.status===429?'limited':response.status===400||response.status===422?(action==='join'?'invalid':'expired'):response.status===410?'expired':'unavailable');
 const body:unknown=await response.json();
 if(!body||typeof body!=='object'||!('schema_version'in body)||body.schema_version!=='1.0'||!('request_id'in body)||typeof body.request_id!=='string'||!('data'in body)||!body.data||typeof body.data!=='object'||!('status'in body.data))throw new WaitlistError('unavailable');
 const expected=action==='join'?'pending':action==='confirm'?'confirmed':'unsubscribed';
 if(body.data.status!==expected)throw new WaitlistError('unavailable');
}
