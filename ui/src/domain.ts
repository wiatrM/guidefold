import type {ReactNode} from 'react';
import type {DataSource} from './data/source';
import type {AccessState} from './api/access';
import type {Me,Role} from './api/decoders';
export type View='home'|'import'|'library'|'map'|'skill'|'proposals'|'usage'|'organization';
export type DataState='ready'|'empty'|'loading'|'partial'|'error'|'degraded'|'restricted';
export type Tone='neutral'|'system'|'human'|'warning'|'error';
/** Unsent operator text held in RAM for the current access generation; never persisted (07 §Prywatność). */
export interface Draft {candidate:string;digest:string;reason:string;}
export interface Session {proposal?:Draft;feedback?:Record<string,string>;}
export type Params=Record<string,string|number|null|undefined>;
export interface TreeNode {id:string;label:string;detail?:string;href?:string;children?:TreeNode[];}
export interface EvidenceEntry {label:string;value:ReactNode;detail?:string;href?:string;code?:boolean;}
/** Context for the seven routes reading the hosted API. */
export interface ApiRouteContext {source:DataSource;access:AccessState;me:Me|null;org:string|null;repo:string|null;role:Role|null;params:URLSearchParams;view:View;href:(view:View,changes?:Params)=>string;go:(view:View,changes?:Params)=>void;
 /** Forces an immediate /me re-check (bypassing the ~25 s cadence) so a just-completed
  * membership change (create org, accept invitation, ...) is visible before the next
  * navigation, instead of reading as "Organization unavailable" for up to 25 s. No-op if
  * the access controller is not mounted. */
 recheckAccess?:()=>Promise<unknown>;}
