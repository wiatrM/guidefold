import type {ReactNode} from 'react';
import {AlertDialog,AlertDialogTrigger,AlertDialogContent,AlertDialogHeader,AlertDialogTitle,AlertDialogDescription,AlertDialogFooter,AlertDialogAction,AlertDialogCancel} from '@/components/ui/alert-dialog';
import {Button} from '@/components/ui/button';
import css from './ConfirmDialog.module.css';

/**
 * A destructive or otherwise consequential confirmation, opened from its own trigger button:
 * "Disconnect GitHub", deleting a model key. Wraps shadcn `alert-dialog` (2026-09-13). The
 * dialog is a Base UI portal, so its open content is exercised in the Playwright gallery spec,
 * not Vitest/jsdom (docs/ui/pipeline/08-components.md).
 */
export function ConfirmDialog({triggerLabel,title,description,confirmLabel='Confirm',cancelLabel='Cancel',destructive,onConfirm,disabled,className}:{triggerLabel:ReactNode;title:string;description:ReactNode;confirmLabel?:string;cancelLabel?:string;destructive?:boolean;onConfirm:()=>void;disabled?:boolean;className?:string}){
 return <AlertDialog>
  <AlertDialogTrigger render={<Button type="button" variant={destructive?'destructive':'outline'} disabled={disabled} className={className}/>}>{triggerLabel}</AlertDialogTrigger>
  <AlertDialogContent>
   <AlertDialogHeader>
    <AlertDialogTitle>{title}</AlertDialogTitle>
    <AlertDialogDescription className={css.description}>{description}</AlertDialogDescription>
   </AlertDialogHeader>
   <AlertDialogFooter>
    <AlertDialogCancel render={<Button type="button" variant="outline"/>}>{cancelLabel}</AlertDialogCancel>
    <AlertDialogAction render={<Button type="button" variant={destructive?'destructive':'default'}/>} onClick={onConfirm}>{confirmLabel}</AlertDialogAction>
   </AlertDialogFooter>
  </AlertDialogContent>
 </AlertDialog>;
}
