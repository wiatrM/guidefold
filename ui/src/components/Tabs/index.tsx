import {Link} from 'react-router-dom';
import css from './Tabs.module.css';

export function Tabs({label,items,current}:{label:string;items:{id:string;label:string;href:string}[];current:string}){return <nav className={css.tabs} aria-label={label}>{items.map(item=><Link key={item.id} to={item.href} aria-current={current===item.id?'page':undefined}>{item.label}</Link>)}</nav>;}
