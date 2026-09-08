import {MetricRow} from './index';
export default {title:'Guidefold/MetricRow',component:MetricRow};
export const Default={args:{items:[
 {label:'Delivery',value:'Unknown',detail:'No adapter event ledger'},
 {label:'Helpfulness',value:'Unknown',detail:'No attributed assessments'},
 {label:'Observation coverage',value:'Unknown',detail:'Eligible episodes unavailable'}
]}};
export const Funnel={args:{layout:'funnel',items:[
 {label:'Exposed',value:'120',detail:'Cards an adapter placed into context'},
 {label:'Loaded',value:'44',detail:'44 of 120 (37%) of exposed cards had a verified body load'},
 {label:'Context confirmed',value:'40',detail:'4 verified loads have an unknown context outcome'},
 {label:'Applied · reported / observed',value:'11 / 7',detail:'9 task-linked episodes'},
 {label:'Helped',value:'Unknown',detail:'No assessment recorded; not 0%'}
]}};
