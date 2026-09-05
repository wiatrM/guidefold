(() => {
"use strict";
const DATA = JSON.parse(document.getElementById("tracker-data").textContent);
const KEY = "guidefold.learning.progress.v1";
const BACKUP = KEY + ".previous";
const MAX_NOTES = 10000;
const STATUSES = {planned:"Do zrobienia",active:"W trakcie",paused:"Pauza",done:"Zaliczony"};
const byId = Object.fromEntries(DATA.stages.map(s => [s.id,s]));
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const now = () => new Date().toISOString();
const fmt = n => new Intl.NumberFormat("pl-PL",{maximumFractionDigits:2}).format(n);
const newState = () => ({app:"guidefold-learning",version:1,updatedAt:null,revision:"",stages:Object.fromEntries(DATA.stages.map(s => [s.id,{status:"planned",checks:Object.fromEntries(s.tasks.map(t=>[t[0],false])),hours:0,notes:"",updatedAt:null,completedAt:null}]))});
let state = newState(), lastRaw = null, pendingImport = null, storageAvailable = true, conflict = false, corruptRaw = null, toastTimer;
const isObject = x => !!x && typeof x === "object" && !Array.isArray(x);
const hasKeys = (x, allowed) => Object.keys(x).every(k => allowed.includes(k));
const validDate = x => x === null || (typeof x === "string" && x.length < 60 && /^\d{4}-\d\d-\d\dT/.test(x) && Number.isFinite(Date.parse(x)));
function validate(input) {
  const bad = msg => {throw new Error(msg);};
  if (!isObject(input) || input.app !== "guidefold-learning" || input.version !== 1) bad("To nie jest obsługiwana kopia postępu (wersja 1).");
  if (!hasKeys(input,["app","version","updatedAt","revision","stages","exportedAt"])) bad("Plik zawiera nieznane pola.");
  if (!validDate(input.updatedAt) || typeof input.revision !== "string" || input.revision.length > 200) bad("Niepoprawne metadane zapisu.");
  if (input.exportedAt !== undefined && !validDate(input.exportedAt)) bad("Niepoprawna data eksportu.");
  if (!isObject(input.stages) || Object.keys(input.stages).length !== DATA.stages.length || !hasKeys(input.stages,Object.keys(byId))) bad("Plik musi zawierać wszystkie 10 znanych etapów.");
  const out = newState(); out.updatedAt=input.updatedAt; out.revision=input.revision;
  for (const stage of DATA.stages) {
    const r=input.stages[stage.id], ids=stage.tasks.map(t=>t[0]);
    if (!isObject(r) || !hasKeys(r,["status","checks","hours","notes","updatedAt","completedAt"])) bad("Niepoprawne dane etapu: "+stage.title);
    if (typeof r.status !== "string" || !Object.hasOwn(STATUSES,r.status)) bad("Niepoprawny status etapu.");
    if (typeof r.hours !== "number" || !Number.isFinite(r.hours) || r.hours < 0 || r.hours > 10000) bad("Godziny muszą być liczbą od 0 do 10 000.");
    if (typeof r.notes !== "string" || r.notes.length > MAX_NOTES) bad("Notatka przekracza limit 10 000 znaków lub ma niepoprawny format.");
    if (!isObject(r.checks) || Object.keys(r.checks).length !== ids.length || !hasKeys(r.checks,ids) || !ids.every(id=>typeof r.checks[id]==="boolean")) bad("Niepoprawna checklista etapu.");
    if (!validDate(r.updatedAt) || !validDate(r.completedAt)) bad("Niepoprawna data etapu.");
    if (r.status==="done" && (!ids.every(id=>r.checks[id]) || !r.completedAt)) bad("Zaliczony etap musi mieć wszystkie sprawdzenia i datę zaliczenia.");
    if (r.status!=="done" && r.completedAt!==null) bad("Data zaliczenia nie odpowiada statusowi etapu.");
    out.stages[stage.id]={status:r.status,checks:Object.fromEntries(ids.map(id=>[id,r.checks[id]])),hours:r.hours,notes:r.notes,updatedAt:r.updatedAt,completedAt:r.completedAt};
  }
  return out;
}
function toast(message) {
  $("toast").textContent=message; $("toast").hidden=false;
  clearTimeout(toastTimer); toastTimer=setTimeout(()=>$("toast").hidden=true,5500);
}
function saveMessage(message,error=false) {
  $("save-status").textContent=message;
  $("save-strip").classList.toggle("error",error);
}
function showConflict() {
  conflict=true; $("conflict").hidden=false;
  $("conflict-message").textContent="W innej karcie zmieniono zapis. Twoje zmiany pozostają na tej stronie, ale automatyczny zapis jest wstrzymany. Wybierz wersję do zachowania lub wyeksportuj bieżącą.";
  saveMessage("Konflikt wersji — automatyczny zapis wstrzymany.",true);
}
function persist(force=false) {
  if (corruptRaw !== null && !force) {saveMessage("Zachowano uszkodzony zapis. Bieżące zmiany możesz wyeksportować.",true); return false;}
  if (conflict && !force) {saveMessage("Konflikt wersji — zmiany są tylko na tej stronie.",true);return false;}
  state.updatedAt=now(); state.revision=Date.now()+"-"+Math.random().toString(36).slice(2);
  try {
    const raw=localStorage.getItem(KEY);
    if (!force && raw!==lastRaw) {showConflict();return false;}
    const next=JSON.stringify(state); localStorage.setItem(KEY,next); lastRaw=next; storageAvailable=true;
    conflict=false; $("conflict").hidden=true;
    saveMessage("Zapisano lokalnie · "+new Date().toLocaleTimeString("pl-PL",{hour:"2-digit",minute:"2-digit"}));
    return true;
  } catch {
    storageAvailable=false;
    saveMessage("Zapis lokalny niedostępny. Zmiany są na tej stronie — wyeksportuj postęp przed zamknięciem.",true);
    return false;
  }
}
function loadInitial() {
  try {lastRaw=localStorage.getItem(KEY);}
  catch {storageAvailable=false;saveMessage("Przeglądarka blokuje zapis. Korzystaj z eksportu postępu.",true);return;}
  if (lastRaw !== null) {
    try {state=validate(JSON.parse(lastRaw));saveMessage("Wczytano Twój lokalny postęp.");}
    catch {corruptRaw=lastRaw; $("corrupt").hidden=false;saveMessage("Niepoprawny zapis zachowano bez zmian.",true);}
  } else saveMessage("Gotowe. Postęp zapisuje się lokalnie po każdej zmianie.");
  updateBackupButton();
}
function updateBackupButton() {try {$("previous-backup").hidden=!localStorage.getItem(BACKUP);}catch{$("previous-backup").hidden=true;}}
function renderStages() {
  $("quick-nav").innerHTML=DATA.stages.map(s=>'<button type="button" data-jump="'+s.id+'"><span class="dot" id="dot-'+s.id+'" aria-hidden="true"></span>'+esc(s.title)+'</button>').join("");
  $("stages").innerHTML=DATA.stages.map((s,i)=>'<details class="stage" id="'+s.id+'" '+(i===0?"open":"")+'><summary><span class="stage-number" aria-hidden="true">'+String(i+1).padStart(2,"0")+'</span><span class="stage-title"><strong>'+esc(s.title)+'</strong><small>'+esc(s.track)+'</small></span><span class="summary-meta"><span class="chip" id="chip-'+s.id+'">Do zrobienia</span><span class="check-count" id="count-'+s.id+'">0 / '+s.tasks.length+'</span></span><span class="chevron" aria-hidden="true">›</span></summary><div class="stage-body"><p class="when">'+esc(s.when)+'</p><fieldset class="tasks"><legend>Sprawdzenia do zaliczenia etapu</legend>'+s.tasks.map(t=>'<label class="task"><input type="checkbox" data-stage="'+s.id+'" data-check="'+t[0]+'" id="'+s.id+'-'+t[0]+'"><span>'+esc(t[1])+'</span></label>').join("")+'</fieldset><div class="fields"><div class="field"><label for="status-'+s.id+'">Status · '+esc(s.title)+'</label><select id="status-'+s.id+'" data-status="'+s.id+'">'+Object.entries(STATUSES).map(([key,name])=>'<option value="'+key+'">'+name+'</option>').join("")+'</select><small class="hint" id="status-hint-'+s.id+'">Zaliczenie po wszystkich sprawdzeniach.</small></div><div class="field"><label for="hours-'+s.id+'">Przepracowane godziny · '+esc(s.title)+'</label><input id="hours-'+s.id+'" data-hours="'+s.id+'" type="number" min="0" max="10000" step="any" inputmode="decimal" aria-describedby="hours-hint-'+s.id+'"><small id="hours-hint-'+s.id+'" class="hint">Wpisz łączny czas tego etapu, np. 1,5 h. Zakres: 0–10 000.</small></div><div class="field notes-field"><label for="notes-'+s.id+'">Notatki i dowody · '+esc(s.title)+'</label><textarea id="notes-'+s.id+'" data-notes="'+s.id+'" maxlength="10000" aria-describedby="notes-hint-'+s.id+'" placeholder="Co zrobiłem? Czego jeszcze nie rozumiem? Link do notatnika lub wyniku…"></textarea><small class="hint" id="notes-hint-'+s.id+'"><span id="notes-length-'+s.id+'">0</span> / 10 000 znaków · notatki pozostają lokalne</small></div></div><div class="stage-links"><button type="button" data-reading="'+s.id+'">Kursy i zadania tego etapu ↗</button><span class="completed-at" id="completed-'+s.id+'"></span></div></div></details>').join("");
  document.querySelectorAll("[data-notes]").forEach(node=>node.addEventListener("paste",event=>{
    const pasted=event.clipboardData?.getData("text") || "";
    if (node.value.length-(node.selectionEnd-node.selectionStart)+pasted.length>MAX_NOTES) {
      event.preventDefault(); toast("Tekst nie został wklejony: notatka może mieć do 10 000 znaków.");
    }
  }));
}
function syncInputs() {
  for (const s of DATA.stages) {
    const r=state.stages[s.id];
    $("status-"+s.id).value=r.status; $("hours-"+s.id).value=String(r.hours); $("notes-"+s.id).value=r.notes;
    $("hours-"+s.id).setCustomValidity(""); $("hours-"+s.id).removeAttribute("aria-invalid");
    $("hours-hint-"+s.id).textContent="Łączny czas tego etapu. Zakres: 0–10 000 godzin.";
    for(const t of s.tasks) $(s.id+"-"+t[0]).checked=r.checks[t[0]];
  }
  updateSummary();
}
function totals(source=state) {
  return {done:DATA.stages.filter(s=>source.stages[s.id].status==="done").length,
    checked:DATA.stages.reduce((sum,s)=>sum+Object.values(source.stages[s.id].checks).filter(Boolean).length,0),
    hours:DATA.stages.reduce((sum,s)=>sum+source.stages[s.id].hours,0)};
}
function updateSummary() {
  const t=totals(), max=DATA.stages.reduce((sum,s)=>sum+s.tasks.length,0);
  $("done-count").textContent=t.done+" / "+DATA.stages.length;
  $("checks-count").textContent=t.checked+" / "+max;
  $("hours-count").textContent=fmt(t.hours)+" h";
  $("overall-progress").max=max; $("overall-progress").value=t.checked;
  $("percent").textContent=Math.round(t.checked/max*100)+"%";
  for(const s of DATA.stages) {
    const r=state.stages[s.id], checked=Object.values(r.checks).filter(Boolean).length;
    $("chip-"+s.id).textContent=STATUSES[r.status]; $("chip-"+s.id).className="chip "+r.status;
    $("dot-"+s.id).className="dot "+r.status;
    $("count-"+s.id).textContent=checked+" / "+s.tasks.length;
    $("status-"+s.id).querySelector('option[value="done"]').disabled=checked!==s.tasks.length;
    $("status-"+s.id).value=r.status;
    $("notes-length-"+s.id).textContent=r.notes.length;
    $("completed-"+s.id).textContent=r.completedAt?"Zaliczono "+new Date(r.completedAt).toLocaleDateString("pl-PL"):"";
  }
  const next=DATA.stages.find(s=>state.stages[s.id].status==="active") || DATA.stages.find(s=>state.stages[s.id].status==="planned") || DATA.stages.find(s=>state.stages[s.id].status==="paused");
  $("continue").disabled=!next; $("continue").dataset.target=next?.id || "";
  $("next-title").textContent=next?next.title:"Wszystkie etapy zaliczone";
  $("next-label").textContent=next?"Proponowany następny krok":"Twój zapis postępu";
  $("continue").textContent=next?"Otwórz etap →":"Gotowe";
}
function selectView(view,focus=false) {
  for(const name of ["tracker","starter","library"]) $("view-"+name).hidden=name!==view;
  document.querySelectorAll("[data-view]").forEach(b=>{
    if(b.dataset.view===view)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current");
  });
  if(focus){$("main").scrollIntoView({block:"start"});}
}
function openStage(id) {
  if(!byId[id])return;selectView("tracker"); const d=$(id); d.open=true;
  d.scrollIntoView({block:"start",behavior:"auto"});d.querySelector("summary").focus({preventScroll:true});
}
function openReading(id) {
  selectView("library"); const d=$("reading-"+id);
  if(d){d.open=true;d.scrollIntoView({block:"start"});d.querySelector("summary").focus({preventScroll:true});}
}
function changed(id) {state.stages[id].updatedAt=now();updateSummary();persist();}
$("stages").addEventListener("change",event=>{
  const x=event.target;
  if(x.dataset.check) {
    const id=x.dataset.stage,r=state.stages[id];r.checks[x.dataset.check]=x.checked;
    if(r.status==="planned" && x.checked)r.status="active";
    if(r.status==="done" && !x.checked){r.status="active";r.completedAt=null;toast("Etap wrócił do „W trakcie”, bo odznaczono sprawdzenie.");}
    changed(id);
  } else if(x.dataset.status) {
    const id=x.dataset.status,r=state.stages[id];
    if(x.value==="done" && !Object.values(r.checks).every(Boolean)){x.value=r.status;toast("Najpierw wykonaj wszystkie sprawdzenia etapu.");return;}
    r.status=x.value;r.completedAt=r.status==="done"?(r.completedAt||now()):null;changed(id);
  }
});
$("stages").addEventListener("input",event=>{
  const x=event.target;
  if(x.dataset.hours) {
    const value=x.valueAsNumber;
    if(!Number.isFinite(value)||value<0||value>10000) {
      x.setCustomValidity("Podaj liczbę od 0 do 10 000.");x.setAttribute("aria-invalid","true");
      $("hours-hint-"+x.dataset.hours).textContent="Nie zapisano tej wartości. Podaj liczbę 0–10 000; poprzedni czas jest zachowany.";
      saveMessage("Nie zapisano niepoprawnej liczby godzin. Poprzednia wartość pozostaje zachowana.",true);return;
    }
    x.setCustomValidity("");x.removeAttribute("aria-invalid");
    $("hours-hint-"+x.dataset.hours).textContent="Łączny czas tego etapu. Zakres: 0–10 000 godzin.";
    state.stages[x.dataset.hours].hours=value;changed(x.dataset.hours);
  } else if(x.dataset.notes) {
    if(x.value.length>MAX_NOTES){saveMessage("Notatka jest za długa; poprzedni zapis pozostaje zachowany.",true);return;}
    state.stages[x.dataset.notes].notes=x.value;changed(x.dataset.notes);
  }
});
function download(text,filename) {
  const blob=new Blob([text],{type:"application/json;charset=utf-8"}),url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),3000);
}
function exportProgress() {
  download(JSON.stringify({...state,exportedAt:now()},null,2)+"\n","guidefold-postep-"+new Date().toISOString().slice(0,10)+".json");
  toast("Wyeksportowano kopię postępu.");
}
for(const id of ["export","export-current","export-before-import"]) $(id).addEventListener("click",exportProgress);
$("import").addEventListener("click",()=>$("import-file").click());
$("import-file").addEventListener("change",async event=>{
  const file=event.target.files?.[0];if(!file)return;
  try{
    if(file.size>2*1024*1024)throw new Error("Plik jest za duży (maksymalnie 2 MB).");
    const candidate=validate(JSON.parse(await file.text())); pendingImport=candidate;
    const t=totals(candidate);
    $("import-summary").textContent="Kopia: "+t.done+" zaliczonych etapów, "+t.checked+" sprawdzeń, "+fmt(t.hours)+" h. Notatki i pozostałe dane też zostaną wczytane.";
    $("import-dialog").showModal();
  }catch(error){pendingImport=null;toast("Nie wczytano pliku. "+(error instanceof SyntaxError?"Niepoprawny JSON.":error.message));}
  finally{event.target.value="";}
});
$("cancel-import").addEventListener("click",()=>{$("import-dialog").close();pendingImport=null;});
$("import-dialog").addEventListener("cancel",()=>{pendingImport=null;});
$("confirm-import").addEventListener("click",()=>{
  if(!pendingImport)return;
  try{if(localStorage.getItem(KEY)!==lastRaw){$("import-dialog").close();showConflict();return;}}catch{}
  try{localStorage.setItem(BACKUP,corruptRaw??JSON.stringify(state));}
  catch{toast("Import zatrzymany: nie można zapisać kopii poprzedniego postępu. Bieżące dane pozostają bez zmian. Wyeksportuj je i sprawdź miejsce lub uprawnienia przeglądarki.");return;}
  state=pendingImport;pendingImport=null;corruptRaw=null;$("corrupt").hidden=true;
  persist(true);syncInputs();updateBackupButton();$("import-dialog").close();
  toast(storageAvailable?"Wczytano i zapisano postęp.":"Wczytano postęp na tej stronie. Zapis lokalny nie działa — zachowaj eksport.");
});
$("previous-backup").addEventListener("click",()=>{
  try {const raw=localStorage.getItem(BACKUP);if(raw)download(raw,"guidefold-postep-przed-importem.json");}
  catch{toast("Kopia lokalna nie jest dostępna.");}
});
$("export-raw").addEventListener("click",()=>{if(corruptRaw!==null)download(corruptRaw,"guidefold-zachowany-zapis.json");});
$("new-storage").addEventListener("click",()=>{
  if(!confirm("Zastąpić niepoprawny zapis bieżącym postępem? Najpierw możesz pobrać zachowaną kopię."))return;
  try{localStorage.setItem(BACKUP,corruptRaw);}catch{}
  corruptRaw=null;$("corrupt").hidden=true;persist(true);updateBackupButton();
});
$("load-latest").addEventListener("click",()=>{
  try{
    const raw=localStorage.getItem(KEY),candidate=raw===null?newState():validate(JSON.parse(raw));
    state=candidate;lastRaw=raw;conflict=false;corruptRaw=null;$("conflict").hidden=true;$("corrupt").hidden=true;syncInputs();saveMessage("Wczytano najnowszy zapis z przeglądarki.");
  }catch{toast("Najnowszy zapis jest niepoprawny lub niedostępny. Bieżący postęp pozostaje bez zmian.");}
});
$("keep-current").addEventListener("click",()=>{
  if(!confirm("Zastąpić zapis z innej karty postępem widocznym na tej stronie?"))return;
  try{const raw=localStorage.getItem(KEY);if(raw!==null)localStorage.setItem(BACKUP,raw);}catch{}
  persist(true);updateBackupButton();
});
window.addEventListener("storage",event=>{if(event.key===KEY && event.newValue!==lastRaw)showConflict();});
document.addEventListener("click",event=>{
  const b=event.target.closest("button");if(!b)return;
  if(b.dataset.view)selectView(b.dataset.view,true);
  else if(b.dataset.jump)openStage(b.dataset.jump);
  else if(b.dataset.reading)openReading(b.dataset.reading);
});
$("continue").addEventListener("click",()=>openStage($("continue").dataset.target));
$("copy-prompt").addEventListener("click",async()=>{
  const text=$("learning-prompt").textContent;
  try{await navigator.clipboard.writeText(text);toast("Skopiowano prompt.");}
  catch{const range=document.createRange();range.selectNodeContents($("learning-prompt"));const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);toast("Zaznaczono prompt. Użyj kopiowania w przeglądarce.");}
});
document.querySelectorAll('a[href^="https://"]').forEach(a=>{a.target="_blank";a.rel="noopener noreferrer";});
loadInitial();renderStages();syncInputs();
})();
