import {cloneElement,type ReactElement} from 'react';
import css from './Field.module.css';

export function Field({id,label,hint,error,children}:{id:string;label:string;hint?:string;error?:string;children:ReactElement<{id?:string;'aria-describedby'?:string;'aria-invalid'?:boolean}>}){
 const described=[children.props['aria-describedby'],hint?id+'-hint':null,error?id+'-error':null].filter(Boolean).join(' ')||undefined;
 const control=cloneElement(children,{id,'aria-describedby':described,'aria-invalid':error?true:children.props['aria-invalid']});
 return <div className={css.field}><label htmlFor={id}>{label}</label>{control}{hint&&<small id={id+'-hint'}>{hint}</small>}{error&&<p id={id+'-error'} className={css.errorText} role="alert">{error}</p>}</div>;
}

