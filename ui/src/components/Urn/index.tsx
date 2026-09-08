import {useEffect,useRef,useState} from 'react';
import {Check,Copy} from '@phosphor-icons/react';
import css from './Urn.module.css';

export function Urn({value}:{value:string}){
 const [result,setResult]=useState({value,message:''});
 const operation=useRef(0);
 useEffect(()=>{operation.current++;setResult({value,message:''});},[value]);
 const notice=result.value===value?result.message:'';
 async function copy(){
  const request=++operation.current,copiedValue=value;
  try{
   await navigator.clipboard.writeText(copiedValue);
   if(request===operation.current)setResult({value:copiedValue,message:'Copied identifier'});
  }catch{
   if(request===operation.current)setResult({value:copiedValue,message:'Copy unavailable. Select the identifier text.'});
  }
 }
 return <div className={css.urn}><code>{value}</code><button type="button" onClick={copy} aria-label="Copy identifier" title="Copy identifier">{notice==='Copied identifier'?<Check aria-hidden="true"/>:<Copy aria-hidden="true"/>}</button><span className={css.copyNotice} role="status">{notice}</span></div>;
}
