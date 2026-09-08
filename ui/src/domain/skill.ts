import type {Skill} from '../domain';
export const bodyPrefix=(s:Skill)=>s.raw.match(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n)+/)?.[0] ?? '';
export const digest=async(text:string)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),b=>b.toString(16).padStart(2,'0')).join('');
