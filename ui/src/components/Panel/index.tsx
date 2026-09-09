import {useId, type ReactNode} from 'react';
import css from './Panel.module.css';
import {BeamCard} from '../spectrumui/beam-card';

export function Panel({title,eyebrow,icon,action,children,className='',id}:{title:string;eyebrow?:string;icon?:ReactNode;action?:ReactNode;children:ReactNode;className?:string;id?:string}){
 const titleId=useId();return <section id={id} className={[css.region,className].join(' ')} aria-labelledby={titleId} data-slot="card"><BeamCard active={false} theme="dark" colorVariant="mono" className={css.panel} contentClassName={css.content}><header className={css.panelHeader} data-slot="card-header"><div><h2 id={titleId} data-slot="card-title">{icon&&<span aria-hidden="true">{icon}</span>}{title}</h2>{eyebrow&&<span className={css.eyebrow}>{eyebrow}</span>}</div>{action}</header><div className={css.panelBody} data-slot="card-content">{children}</div></BeamCard></section>;
}
