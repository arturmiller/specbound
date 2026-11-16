import React from 'react';

/** @param {{path: string, onPath: (value: string) => void, refType: string, onRefType: (value: string) => void, defaultPath: string}} props */
export function ManifestSourceFields({ path, onPath, refType, onRefType, defaultPath }) {
  return <>
    <label className="field">Ref-Typ<select aria-label="Ref-Typ" value={refType} onChange={(event) => onRefType(event.target.value)}><option value="tag">Release-Tag</option><option value="branch">Branch</option><option value="commit">Commit</option></select></label>
    <label className="field">Manifestpfad<input value={path} onChange={(event) => onPath(event.target.value)} maxLength={500} placeholder={defaultPath} /><small>Relativ zur Repository-Wurzel. Ohne Eingabe: {defaultPath}.</small></label>
  </>;
}

/** @param {{source: {repository: string, commit: string, tag?: string, ref?: string, refType?: string, manifestPath?: string, schemaUrl?: string, manifestUrl?: string, commitUrl?: string}, defaultPath: string}} props */
export function ManifestProvenance({ source, defaultPath }) {
  const root = `https://github.com/${source.repository}`;
  const path = source.manifestPath || defaultPath;
  return <p className="break-value">Manifest: <a href={source.manifestUrl || `${root}/blob/${source.commit}/${path}`}>{path}</a>{' · '}{source.refType || 'tag'}: {source.ref || source.tag}{' · '}Revision: <a href={source.commitUrl || `${root}/commit/${source.commit}`}>{source.commit.slice(0, 12)}</a>{source.schemaUrl && <>{' · '}<a href={source.schemaUrl}>Schema ansehen</a></>}</p>;
}
