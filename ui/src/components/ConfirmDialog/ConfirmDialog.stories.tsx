import {ConfirmDialog} from './index';
export default {title:'Guidefold/ConfirmDialog',component:ConfirmDialog};
export const DisconnectGitHub={render:()=> <ConfirmDialog triggerLabel="Disconnect GitHub" title="Disconnect GitHub?" description="Guidefold stops reading new commits from every repository in this organisation. Already-imported skills and their history stay." confirmLabel="Disconnect" destructive onConfirm={()=>{}}/>};
export const DeleteModelKey={render:()=> <ConfirmDialog triggerLabel="Delete" title="Delete this model key?" description="Imports that need a model for proposals will show the no-key state until another key is added." confirmLabel="Delete key" destructive onConfirm={()=>{}}/>};
