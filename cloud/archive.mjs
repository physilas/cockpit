/* Server-only archive API. The token grants no Cloudflare account access. */
const MAX_BATCH = 5;
const MAX_EXPORT_BYTES = 3_000_000;
const MIN_AGE_MS = 10 * 60 * 1000;
const hex = /^[a-f0-9]{64}$/;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const encoder = new TextEncoder();

export async function sha256(value) {
  const digest = await crypto.subtle.digest('SHA-256', encoder.encode(value));
  return Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2, '0')).join('');
}

export async function archiveRequest(request, env) {
  const reply = (status, body) => new Response(JSON.stringify(body), {
    status, headers: {'Content-Type': 'application/json', 'Cache-Control': 'no-store'},
  });
  const supplied = request.headers.get('Authorization')?.match(/^Bearer ([a-f0-9]{64})$/)?.[1];
  if (!hex.test(env.ARCHIVE_TOKEN || '') || !hex.test(supplied || '')) {
    return reply(401, {error: 'archive_auth'});
  }
  const expected = await sha256(env.ARCHIVE_TOKEN), actual = await sha256(supplied);
  let different = 0;
  for (let i = 0; i < expected.length; i++) different |= expected.charCodeAt(i) ^ actual.charCodeAt(i);
  if (different) return reply(401, {error: 'archive_auth'});
  const path = new URL(request.url).pathname;
  if (!['/archive/export', '/archive/ack'].includes(path)) return reply(404, {error: 'not_found'});
  if (request.method !== 'POST') return reply(405, {error: 'method'});
  try {
    const cutoff = new Date(Date.now() - MIN_AGE_MS).toISOString();
    if (path === '/archive/export') {
      const result = await env.TRAINING_DB.prepare(`
        SELECT participant_hash, session_id, revision, mode, status, event_count, received_at, payload
        FROM training_sessions
        WHERE status IN ('gewonnen', 'verloren', 'aborted') AND received_at <= ?
        ORDER BY received_at, participant_hash, session_id LIMIT ?
      `).bind(cutoff, MAX_BATCH).all();
      if (!result.success) return reply(503, {error: 'storage'});
      const records = []; let bytes = 0;
      for (const row of result.results) {
        const size = encoder.encode(row.payload).byteLength;
        if (records.length && bytes + size > MAX_EXPORT_BYTES) break;
        records.push({...row, sha256: await sha256(row.payload)});
        bytes += size;
      }
      return reply(200, {records});
    }
    // Acknowledgements contain identities and digests, never large payloads.
    const reader = request.body?.getReader();
    if (!reader) return reply(400, {error: 'body'});
    let raw = ''; const decoder = new TextDecoder(); let bytes = 0;
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      bytes += value.length;
      if (bytes > 8192) { await reader.cancel(); return reply(413, {error: 'size'}); }
      raw += decoder.decode(value, {stream: true});
    }
    raw += decoder.decode();
    let data;
    try { data = JSON.parse(raw); } catch { return reply(400, {error: 'json'}); }
    if (!Array.isArray(data.records) || data.records.length < 1 || data.records.length > MAX_BATCH
        || !data.records.every(r => hex.test(r.participant_hash || '') && uuid.test(r.session_id || '')
          && Number.isSafeInteger(r.revision) && r.revision > 0 && hex.test(r.sha256 || ''))) {
      return reply(400, {error: 'schema'});
    }
    const results = [];
    for (const record of data.records) {
      const row = await env.TRAINING_DB.prepare(`
        SELECT revision, status, received_at, payload FROM training_sessions
        WHERE participant_hash = ? AND session_id = ?
      `).bind(record.participant_hash, record.session_id).first();
      let status = 'missing';
      if (row) {
        status = 'changed';
        if (row.revision === record.revision && ['gewonnen', 'verloren', 'aborted'].includes(row.status)
            && row.received_at <= cutoff && await sha256(row.payload) === record.sha256) {
          // Match the exact payload as well: a concurrent upload/undo is preserved.
          const result = await env.TRAINING_DB.prepare(`
            DELETE FROM training_sessions
            WHERE participant_hash = ? AND session_id = ? AND revision = ? AND payload = ?
          `).bind(record.participant_hash, record.session_id, record.revision, row.payload).run();
          if (!result.success) return reply(503, {error: 'storage'});
          status = result.meta.changes === 1 ? 'deleted' : 'changed';
        }
      }
      results.push({session_id: record.session_id, revision: record.revision, status});
    }
    return reply(200, {results});
  } catch { return reply(503, {error: 'storage'}); }
}
