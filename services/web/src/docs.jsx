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
      result.push(<pre key={start}><code>{code.join('\n')}</code></pre>);
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
  return guides.find((guide) => guide.id === id) || guides[0];
}

export function Documentation() {
  const [guide, setGuide] = useState(currentGuide);
  useEffect(() => {
    const onHashChange = () => setGuide(currentGuide());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);
  return <section className="documentation" aria-labelledby="docs-title">
    <h2 id="docs-title">Dokumentation</h2>
    <nav aria-label="Dokumentationskategorien" className="docs-nav">
      {guides.map((item) => <a key={item.id} href={`#docs/${item.id}`} aria-current={item.id === guide.id ? 'page' : undefined}>{item.label}</a>)}
    </nav>
    <article className="panel docs-content" aria-label="Dokumentationsinhalt">{renderGuide(guide.text)}</article>
  </section>;
}
