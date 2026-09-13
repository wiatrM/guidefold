import {useCallback,useState} from 'react';
import {useDropzone} from 'react-dropzone';
import {Accordion,AccordionItem,AccordionTrigger,AccordionContent} from '@/components/ui/accordion';
import {CodeBlock} from '@/components/ui/code-block';
import css from './AdapterFallback.module.css';

/**
 * The wizard's GitHub-step disclosure (UX §3a: "krok GitHub ma zwiniętą ścieżkę awaryjną — CLI
 * albo pliki"), collapsed by default: run the adapter's CLI commands, or drop a file instead.
 * Wraps shadcn `accordion`, the `code-block` primitive for the adapter commands and a plain
 * `react-dropzone` target with no hover flourish beyond the drag-active state itself
 * (2026-09-13; the vendored aceternity-style file-upload demo added a decorative
 * `whileHover` icon translation unrelated to any state change, which UX §6 does not allow).
 */
export function AdapterFallback({commands,onFileSelected,accept,className}:{commands:string[];onFileSelected?:(file:File)=>void;accept?:string;className?:string}){
 const [fileName,setFileName]=useState<string|undefined>();
 const onDrop=useCallback((accepted:File[])=>{const file=accepted[0];if(file){setFileName(file.name);onFileSelected?.(file);}},[onFileSelected]);
 const {getRootProps,getInputProps,isDragActive}=useDropzone({onDrop,multiple:false,accept:accept?{[accept]:[]}:undefined});
 return <Accordion defaultValue={[]} className={className} data-slot="adapter-fallback">
  <AccordionItem value="cli">
   <AccordionTrigger>Use the CLI</AccordionTrigger>
   <AccordionContent><CodeBlock code={commands.join('\n')} language="bash" filename="terminal"/></AccordionContent>
  </AccordionItem>
  <AccordionItem value="file">
   <AccordionTrigger>Upload a file</AccordionTrigger>
   <AccordionContent>
    <div {...getRootProps()} className={css.drop} data-active={isDragActive||undefined}>
     <input {...getInputProps()} aria-label="guidefold.yaml file"/>
     <p>{fileName??(isDragActive?'Drop the file':'Drag a file here, or click to choose one')}</p>
    </div>
   </AccordionContent>
  </AccordionItem>
 </Accordion>;
}
