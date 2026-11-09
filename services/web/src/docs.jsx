import React, { useEffect, useState } from 'react';
import gettingStarted from './guides/getting-started.md?raw';
import packs from './guides/packs.md?raw';
import evidence from './guides/evidence.md?raw';
import security from './guides/security.md?raw';
import prIntegration from './guides/pr-integration.md?raw';

const guides = [
  { id: 'getting-started', label: 'Getting Started', text: gettingStarted },
  { id: 'packs', label: 'Packs', text: packs },
  { id: 'evidence', label: 'Evidence', text: evidence },
  { id: 'security', label: 'Security', text: security },
  { id: 'pr-integration', label: 'PR Integration', text: prIntegration },
];

/** @param {string} text @returns {React.ReactNode[]} */
function renderGuide(text) {
  const lines = text.split(/\r?\n/);
  /** @type {React.ReactNode[]} */
  const result = [];
  for (let i = 0; i < lines.length;) {
    const line = lines[i];
    if (!line.trim()) { i += 1; continue; }
    if (line.startsWith('```')) {
      const start = i++;
      const code = [];
      while (i < lines.length && !lines[i].startsWith('```')) code.push(lines[i++]);
      i += 1;
      result.push(<pre key={start} tabIndex={0} aria-label="Codebeispiel, horizontal scrollbar"><code>{code.join('\n')}</code></pre>);
    } else if (line.startsWith('## ')) {
      result.push(<h4 key={i}>{line.slice(3)}</h4>); i += 1;
    } else if (line.startsWith('# ')) {
      result.push(<h3 key={i}>{line.slice(2)}</h3>); i += 1;
    } else if (line.startsWith('- ')) {
      const start = i;
      const items = [];
      while (i < lines.length && lines[i].startsWith('- ')) items.push(lines[i++].slice(2));
      result.push(<ul key={start}>{items.map((item, index) => <li key={index}>{item}</li>)}</ul>);
    } else {
      const start = i;
      const paragraph = [];
      while (i < lines.length && lines[i].trim() && !/^(# |## |- |```)/.test(lines[i])) paragraph.push(lines[i++]);
      result.push(<p key={start}>{paragraph.join(' ')}</p>);
    }
  }
  return result;
}

function currentGuide() {
  const id = window.location.hash.startsWith('#docs/') ? window.location.hash.slice(6) : '';
  return id ? guides.find((guide) => guide.id === id) : guides[0];
}

export function Documentation() {
  const [guide, setGuide] = useState(currentGuide);
  useEffect(() => {
    const onHashChange = () => setGuide(currentGuide());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);
  const organization = new URLSearchParams(window.location.search).get('organization');
  const orgQuery = organization ? `?${new URLSearchParams({ organization })}` : '';
  const article = guide ? <article className="panel docs-content" aria-label="Dokumentationsinhalt"><p className="pack-scroll-hint">Codeblöcke lassen sich horizontal scrollen.</p>{renderGuide(guide.text)}</article> : <div className="panel" role="alert"><h2>Anleitung nicht gefunden</h2><p>Wähle eine verfügbare Kategorie aus.</p></div>;
  const links = <aside className="panel docs-popular"><h2>Anleitungen</h2><ul><li><a href="#docs/getting-started">Erste Schritte →</a></li><li><a href="#docs/packs">Packs verstehen →</a></li><li><a href="#docs/evidence">Evidence und Bewertungen →</a></li><li><a href="#docs/security">Sicherheit und Identität →</a></li><li><a href="#docs/pr-integration">PR-Integration einrichten →</a></li></ul></aside>;
  return <section className="documentation" aria-labelledby="docs-title">
    <p className="eyebrow">LERNEN / DOKUMENTATION</p><div className="page-heading"><div><h1 id="docs-title">Dokumentation</h1><p>Anleitungen zur Plattform, ihren Grenzen und zur lokalen Einrichtung.</p></div><a className="team-back" href={`/packs${orgQuery}`}>Packs ansehen →</a></div>
    <nav aria-label="Dokumentationskategorien" className="docs-nav">
      {guides.map((item) => <a key={item.id} href={`#docs/${item.id}`} aria-current={item.id === guide?.id ? 'page' : undefined}>{item.label}</a>)}
    </nav>
    {guide?.id === 'getting-started' ? <><div className="docs-columns"><div className="panel docs-hero"><span aria-hidden="true">◎</span><h2>Specbound verstehen</h2><p>Verbinde versionierte Governance-Packs, betrachte Assessments und verfolge Ergebnisse bis zur gespeicherten Evidence.</p><div className="docs-actions"><a className="primary-link" href={`/packs${orgQuery}`}>Governance-Packs ansehen →</a><a className="team-back" href={`/providers${orgQuery}`}>Evidence Provider Packs →</a></div></div>{links}</div><div className="docs-steps"><div className="panel"><strong>01</strong><h2>Quellen verbinden</h2><p>Repositories und festgelegte Packrevisionen mit ihren Berechtigungen verbinden.</p></div><div className="panel"><strong>02</strong><h2>Assessments betrachten</h2><p>Gespeicherte Bewertungen beziehen sich auf einen konkreten Kontext und Commit.</p></div><div className="panel"><strong>03</strong><h2>Findings erklären</h2><p>Controls, Nachweise und fehlende Evidence bleiben nachvollziehbar.</p></div></div>{article}</> : <div className="docs-columns">{article}{links}</div>}
  </section>;
}
