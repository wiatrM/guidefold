import type {ReactNode} from 'react';
import type {Tone} from '../../domain';
import css from './StateBadge.module.css';

export function StateBadge({children,tone='neutral'}:{children:ReactNode;tone?:Tone}){return <span className={[css.badge,css[tone]].join(' ')}>{children}</span>;}
