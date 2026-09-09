import type {ReactNode} from 'react';
import {WarningCircle} from '@phosphor-icons/react';
import type {DataState} from '../../domain';
import css from './RouteState.module.css';

export function RouteState({state,title,description,action}:{state:DataState;title:string;description:string;action?:ReactNode}){
 return <section className={css.routeState} aria-busy={state==='loading'} aria-live="polite" data-slot="alert"><div className={css.stateHeader}>{state==='error'&&<WarningCircle aria-hidden="true" className={css.errorIcon}/>}<h2>{title}</h2></div><p>{description}</p>{state==='loading'&&<div className={css.skeleton} aria-hidden="true" data-slot="skeleton"><span/><span/><span/></div>}{action&&<div className={css.stateAction}>{action}</div>}</section>;
}
