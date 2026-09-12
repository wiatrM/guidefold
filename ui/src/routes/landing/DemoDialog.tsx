import {useRef,useState} from 'react';
import {Dialog} from '@base-ui/react/dialog';
import {ArrowUpRight,Play,X} from '@phosphor-icons/react';
import {buttonVariants} from '../../components/ui/button';
import {demoUrl} from './instruction';
import css from './landing.module.css';

/**
 * The recorded demo, kept as a compact action. The nocookie player is mounted only
 * while the dialog is open and unmounted on close, so no YouTube request happens on
 * arrival, and the plain link is the fallback for anyone who cannot use the dialog.
 */
export function DemoDialog({onOpenChange,defaultOpen=false}:{onOpenChange:(open:boolean)=>void;defaultOpen?:boolean}){
 const [open,setOpen]=useState(defaultOpen);
 const trigger=useRef<HTMLButtonElement>(null);
 const close=useRef<HTMLButtonElement>(null);
 return <Dialog.Root open={open} onOpenChange={value=>{setOpen(value);onOpenChange(value);}}>
  <Dialog.Trigger ref={trigger} className={buttonVariants({variant:'outline',className:css.actionQuiet})}>
   <Play weight="fill" aria-hidden="true"/>Play demo
  </Dialog.Trigger>
  <Dialog.Portal>
   <Dialog.Backdrop className={css.backdrop}/>
   <Dialog.Popup className={css.cinema} initialFocus={close} finalFocus={trigger}>
    <div className={css.dialogHeader}>
     <Dialog.Title className={css.dialogTitle}>Guidefold product demo</Dialog.Title>
     <Dialog.Close ref={close} className={css.dialogClose} aria-label="Stop video"><X aria-hidden="true"/>Close</Dialog.Close>
    </div>
    <Dialog.Description className={css.dialogDescription}>The recorded workflow, from repository instructions to an agent loading a skill.</Dialog.Description>
    {open&&<iframe className={css.player} title="Guidefold product demo" src="https://www.youtube-nocookie.com/embed/e350wBr1W8c?autoplay=1" allow="autoplay; encrypted-media; picture-in-picture" allowFullScreen referrerPolicy="strict-origin-when-cross-origin"/>}
    <a className={css.textLink} href={demoUrl} target="_blank" rel="noreferrer">Watch on YouTube <ArrowUpRight aria-hidden="true"/></a>
   </Dialog.Popup>
  </Dialog.Portal>
 </Dialog.Root>;
}
