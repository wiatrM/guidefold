import {Toaster} from 'sonner';
import css from './App.module.css';

export default function ToastHost() {
 return <Toaster position="bottom-right" theme="dark" closeButton toastOptions={{classNames:{toast:css.toast,title:css.toastTitle,description:css.toastDescription,actionButton:css.toastAction,closeButton:css.toastClose}}}/>;
}
