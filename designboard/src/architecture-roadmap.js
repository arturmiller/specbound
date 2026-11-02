// ---- Separate workspaces: architecture and implementation roadmap (no external libraries).



const archMap=Object.fromEntries(ARCH_NODES.map(n=>[n.id,n]));
let mainView='screens',archTab='system',selectedArch='evaluate',deployProfile='k8s';
let roadmap={epic:'E01',task:'T001',search:'',phase:'all',openOnly:false,done:{}};
try{let previous=JSON.parse(localStorage.getItem('governance-roadmap-progress-v1')||'{}');if(previous&&typeof previous==='object')roadmap.done=previous;}catch(e){}
const allTasks=VIEW_EPICS.flatMap(e=>e.features.flatMap(f=>f.tasks));
const findTask=(id)=>allTasks.find(t=>t.id===id);
function changeView(next){
  if(!['screens','architecture','plan'].includes(next))return;
  mainView=next;document.body.classList.toggle('mode-architecture',next==='architecture');document.body.classList.toggle('mode-plan',next==='plan');
  $('#architecture-surface').hidden=next!=='architecture';$('#plan-surface').hidden=next!=='plan';$('#view-mode').value=next;
  if(next==='architecture')renderArchitecture();if(next==='plan')renderRoadmap();if(next==='screens')requestAnimationFrame(()=>{if(preview)renderPreview();else updateTransform()});
}
function saveRoadmap(){save()}
function renderArchitecture(){
  $$('#architecture-surface [data-arch-tab]').forEach(x=>x.classList.toggle('active',x.dataset.archTab===archTab));
  $('#deploy-target').value=deployProfile;
  $('#architecture-diagram').innerHTML=archTab==='system'?systemDiagram():archTab==='flow'?flowDiagram():deploymentDiagram();
  let n=archMap[selectedArch]||archMap.evaluate;
  if(archTab==='flow'){
    $('#architecture-inspector').innerHTML='<h2>Asynchrone Assessments</h2><p class="sub">Dieselben Kontrollverträge – zwei getrennte Anlässe.</p><p>Ein PR-Push prüft den HEAD-Commit und aktualisiert genau einen PR-Kommentar. Eine Pack-Aktivierung oder ein Zeitplan prüft dagegen die bereits deployte Baseline.</p><div class="arch-assertion">Bewertungs-Snapshot enthält <b>target revision</b>, <b>pack revision</b>, <b>evidence scope</b> und <b>collector version</b>. Fehlende Evidenz führt zu UNKNOWN.</div>';
  }else if(archTab==='deploy'){
    const map={k8s:['Kubernetes (beliebiger Anbieter)','Deployments, Services, Helm, Kubernetes Job/worker, PostgreSQL, S3-kompatibler Bucket','Cluster-RBAC, network policies, OCI image runner'],ecs:['AWS ECS / Fargate','ECS services, ALB, RDS PostgreSQL, S3; Collector als isolierter Fargate Task','Task roles, separate task definition, private network'],local:['Lokal · Docker Compose','Web/API/Worker, PostgreSQL, MinIO, separater Demo-Collector','Docker-Netzwerk, dev secrets, Integrationstests']};
    let p=map[deployProfile];$('#architecture-inspector').innerHTML=`<h2>${p[0]}</h2><p class="sub">Hosting-Profil statt eigener Fachlogik</p><p>${p[1]}</p><div class="arch-assertion">${p[2]}</div><p>Alle drei Profile betreiben dieselben OCI-Images und verwenden dieselben API-, Daten- und Collector-Verträge. Nur die Laufzeit- und Secret-Adapter unterscheiden sich.</p>`;
  }else{
    $('#architecture-inspector').innerHTML=`<span class="arch-badge">${n.kind==='core'?'PLATFORM CORE':n.kind==='external'?'EXTERNE QUELLE':n.kind==='storage'?'STATE':n.kind==='runner'?'PACK-RUNTIME':'OUTPUT'}</span><h2>${esc(n.title)}</h2><p class="sub">${esc(n.sub)}</p><p>${esc(n.detail)}</p><div class="arch-assertion"><b>Invariant / Sicherheitsgrenze</b><p style="margin:6px 0 0;color:inherit">${esc(n.invariant)}</p></div>`;
  }
}
function systemDiagram(){
 const color={external:['#f0f4f9','#91a8c0'],core:['#ecf3ff','#7daaf1'],storage:['#e9f7f2','#54ac92'],runner:['#fff7e9','#d9b26f'],output:['#eef5ff','#84afea']};
 const edgePath=(a,b)=>{const p=archMap[a],q=archMap[b];if(!p||!q)return '';
   let startX=p.x+p.w/2,startY=p.y+p.h/2,endX=q.x+q.w/2,endY=q.y+q.h/2;
   if(q.x>=p.x+p.w){startX=p.x+p.w;endX=q.x;return `M${startX},${startY} H${(startX+endX)/2} V${endY} H${endX}`}
   if(q.y>=p.y+p.h){startY=p.y+p.h;endY=q.y;return `M${startX},${startY} V${(startY+endY)/2} H${endX} V${endY}`}
   return `M${startX},${startY} L${endX},${endY}`};
 return `<svg viewBox="0 0 1195 745" role="img" aria-label="Klickbare Systemkomponenten und Architekturbeziehungen"><defs><marker id="archarrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10Z" fill="#acc0d8"/></marker></defs><g stroke="#a9bdd4" stroke-width="1.8" fill="none" opacity="0.74" marker-end="url(#archarrow)">${ARCH_EDGES.map(([a,b])=>`<path d="${edgePath(a,b)}"/>`).join('')}</g>${ARCH_NODES.map(n=>{const [fill,stroke]=color[n.kind]||color.core;return `<g class="arch-svg-node ${n.id===selectedArch?'selected':''}" data-arch-node="${n.id}" role="button" tabindex="0" aria-label="${esc(n.title)}"><rect x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="13" fill="${fill}" stroke="${stroke}" stroke-width="1.7"/><text x="${n.x+16}" y="${n.y+31}" fill="#193355" font-size="15" font-weight="750">${esc(n.title)}</text><text x="${n.x+16}" y="${n.y+52}" fill="#638099" font-size="11">${esc(n.sub)}</text></g>`}).join('')}<text x="45" y="28" font-size="12" fill="#8a9db3">QUELLEN / AKTEURE</text><text x="342" y="28" font-size="12" fill="#8a9db3">KERN & ORCHESTRIERUNG</text><text x="924" y="28" font-size="12" fill="#8a9db3">SPEICHER / ISOLATION</text></svg>`;
}
function flowDiagram(){return `<div class="flow-timeline">${[['1 · Git push','Mensch oder Agent erstellt Commit'],['2 · Webhook','Event deduplizieren'],['3 · Assessment','Pack-SHA + Produkt-SHA pinnen'],['4 · Evidence','Provider-Runner isoliert'],['5 · Ergebnis','Vier Zahlen + ein Berichtslink'],['6 · Recheck','Nächster Push startet neue Runde']].map((s,i)=>`<div class="flow-step" data-arch-flow="${i}"><b>${s[0]}</b><span>${s[1]}</span></div>${i===5?'':'<span class="flow-arrow">→</span>'}`).join('')}</div><div class="flow-lanes"><div class="flow-lane"><h3>① PR-Lane</h3><p><b>Auslöser:</b> Pull Request opened / synchronize</p><p>Input = aktueller Head SHA. Output = genau ein aktualisierter Git-Kommentar + separater Commit-Check.</p><p>Fehlerkorrektur findet ausschließlich im Git-Workflow statt; das Portal beauftragt weder Mensch noch KI-Agent.</p></div><div class="flow-lane"><h3>② Baseline-Lane</h3><p><b>Auslöser:</b> neues Pack, geänderte Konfiguration oder Zeitplan</p><p>Input = inventarisierte Deployment-Revision und frische Infrastrukturbeobachtung. Output = eigenständige Findings.</p><p>PR-Nachweise und Baseline-Nachweise sind getrennte Assessment-Kontexte.</p></div></div>`}
function deploymentDiagram(){const cfg={k8s:['Helm release','Kubernetes Deployment · API + UI','Worker Deployment · concurrency','Collector Kubernetes Job','PostgreSQL · CloudNativePG / managed','S3-compatible bucket / MinIO'],ecs:['ECS service','Fargate service · API + UI','Fargate service · worker','Isolated Fargate task · collector','RDS PostgreSQL','S3 via BlobStore adapter'],local:['Docker Compose','Container · API + UI','Container · worker','Isolated container · collector','PostgreSQL container','MinIO local object store']};const data=cfg[deployProfile];return `<div class="deploy-grid"><div class="deploy-col"><h3>Deployment Controller</h3><div class="dep-piece">${data[0]}</div><div class="dep-arrow">↓</div><div class="dep-piece">${data[1]}</div><div class="dep-piece">${data[2]}</div></div><div class="deploy-col"><h3>Execution / Trust Boundary</h3><div class="dep-piece">OCI images versioned by digest</div><div class="dep-arrow">↓</div><div class="dep-piece">${data[3]}</div><div class="dep-piece">Secrets via environment-specific adapters</div></div><div class="deploy-col"><h3>Durable State</h3><div class="dep-piece">${data[4]}</div><div class="dep-piece">${data[5]}</div><div class="dep-piece">Schema migrations run as one-off job</div></div></div><div class="deploy-notes"><b>Portabilität:</b> Der Plattform-Code ist identisch. Deployment-Charts bzw. IaC konfigurieren die gleichen Env-Variablen und Schnittstellen. AWS ist eine mögliche Ausführungsumgebung; Kubernetes kann auf AWS, Azure, On-Premises oder anderswo laufen. <b>Terraform gehört – wenn verwendet – in den separat freigegebenen Provider-Collector.</b></div>`}
function downloadArtifact(name,value){const obj=new Blob([JSON.stringify(value,null,2)],{type:'application/json'}),url=URL.createObjectURL(obj),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function renderRoadmap(){
 const done=allTasks.filter(t=>!!roadmap.done[t.id]).length;
 const countPhase=phase=>allTasks.filter(t=>VIEW_EPICS.some(e=>e.phase===phase&&e.features.some(f=>f.tasks.some(x=>x.id===t.id)))).length;
 $('#plan-stats').innerHTML=[[VIEW_EPICS.length,'Epics'],[VIEW_EPICS.reduce((n,e)=>n+e.features.length,0),'Features'],[allTasks.length,'konkrete Tasks'],[done,'lokal erledigt'],[countPhase('MVP'),'Tasks im MVP']].map(x=>`<div class="plan-stat"><b>${x[0]}</b><small>${x[1]}</small></div>`).join('');
 $('#epic-menu-list').innerHTML=VIEW_EPICS.map(e=>`<button class="epic-select ${roadmap.epic===e.id?'active':''}" data-epic="${e.id}"><b>${e.id} · ${esc(e.title)}</b><small>${e.phase} · ${e.features.reduce((n,f)=>n+f.tasks.length,0)} Tasks</small></button>`).join('');
 $('#task-search').value=roadmap.search;$('#phase-filter').value=roadmap.phase;$('#open-only').checked=roadmap.openOnly;
 let epic=VIEW_EPICS.find(e=>e.id===roadmap.epic)||VIEW_EPICS[0];
 let term=roadmap.search.toLowerCase().trim();
 let selected=roadmap.task;
 let visible=epic.features.map(f=>({...f,tasks:f.tasks.filter(t=>(!term||[t.id,t.title,t.output,t.accept].join(' ').toLowerCase().includes(term))&&(!roadmap.openOnly||!roadmap.done[t.id]))})).filter(f=>f.tasks.length);
 if(roadmap.phase!=='all'&&epic.phase!==roadmap.phase)visible=[];
 $('#plan-content').innerHTML=`<div><span class="pill blue">${epic.phase}</span><h2 style="margin:7px 0 5px;font-size:21px">${esc(epic.title)}</h2><p style="font-size:12px;color:#687a90;line-height:1.6">${esc(epic.goal)}</p></div>`+ (visible.length?visible.map(f=>`<section class="feature-section"><header class="feature-heading"><strong>${f.id} · ${esc(f.title)}</strong><small>${esc(f.goal)}</small></header>${f.tasks.map(t=>`<div class="task-row ${selected===t.id?'selected':''}" data-task="${t.id}"><span class="task-id">${t.id}</span><div><div class="task-name">${esc(t.title)}</div><div class="task-description">${esc(t.output)}</div></div><span class="task-state">${roadmap.done[t.id]?'✓ Done':'○ Open'}</span></div>`).join('')}</section>`).join(''):'<p class="empty">Keine Tasks entsprechen dem Filter. Wechsel die Phase oder lösche den Suchbegriff.</p>');
 const t=findTask(selected)||allTasks[0];
 let featureNode=VIEW_EPICS.flatMap(e=>e.features).find(f=>f.tasks.some(x=>x.id===t.id));
 $('#task-details').innerHTML=`<span class="pill blue">${t.id}</span><h2>${esc(t.title)}</h2><p style="color:#7889a0;margin:6px 0">${featureNode?.id||''} · ${esc(featureNode?.title||'')}</p><h3>Konkretes Ergebnis</h3><p>${esc(t.output)}</p><h3>Abnahme / Nachweis</h3><p>${esc(t.accept)}</p><h3>Vorbedingungen</h3><div>${t.deps.length?t.deps.map(id=>`<button class="dep-chip" data-task-link="${id}">${id}</button>`).join(''):'<span class="caption">Keine – unabhängig startbar.</span>'}</div><h3>Planungsstatus</h3><p>Dieser Status ist nur für die Entwurfsplanung lokal gespeichert, kein Issue-Tracker und kein Backend.</p><button class="state-toggle ${roadmap.done[t.id]?'done':''}" id="toggle-task-done">${roadmap.done[t.id]?'↶ Als offen markieren':'✓ Als erledigt markieren'}</button>`;
}
function pickTask(id){const t=findTask(id);if(!t)return;const e=VIEW_EPICS.find(e=>e.features.some(f=>f.tasks.some(z=>z.id===id)));roadmap.epic=e.id;roadmap.task=id;roadmap.search='';roadmap.phase='all';roadmap.openOnly=false;renderRoadmap()}
$('#view-mode').addEventListener('change',e=>changeView(e.target.value));
$('#architecture-surface').addEventListener('click',e=>{const tab=e.target.closest('[data-arch-tab]'),node=e.target.closest('[data-arch-node]');if(tab){archTab=tab.dataset.archTab;renderArchitecture()}if(node){selectedArch=node.dataset.archNode;renderArchitecture()}});
$('#architecture-surface').addEventListener('keydown',e=>{const n=e.target.closest('[data-arch-node]');if(n&&(e.key==='Enter'||e.key===' ')){e.preventDefault();selectedArch=n.dataset.archNode;renderArchitecture()}});
$('#deploy-target').addEventListener('change',e=>{deployProfile=e.target.value;renderArchitecture()});
$('#export-architecture').addEventListener('click',()=>downloadArtifact('governance-architecture.json',{nodes:ARCH_NODES,edges:ARCH_EDGES,profiles:['k8s','ecs','local'],principle:'Cloud-neutral core, pack-owned collectors'}));
$('#export-plan').addEventListener('click',()=>downloadArtifact('governance-development-plan.json',{version:1,epics:VIEW_EPICS,localProgress:roadmap.done}));
$('#reset-progress').addEventListener('click',()=>{if(!window.confirm('Lokale Task-Status wirklich zurücksetzen?'))return;roadmap.done={};saveRoadmap();renderRoadmap()});
$('#epic-menu-list').addEventListener('click',e=>{const el=e.target.closest('[data-epic]');if(el){roadmap.epic=el.dataset.epic;const epi=VIEW_EPICS.find(x=>x.id===roadmap.epic);roadmap.task=epi.features[0].tasks[0].id;renderRoadmap()}});
$('#plan-content').addEventListener('click',e=>{let el=e.target.closest('[data-task]');if(el){roadmap.task=el.dataset.task;renderRoadmap()}});
$('#task-details').addEventListener('click',e=>{let d=e.target.closest('[data-task-link]');if(d){pickTask(d.dataset.taskLink);return}if(e.target.closest('#toggle-task-done')){roadmap.done[roadmap.task]=!roadmap.done[roadmap.task];saveRoadmap();renderRoadmap()}});
$('#task-search').addEventListener('input',e=>{roadmap.search=e.target.value;renderRoadmap();let field=$('#task-search');field.focus();field.setSelectionRange(field.value.length,field.value.length)});
$('#phase-filter').addEventListener('change',e=>{roadmap.phase=e.target.value;renderRoadmap()});
$('#open-only').addEventListener('change',e=>{roadmap.openOnly=e.target.checked;renderRoadmap()});
