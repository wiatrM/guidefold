import type {ReactNode} from 'react';
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
export interface RouteContext {params:URLSearchParams;state:DataState;view:View;member:boolean;canWrite:boolean;canFeedback:boolean;memory:Session;save:(patch:Partial<Session>)=>void;href:(view:View,changes?:Params)=>string;go:(view:View,changes?:Params)=>void;}
export interface TreeNode {id:string;label:string;detail?:string;href?:string;children?:TreeNode[];}
export interface EvidenceEntry {label:string;value:ReactNode;detail?:string;href?:string;code?:boolean;}
