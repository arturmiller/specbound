// Proposed configuration model for the UI prototype, not a backend contract.
const resourceTypes = {
  Product: { label: 'Produkte', singular: 'Produkt', path: 'products/audio-visualizer.json', spec: { repositories: ['djfun/audio-visualizer-python'], profile: { id: 'application-baseline', version: '1.0.0' } }, description: 'Der Prüfgegenstand und das ausdrücklich zugeordnete Profil.' },
  ControlCatalog: { label: 'Kataloge', singular: 'Katalog', path: 'catalogs/application.json', spec: { controls: ['controls/licenses.json', 'controls/api-auth.json', 'controls/encryption.json', 'controls/backups.json'] }, description: 'Gruppierte Controls als wiederverwendbare Anforderungen.' },
  ControlProfile: { label: 'Profile', singular: 'Profil', path: 'profiles/application-baseline.json', spec: { catalog: { id: 'application-controls', version: '1.0.0' }, includeControls: ['PY-LIC-001', 'SEC-API-001', 'PRIV-001', 'OPS-001'] }, description: 'Explizite Auswahl von Controls für Produkte.' },
  EvidenceProviderPack: { label: 'Evidence Packs', singular: 'Evidence Pack', path: 'evidence/python-licenses/pack.json', spec: { capabilities: ['python.package-license/v1'], runtime: { image: 'example/license-collector@sha256:' + 'a'.repeat(64) }, inputSchema: 'schemas/input.json', outputSchema: 'schemas/output.json' }, description: 'Beschreibt die Ermittlung von Nachweisen, Laufzeit und Datenverträge.' }
};
const resourceExamples = {
  Product: ['audio-visualizer', 'Audio Visualizer'], ControlCatalog: ['application-controls', 'Application Controls'], ControlProfile: ['application-baseline', 'Application Baseline'], EvidenceProviderPack: ['python-licenses', 'Python-Lizenzen']
};
const configSchemas = Object.fromEntries(Object.keys(resourceTypes).map(kind => [kind, {
  $schema: 'https://json-schema.org/draft/2020-12/schema', $id: `urn:specbound:design:v1:${kind}`,
  title: `${kind} – Schemavorschlag`, type: 'object', additionalProperties: false,
  required: ['apiVersion', 'kind', 'metadata', 'spec'], properties: {
    apiVersion: { const: 'specbound.design/v1' }, kind: { const: kind },
    metadata: { type: 'object', additionalProperties: false, required: ['id', 'name', 'version'], properties: { id: { type: 'string', minLength: 1 }, name: { type: 'string', minLength: 1 }, version: { type: 'string', minLength: 1 } } },
    spec: { type: 'object', additionalProperties: false, required: Object.keys(resourceTypes[kind].spec), properties: {} }
  }
}]));
const textSchema = { type: 'string', minLength: 1 };
const refSchema = { type: 'object', additionalProperties: false, required: ['id', 'version'], properties: { id: textSchema, version: textSchema } };
configSchemas.Product.properties.spec.properties = { repositories: { type: 'array', minItems: 1, items: textSchema }, profile: refSchema };
configSchemas.ControlCatalog.properties.spec.properties = { controls: { type: 'array', minItems: 1, items: textSchema } };
configSchemas.ControlProfile.properties.spec.properties = { catalog: refSchema, includeControls: { type: 'array', minItems: 1, items: textSchema } };
configSchemas.EvidenceProviderPack.properties.spec.properties = { capabilities: { type: 'array', minItems: 1, items: textSchema }, runtime: { type: 'object', additionalProperties: false, required: ['image'], properties: { image: textSchema } }, inputSchema: textSchema, outputSchema: textSchema };
let registryKind = 'Product';
const escapeConfig = s => String(s).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
function exampleManifest(kind) { return { apiVersion: 'specbound.design/v1', kind, metadata: { id: resourceExamples[kind][0], name: resourceExamples[kind][1], version: '1.0.0' }, spec: structuredClone(resourceTypes[kind].spec) }; }
function validateConfig(value, schema, path = '$') {
  if (schema.const !== undefined && value !== schema.const) return `${path}: Erwartet ${schema.const}`;
  if (schema.type === 'object') {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return `${path}: Objekt erwartet`;
    for (const key of schema.required || []) if (!(key in value)) return `${path}.${key}: Pflichtfeld fehlt`;
    for (const key of Object.keys(value)) {
      if (!(key in schema.properties)) return `${path}.${key}: Unbekanntes Feld`;
      const error = validateConfig(value[key], schema.properties[key], `${path}.${key}`); if (error) return error;
    }
  }
  if (schema.type === 'string' && (typeof value !== 'string' || value.length < (schema.minLength || 0))) return `${path}: Nichtleerer Text erwartet`;
  if (schema.type === 'array') {
    if (!Array.isArray(value) || value.length < (schema.minItems || 0)) return `${path}: Nichtleere Liste erwartet`;
    for (let i = 0; i < value.length; i++) { const error = validateConfig(value[i], schema.items, `${path}[${i}]`); if (error) return error; }
  }
  return '';
}
function resourceTable(kind) {
  const type = resourceTypes[kind]; const extra = kind === 'EvidenceProviderPack';
  return `<div class="eyebrow">As Code / ${type.label}</div><div class="row spread"><div><h1>${type.label}</h1><p class="lead">${type.description}</p></div><button class="btn" data-register="${kind}">Manifest registrieren</button></div><div class="card"><h2>Registrierte Quellen · Beispieldaten</h2><div class="scroll"><table class="table"><thead><tr><th>Name / Version</th><th>Repository und Manifest</th><th>Stand</th><th></th></tr></thead><tbody><tr><td><b>${resourceExamples[kind][1]}</b><p>1.0.0</p></td><td>example/governance<br><span class="muted">${type.path}</span></td><td>Entwurf<br><span class="muted">Revision nicht aufgelöst</span></td><td><button data-manifest="${kind}">Konfiguration ansehen →</button></td></tr>${extra?'<tr><td><b>Cloud-Konfiguration</b><p>1.0.0</p></td><td>example/governance<br><span class="muted">evidence/cloud-config/pack.json</span></td><td>Entwurf</td><td><span class="muted">Zweites Pack im selben Repository</span></td></tr>':''}</tbody></table></div>${kind==='Product'?'<p><button class="link" data-open-product>Audio Visualizer öffnen →</button></p>':''}</div><p class="muted">Dateipfade, Manifeste und Zuordnungen sind Vorschläge für den Entwurf; es wurde kein Repository importiert.</p>`;
}
function manifestRelations(kind) {
  if (kind==='Product') return `<div class="card profile-context"><h2>Ausdrücklich zugeordnetes Profil</h2><p>Application Baseline · 1.0.0</p><button class="link" data-manifest="ControlProfile">Profil und ausgewählte Controls öffnen →</button><p class="muted">Profilzuordnung im Entwurf; Quellenrevision noch nicht aufgelöst.</p></div>`;
  if (kind==='ControlProfile') return `<div class="card profile-context"><h2>Herkunft und Auswahl</h2><p><b>Katalog:</b> Application Controls · 1.0.0</p><button class="link" data-manifest="ControlCatalog">Katalog und Control-Definitionen öffnen →</button><h3 style="margin-top:18px">Explizit ausgewählte Controls</h3>${prototypeControls.map(c=>`<p><b>${c.id}</b> · ${c.name}</p>`).join('')}<p class="muted">Die Profilrevision ist noch nicht aufgelöst. Die drei ergänzenden Controls sind illustrative Definitionen.</p><p>Änderungen an der Auswahl erfolgen im Profilmanifest. Ein Produktwechsel auf ein anderes Profil erfolgt im Produktmanifest.</p><button class="link" data-manifest="Product">Verwendendes Produkt ansehen →</button></div>`;
  if (kind==='ControlCatalog') return `<div class="card profile-context"><h2>Controls im Katalog</h2>${prototypeControls.map(c=>`<details class="trace"><summary>${c.group} · ${c.id}</summary><h3>${c.name}</h3><p>${c.requirement}</p><p class="muted">${c.example?'Illustratives Control.':'Angelehnt an das Lizenzscan-Beispiel; keine rückwirkend belegte Katalogzugehörigkeit.'}</p></details>`).join('')}<p><button class="link" data-manifest="ControlProfile">Auswahl im Profil ansehen →</button></p></div>`;
  return `<div class="card profile-context"><h2>Verwendung und Freigabe</h2><p>Das Manifest ist eine vorgeschlagene Pack-Konfiguration. Der historische öffentliche Lizenzscan wurde ohne dieses Pack ausgeführt.</p><p class="muted">Strukturprüfung, fachliche Kompatibilität und Ausführungsfreigabe sind getrennte Entscheidungen.</p></div>`;
}
function registryScreen(view) {
  const kind = Object.keys(resourceTypes).find(k => resourceTypes[k].label === view);
  if (kind) return resourceTable(kind);
  if (view === 'Manifest') { const k = registryKind; return `<div class="eyebrow">${resourceTypes[k].label} / Konfiguration</div><h1>${resourceExamples[k][1]}</h1><p class="lead">Manifestdatei, Schema und verwendete Version gemeinsam ansehen.</p>${manifestRelations(k)}<div class="card"><p><b>Repository:</b> example/governance · Beispieladresse</p><p><b>Datei:</b> ${resourceTypes[k].path}</p><p><b>Gewünschter Ref:</b> main · <b>Verwendeter Commit:</b> noch nicht aufgelöst</p><p><b>Schema:</b> urn:specbound:design:v1:${k} · Vorschlag</p><pre style="overflow:auto;padding:16px;background:#f3f5fa">${escapeConfig(JSON.stringify(exampleManifest(k), null, 2))}</pre><details><summary>Schema ansehen</summary><pre style="overflow:auto">${escapeConfig(JSON.stringify(configSchemas[k],null,2))}</pre></details><p class="muted">Relative Dateipfade werden im Vorschlag vom Verzeichnis der Manifestdatei aus aufgelöst. Änderungen entstehen durch Commits im Repository.</p><button class="link" data-resource="${k}">← Zurück zur Liste</button></div>`; }
  if (view === 'Registrieren') return `<div class="eyebrow">As Code / Quelle hinzufügen</div><h1>Manifest registrieren</h1><p class="lead">Eine Ressource wird durch Repository, Revision und Dateipfad identifiziert.</p><div class="card"><div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(220px,1fr))"><label>Typ<select id="registry-type" style="display:block;width:100%;padding:10px;margin-top:8px">${Object.entries(resourceTypes).map(([k,t])=>`<option value="${k}" ${k===registryKind?'selected':''}>${t.singular}</option>`).join('')}</select></label><label>Repository<input id="registry-repo" value="example/governance" style="display:block;width:100%;padding:10px;margin-top:8px"></label><label>Ref / Tag / Commit<input id="registry-ref" value="main" style="display:block;width:100%;padding:10px;margin-top:8px"></label><label>Manifestpfad<input id="registry-path" value="${resourceTypes[registryKind].path}" style="display:block;width:100%;padding:10px;margin-top:8px"></label></div><p><b>Schema:</b> <span id="registry-schema">urn:specbound:design:v1:${registryKind}</span> · Vorschlag</p><p class="muted">Im Portal würde die Datei aus dem Repository geladen. Im Entwurf bearbeitest du unten eine lokale JSON-Kopie.</p><label>Manifestvorschau<textarea id="registry-json" rows="17" spellcheck="false" style="display:block;width:100%;padding:14px;margin:10px 0;font-family:monospace">${escapeConfig(JSON.stringify(exampleManifest(registryKind),null,2))}</textarea></label><button class="btn" id="validate-config">Vorschau prüfen</button><p id="registry-feedback" role="status"></p><details><summary>Was wird dabei geprüft?</summary><p>Die lokale Feldprüfung prüft Pflichtfelder, Typ, API-Version und die Struktur des Schemavorschlags. Repository-Zugriff, Referenzauflösung, Laufzeitfreigaben und Speicherung sind hier nicht angebunden.</p></details></div><p class="muted">Der Manifestpfad ist Teil der Identität: evidence/python-licenses/pack.json und evidence/cloud-config/pack.json können zwei Packs im selben Repository bezeichnen.</p>`;
}
function mountRegistry(navigate, openProduct) {
  document.querySelectorAll('[data-resource]').forEach(b=>b.onclick=()=>navigate(resourceTypes[b.dataset.resource].label));
  document.querySelectorAll('[data-register]').forEach(b=>b.onclick=()=>{registryKind=b.dataset.register;navigate('Registrieren');});
  document.querySelectorAll('[data-manifest]').forEach(b=>b.onclick=()=>{registryKind=b.dataset.manifest;navigate('Manifest');});
  document.querySelectorAll('[data-open-product]').forEach(b=>b.onclick=openProduct);
  const type = document.getElementById('registry-type');
  if (type) type.onchange=()=>{registryKind=type.value;document.getElementById('registry-json').value=JSON.stringify(exampleManifest(registryKind),null,2);document.getElementById('registry-path').value=resourceTypes[registryKind].path;document.getElementById('registry-schema').textContent=`urn:specbound:design:v1:${registryKind}`;document.getElementById('registry-feedback').textContent='';};
  const check = document.getElementById('validate-config');
  if (check) check.onclick=()=>{
    let error=''; try {
      for (const id of ['registry-repo','registry-ref','registry-path']) if (!document.getElementById(id).value.trim()) error='Repository, Revision und Pfad müssen ausgefüllt sein.';
      const path=document.getElementById('registry-path').value;
      if (path.startsWith('/')||path.includes('..')||path.includes('\\')) error='Manifestpfad muss ein relativer Dateipfad ohne .. sein.';
      const parsed=JSON.parse(document.getElementById('registry-json').value);error=error||validateConfig(parsed,configSchemas[registryKind]);
    }catch{error='Manifestvorschau ist kein gültiges JSON.';}
    document.getElementById('registry-feedback').textContent=error||'Lokale Feldprüfung bestanden. Quelle nicht geladen und nichts gespeichert.';
  };
}
