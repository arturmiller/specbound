/** @param {{observedAt: string, expiresAt: string}} item @param {number} now */
export function evidenceFreshness(item, now) {
  const observed = Date.parse(item.observedAt);
  const expires = Date.parse(item.expiresAt);
  if (!Number.isFinite(observed) || !Number.isFinite(expires) || observed > now || expires <= observed) return 'UNKNOWN';
  return expires <= now ? 'Abgelaufen · UNKNOWN' : 'Zeitlich gültig';
}
