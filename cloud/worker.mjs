/* Private D1 ingestion for the static GitHub Pages app. No read/list endpoint. */
// Leave room below D1's 2,000,000-byte row limit for metadata and JSON framing.
const MAX_BYTES = 1_800_000;
export const UPSERT_SESSION = `
  INSERT INTO training_sessions
    (participant_hash, session_id, revision, mode, status, event_count, received_at, payload)
  VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  ON CONFLICT(participant_hash, session_id) DO UPDATE SET
    revision = excluded.revision, mode = excluded.mode, status = excluded.status,
    event_count = excluded.event_count, received_at = excluded.received_at, payload = excluded.payload
  WHERE excluded.revision > training_sessions.revision
`;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function valid(data) {
  const s = data?.session, schema = data?.schema;
  if (data?.format !== "flyteam-learning-session" || data.version !== 1 || !s || !uuid.test(s.id)) return false;
  if (!["feedback", "examples"].includes(s.mode) || !Number.isSafeInteger(s.data_revision) || s.data_revision < 1) return false;
  if (s.consent?.version !== "2026-10-18" || !Number.isFinite(Date.parse(s.consent.accepted_at))) return false;
  if (schema?.version !== 1 || !Array.isArray(schema.features) || schema.features.length !== 349
      || !Array.isArray(schema.actions) || schema.actions.length !== 121) return false;
  if (!Array.isArray(s.events) || s.events.length < 1 || s.events.length > 1024) return false;
  return s.events.every(e => {
    if (!e || !["human", "ai", "system"].includes(e.actor)) return false;
    if (e.feedback && (!Number.isInteger(e.feedback.value) || Math.abs(e.feedback.value) > 2 || typeof e.feedback.committed !== "boolean")) return false;
    if (e.action_id === null) return e.decision === null;
    return Number.isInteger(e.action_id) && e.action_id >= 0 && e.action_id < 121
      && ["pilot", "kopilot"].includes(e.decision?.role)
      && Array.isArray(e.decision.observation) && e.decision.observation.length === 349
      && e.decision.observation.every(n => typeof n === "number" && Number.isFinite(n))
      && Array.isArray(e.decision.action_mask) && e.decision.action_mask.length === 121
      && e.decision.action_mask.every(n => typeof n === "boolean");
  });
}

async function readLimited(request) {
  if (Number(request.headers.get("Content-Length")) > MAX_BYTES) return null;
  const reader = request.body?.getReader();
  if (!reader) return "";
  const chunks = []; let size = 0;
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    size += value.length;
    if (size > MAX_BYTES) { await reader.cancel(); return null; }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return new TextDecoder().decode(bytes);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url), origin = request.headers.get("Origin");
    const allowed = (env.ALLOWED_ORIGINS || "").split(",").map(v => v.trim()).filter(Boolean);
    const headers = {"Content-Type": "application/json", "Cache-Control": "no-store", "Vary": "Origin"};
    const reply = (status, body) => new Response(JSON.stringify(body), {status, headers});
    if (!allowed.includes(origin)) return reply(403, {error: "origin"});
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Access-Control-Allow-Methods"] = "POST, OPTIONS";
    headers["Access-Control-Allow-Headers"] = "Content-Type, X-Upload-Token";
    headers["Access-Control-Max-Age"] = "86400";
    if (url.pathname !== "/logs") return reply(404, {error: "not_found"});
    if (request.method === "OPTIONS") return new Response(null, {status: 204, headers});
    if (request.method !== "POST") return reply(405, {error: "method"});
    if (!request.headers.get("Content-Type")?.startsWith("application/json")) return reply(415, {error: "content_type"});
    const token = request.headers.get("X-Upload-Token");
    if (!/^[a-f0-9]{64}$/.test(token || "")) return reply(401, {error: "token"});
    // The token is never stored. Its hash isolates each installation's writes.
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token))), n => n.toString(16).padStart(2,"0")).join("");
    if (env.UPLOAD_LIMIT && !(await env.UPLOAD_LIMIT.limit({key: hash})).success) return reply(429, {error: "rate_limit"});
    const raw = await readLimited(request);
    if (raw === null) return reply(413, {error: "size"});
    let data;
    try { data = JSON.parse(raw); } catch { return reply(400, {error: "json"}); }
    if (!valid(data)) return reply(400, {error: "schema"});
    try {
      const received = new Date().toISOString();
      const result = await env.TRAINING_DB.prepare(UPSERT_SESSION).bind(
        hash, data.session.id, data.session.data_revision, data.session.mode,
        String(data.session.status || "active").slice(0, 64), data.session.events.length,
        received, JSON.stringify({...data, received_at: received})
      ).run();
      if (!result.success) return reply(503, {error: "storage"});
      return reply(200, {stored: true});
    } catch { return reply(503, {error: "storage"}); }
  },
};
