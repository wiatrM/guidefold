import {AdapterFallback} from './index';
export default {title:'Guidefold/AdapterFallback',component:AdapterFallback};
export const Default={render:()=> <AdapterFallback commands={['curl -fsSL https://guidefold.dev/install.sh | sh','guidefold login','guidefold link atlas-search','guidefold sync','guidefold status']}/>};
