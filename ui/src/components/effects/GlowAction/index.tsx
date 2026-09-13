import type {ReactNode} from 'react';
import css from './GlowAction.module.css';

/**
 * Glow for the primary action, and a stronger glow on focus (ADR-0049). Wrap a single
 * ActionButton; the halo sits behind it, at rest and brighter under :focus-within, so the
 * ring is visible with a mouse, a keyboard or a screen magnifier. Tone matches the button's
 * own tone: human (orange) for the one primary action, system (teal) for a system action.
 */
export function GlowAction({children,tone='human',className}:{children:ReactNode;tone?:'system'|'human';className?:string}){
 return <span data-slot="glow-action" className={[css.wrap,tone==='system'?css.system:'',className].filter(Boolean).join(' ')}>
  <span aria-hidden="true" className={css.halo}/>
  <span className={css.content}>{children}</span>
 </span>;
}
