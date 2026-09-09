import {useState} from 'react';
import {BeamSearch} from './beam-search';
import {BeamCard} from './beam-card';
import '../../registry.css';

const examples=['beam-search','beam-card'];
export default function SpectrumPreview(){
  const [query,setQuery]=useState(''),[submitted,setSubmitted]=useState(''),[motion,setMotion]=useState(false);
  const matches=examples.filter(name=>name.includes(query.toLowerCase()));
  return <main className="dark mx-auto max-w-3xl space-y-8 p-6 text-neutral-100">
    <header><h1 className="text-3xl">Spectrum UI integration</h1><p className="mt-3 text-neutral-300">Developer preview. Search the two installed examples; this is not the hosted skill search.</p></header>
    <section aria-labelledby="spectrum-search-title" className="space-y-4"><h2 id="spectrum-search-title">Beam Search</h2>
      <BeamSearch label="Filter installed examples" placeholder="Search installed examples…" value={query} onChange={setQuery} onSubmit={setSubmitted} theme="dark" colorVariant="mono"/>
      <p role="status">{matches.length?matches.join(', '):'No installed examples match.'}</p>
      <p>Last submitted query: {submitted||'None'}</p>
    </section>
    <section aria-labelledby="spectrum-card-title" className="space-y-4"><h2 id="spectrum-card-title">Beam Card</h2>
      <button type="button" aria-pressed={motion} onClick={()=>setMotion(!motion)} className="min-h-11 rounded-md border border-neutral-500 px-4">{motion?'Pause card animation':'Play card animation'}</button>
      <BeamCard theme="dark" colorVariant="mono" active={motion} title="Installed from Spectrum UI" description="Editable source, adapted for labelled input and reduced motion."><p className="text-neutral-300">The effect is optional. The content stays readable when motion is disabled.</p></BeamCard>
    </section>
    <a className="inline-flex min-h-11 items-center underline" href="/">Back to Guidefold</a>
  </main>;
}
