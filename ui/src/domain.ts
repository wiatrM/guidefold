import type {ReactNode} from 'react';
import type {FixtureAdapter} from './data';
import type {DataSource,SourceMode} from './data/source';
import type {AccessState} from './api/access';
import type {Me,Role} from './api/decoders';
export type View='import'|'library'|'map'|'skill'|'proposals'|'usage'|'organization';
export type DataState='ready'|'empty'|'loading'|'partial'|'error'|'degraded'|'restricted';
export type Tone='neutral'|'system'|'human'|'warning'|'error';
export interface Skill {id:string;name:string;scope:string;owner:string;sourceLayer:string;knowledgeLayer:string;sourceStatus:string;description:string;body:string;raw:string;path:string;revision:string;bytes:number;requires:string[];refines:string[];references:string[];}
export interface ScopeNode {id:string;paths:string[];owner:string;subteams?:string[];}
export interface Fixture {fixture:boolean;label:string;repo:string;org:string;commit:string;sources:string;nodes:ScopeNode[];skills:Skill[];}
export type ProposalStage='draft'|'editing'|'approved_for_export'|'awaiting_git'|'published'|'rejected';
export interface Proposal {stage:ProposalStage;candidate:string;digest:string;reason:string;}
export interface Session {login?:string;org?:boolean;imported?:boolean;proposal?:Proposal;members?:string[];feedback?:Record<string,string>;token?:boolean;connection?:boolean;}
export type Params=Record<string,string|number|null|undefined>;
export interface RouteContext {data:FixtureAdapter;source:DataSource;mode:SourceMode;params:URLSearchParams;state:DataState;view:View;member:boolean;canWrite:boolean;canFeedback:boolean;memory:Session;save:(patch:Partial<Session>)=>void;href:(view:View,changes?:Params)=>string;go:(view:View,changes?:Params)=>void;}
export interface TreeNode {id:string;label:string;detail?:string;href?:string;children?:TreeNode[];}
export interface EvidenceEntry {label:string;value:ReactNode;detail?:string;href?:string;code?:boolean;}
/** Context for routes reading the hosted API. The fixture adapter is absent by design. */
export interface ApiRouteContext {source:DataSource;access:AccessState;me:Me|null;org:string|null;repo:string|null;role:Role|null;params:URLSearchParams;view:View;href:(view:View,changes?:Params)=>string;go:(view:View,changes?:Params)=>void;
 /** Forces an immediate /me re-check (bypassing the ~25 s cadence) so a just-completed
  * membership change (create org, accept invitation, ...) is visible before the next
  * navigation, instead of reading as "Organization unavailable" for up to 25 s. No-op if
  * the access controller is not mounted (fixture mode never sets this). */
 recheckAccess?:()=>Promise<unknown>;}
