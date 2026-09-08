import {useState} from 'react';
import {Field} from './index';
function ReasonField(){
 const [reason,setReason]=useState('');
 return <Field id="gallery-reason" label="Reason for this decision" hint="Required for every decision." error={reason.trim()?undefined:'Choose a decision and explain your reason.'}><textarea id="gallery-reason" value={reason} onChange={e=>setReason(e.target.value)}/></Field>;
}
export default {title:'Guidefold/Field',component:Field};
export const Default={render:ReasonField};
