from pathlib import Path
p=Path("prototypes/pipeline-wireframes/wireframes.js");s=p.read_text()
old="main.querySelector('.row.end').append(entry);"
new=old+"""
   if(proposal().stage==='published'){
     const evidence=document.createElement('p');evidence.className='context';
     evidence.textContent='Local simulation only · Context loaded: Unknown';
     main.querySelector('.row.end').after(evidence);
   }"""
assert old in s;s=s.replace(old,new);p.write_text(s)
