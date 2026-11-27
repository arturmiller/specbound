import React, { useState } from 'react';

const dateFormat = new Intl.DateTimeFormat('de-DE', { dateStyle: 'short', timeStyle: 'short' });
const pageSize = 10;

/** @typedef {{PASS: number, FAIL: number, UNKNOWN: number}} EvaluationCounts */

/** @param {EvaluationCounts | null | undefined} counts */
export function resultBadge(counts) {
  if (counts?.FAIL) {
    return { status: `${counts.FAIL} ${counts.FAIL === 1 ? 'Verstoß' : 'Verstöße'}`, tone: 'fail' };
  }
  if (!counts?.PASS || counts.UNKNOWN > 0) return { status: 'Ungeklärt', tone: 'unknown' };
  return { status: '0 Verstöße', tone: 'not_applicable' };
}

/** @param {string} value */
export function runDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : dateFormat.format(date);
}

/** @param {{runs: {id: string, href: string, label: string, createdAt: string, status: string, tone?: string}[], label: string}} props */
export function RunList({ runs, label }) {
  const [limit, setLimit] = useState(pageSize);
  return <>
    <ul className="run-list" aria-label={label}>
      {runs.slice(0, limit).map((run) => <li key={run.id}>
        <a href={run.href} className="run-list-row">
          <strong>{run.label}</strong>
          <time dateTime={run.createdAt}>{runDate(run.createdAt)}</time>
          <span className={'assessment-status status-' + (run.tone || 'not_applicable')}>{run.status}</span>
          <span className="run-list-arrow" aria-hidden="true">→</span>
        </a>
      </li>)}
    </ul>
    {runs.length > limit && <button className="run-list-more" onClick={() => setLimit(limit + pageSize)}>Weitere Läufe anzeigen</button>}
  </>;
}
