import {MemoryRouter} from 'react-router-dom';
import {Tabs} from './index';
export default {title:'Guidefold/Tabs',component:Tabs};
export const Fixture={render:()=> <MemoryRouter><Tabs label="Map axes" current="repository" items={[{id:'repository',label:'Repository',href:'/map?tab=repository'},{id:'scopes',label:'Scopes',href:'/map?tab=scopes'},{id:'pyramid',label:'Pyramid',href:'/map?tab=pyramid'}]}/></MemoryRouter>};
