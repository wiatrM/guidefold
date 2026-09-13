import {ModelKeysTable} from './index';
export default {title:'Guidefold/ModelKeysTable',component:ModelKeysTable};
export const Default={render:()=> <ModelKeysTable keys={[{id:'k1',provider:'OpenAI',lastFour:'a1b2',preferred:true},{id:'k2',provider:'Anthropic',lastFour:'9f3d'}]} onDelete={()=>{}} onSetPreferred={()=>{}}/>};
export const Empty={render:()=> <ModelKeysTable keys={[]}/>};
