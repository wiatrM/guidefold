import {cloneElement,type ReactElement} from 'react';
import css from './Field.module.css';

export function Field({id,label,hint,error,children}:{id:string;label:string;hint?:string;error?:string;children:ReactElement<{id?:string;'aria-describedby'?:string;'aria-invalid'?:boolean}>}){
 const described=[children.props['aria-describedby'],hint?id+'-hint':null,error?id+'-error':null].filter(Boolean).join(' ')||undefined;
 const control=cloneElement(children,{id,'aria-describedby':described,'aria-invalid':error?true:children.props['aria-invalid']});
 return <div className={css.field} data-slot="field"><label htmlFor={id} data-slot="field-label">{label}</label>{control}{hint&&<small id={id+'-hint'} data-slot="field-description">{hint}</small>}{error&&<p id={id+'-error'} className={css.errorText} role="alert" data-slot="field-error">{error}</p>}</div>;
}
