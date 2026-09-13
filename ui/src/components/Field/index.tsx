import {cloneElement,type ReactElement} from 'react';
import {FieldLabel,FieldDescription,FieldError} from '@/components/ui/field';
import css from './Field.module.css';

/** Label, control, hint and error wired by id. The control is whatever the route passes (native input, select, textarea or a shadcn Input); the field only names and describes it. Composes the shadcn `field` primitive's label/description/error (2026-09-13) — same props, same data-slot values, own outer grid layout. */
export function Field({id,label,hint,error,children}:{id:string;label:string;hint?:string;error?:string;children:ReactElement<{id?:string;'aria-describedby'?:string;'aria-invalid'?:boolean}>}){
 const described=[children.props['aria-describedby'],hint?id+'-hint':null,error?id+'-error':null].filter(Boolean).join(' ')||undefined;
 const control=cloneElement(children,{id,'aria-describedby':described,'aria-invalid':error?true:children.props['aria-invalid']});
 return <div className={css.field} data-slot="field" data-invalid={error?true:undefined}><FieldLabel htmlFor={id} className={css.label}>{label}</FieldLabel>{control}{hint&&<FieldDescription id={id+'-hint'} className={css.hint}>{hint}</FieldDescription>}{error&&<FieldError id={id+'-error'} className={css.errorText}>{error}</FieldError>}</div>;
}
