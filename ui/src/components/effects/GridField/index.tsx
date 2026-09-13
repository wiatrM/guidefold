import {useMotionGate} from '../useMotionGate';
import css from './GridField.module.css';

/**
 * Lightweight animated grid background for page chrome and empty states (ADR-0049): the same
 * survey-grid device already used inside IconTile, drifting slowly behind content. Cheaper
 * than ShaderField where a shader is more than the moment needs. Purely decorative
 * (aria-hidden); static under reduced motion, off-screen or a hidden tab. Distinct from the
 * survey-grid-pattern image asset UI.md §1 removed from the nav rail — that was chrome behind
 * navigation; this is an opt-in background a route places behind its own content.
 */
export function GridField({className}:{className?:string}){
 const gate=useMotionGate<HTMLDivElement>();
 return <div ref={gate.ref} aria-hidden="true" data-slot="grid-field"
  className={[css.field,gate.active?css.drift:'',className].filter(Boolean).join(' ')}/>;
}
