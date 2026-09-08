import {useId, type ReactNode} from 'react';
import css from './Panel.module.css';

export function Panel({title,eyebrow,icon,action,children,className='',id}:{title:string;eyebrow?:string;icon?:ReactNode;action?:ReactNode;children:ReactNode;className?:string;id?:string}){
 const titleId=useId();return <section id={id} className={[css.panel,className].join(' ')} aria-labelledby={titleId}><header className={css.panelHeader}><div>{eyebrow&&<span className={css.eyebrow}>{eyebrow}</span>}<h2 id={titleId}>{icon&&<span aria-hidden="true">{icon}</span>}{title}</h2></div>{action}</header><div className={css.panelBody}>{children}</div></section>;
}
