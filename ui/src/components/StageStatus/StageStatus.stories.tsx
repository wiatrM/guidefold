import {StageStatus} from './index';
const stages=[{id:'fetch',label:'Fetch'},{id:'parse',label:'Parse'},{id:'propose',label:'Propose'}];
export default {title:'Guidefold/StageStatus',component:StageStatus};
export const Steps={render:()=> <StageStatus stages={stages} activeIndex={1}/>};
export const Inline={render:()=> <StageStatus stages={stages} activeIndex={1} progress={0.4} detail="Parsing 3 of 5 files" variant="inline"/>};
