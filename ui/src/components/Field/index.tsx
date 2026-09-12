import {cloneElement,type ReactElement} from 'react';
import {Label} from '@/components/ui/label';
import css from './Field.module.css';

/** Label, control, hint and error wired by id. The control is whatever the route passes (native input, select, textarea or a shadcn Input); the field only names and describes it. */
export function Field({id,label,hint,error,children}:{id:string;label:string;hint?:string;error?:string;children:ReactElement<{id?:string;'aria-describedby'?:string;'aria-invalid'?:boolean}>}){
 const described=[children.props['aria-describedby'],hint?id+'-hint':null,error?id+'-error':null].filter(Boolean).join(' ')||undefined;
 const control=cloneElement(children,{id,'aria-describedby':described,'aria-invalid':error?true:children.props['aria-invalid']});
 return <div className={css.field} data-slot="field" data-invalid={error?true:undefined}><Label htmlFor={id} className={css.label} data-slot="field-label">{label}</Label>{control}{hint&&<small id={id+'-hint'} className={css.hint} data-slot="field-description">{hint}</small>}{error&&<p id={id+'-error'} className={css.errorText} role="alert" data-slot="field-error">{error}</p>}</div>;
}
