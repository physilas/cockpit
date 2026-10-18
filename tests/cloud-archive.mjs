import assert from 'node:assert/strict';
import fs from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import worker from '../cloud/worker.mjs';
import {sha256} from '../cloud/archive.mjs';

const db = new DatabaseSync(':memory:');
db.exec(fs.readFileSync(new URL('../cloud/schema.sql', import.meta.url), 'utf8'));
let storageFailure = false, beforeDelete = null;
const env = {ARCHIVE_TOKEN: 'c'.repeat(64), TRAINING_DB: {
  prepare: sql => ({bind: (...parameters) => ({
    all: async () => {
      if (storageFailure) throw new Error('unavailable');
      return {success: true, results: db.prepare(sql).all(...parameters)};
    },
    first: async () => {
      if (storageFailure) throw new Error('unavailable');
      return db.prepare(sql).get(...parameters) || null;
    },
    run: async () => {
      if (storageFailure) throw new Error('unavailable');
      if (beforeDelete) { const hook = beforeDelete; beforeDelete = null; hook(); }
      const result = db.prepare(sql).run(...parameters);
      return {success: true, meta: {changes: result.changes}};
    },
  })}),
}};
const old = new Date(Date.now() - 3600_000).toISOString();
function insert(status = 'gewonnen', received = old, padding = '') {
  const row = {participant_hash: 'a'.repeat(64), session_id: crypto.randomUUID(), revision: 3,
    mode: 'examples', status, event_count: 1, received_at: received};
  row.payload = JSON.stringify({session: {id: row.session_id, status}, padding});
  db.prepare('INSERT INTO training_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)').run(...Object.values(row));
  return row;
}
const call = (path, data = {}, token = env.ARCHIVE_TOKEN, method = 'POST') => worker.fetch(
  new Request(`https://logs.workers.dev/archive/${path}`, {method,
    headers: {'Content-Type': 'application/json', ...(token ? {Authorization: `Bearer ${token}`} : {})},
    ...(method === 'POST' ? {body: typeof data === 'string' ? data : JSON.stringify(data)} : {})}), env);
const ack = async row => ({participant_hash: row.participant_hash, session_id: row.session_id,
  revision: row.revision, sha256: await sha256(row.payload)});
const exists = row => !!db.prepare('SELECT 1 FROM training_sessions WHERE session_id = ?').get(row.session_id);

const win = insert(), active = insert('active'), recent = insert('verloren', new Date().toISOString());
const aborted = insert('aborted');
assert.equal((await call('export', {}, null)).status, 401);
assert.equal((await call('export', {}, 'b'.repeat(64))).status, 401);
assert.equal((await call('export', {}, env.ARCHIVE_TOKEN, 'GET')).status, 405);
assert.equal((await call('unknown')).status, 404);
const exported = await call('export');
assert.equal(exported.headers.get('Access-Control-Allow-Origin'), null);
const rows = (await exported.json()).records;
assert.deepEqual(new Set(rows.map(r => r.session_id)), new Set([win.session_id, aborted.session_id]));
assert.equal(rows.find(r => r.session_id === win.session_id).sha256, await sha256(win.payload));

const original = await ack(win);
let result = await (await call('ack', {records: [{...original, sha256: '0'.repeat(64)}]})).json();
assert.equal(result.results[0].status, 'changed'); assert.ok(exists(win));
result = await (await call('ack', {records: [{...original, revision: 2}]})).json();
assert.equal(result.results[0].status, 'changed'); assert.ok(exists(win));
result = await (await call('ack', {records: [await ack(recent), await ack(active)]})).json();
assert.ok(result.results.every(r => r.status === 'changed')); assert.ok(exists(recent) && exists(active));

// Update between SELECT and DELETE: the new revision must survive.
beforeDelete = () => db.prepare('UPDATE training_sessions SET revision = 4 WHERE session_id = ?').run(win.session_id);
result = await (await call('ack', {records: [original]})).json();
assert.equal(result.results[0].status, 'changed'); assert.ok(exists(win));
db.prepare('UPDATE training_sessions SET revision = 3 WHERE session_id = ?').run(win.session_id);
result = await (await call('ack', {records: [original]})).json();
assert.equal(result.results[0].status, 'deleted'); assert.ok(!exists(win));
result = await (await call('ack', {records: [original]})).json();
assert.equal(result.results[0].status, 'missing');
assert.equal((await call('ack', {records: Array(6).fill(original)})).status, 400);
assert.equal((await call('ack', 'x'.repeat(8193))).status, 413);
assert.equal((await call('ack', 'bad JSON')).status, 400);
storageFailure = true;
assert.equal((await call('export')).status, 503);
assert.equal((await call('ack', {records: [await ack(aborted)]})).status, 503);
assert.ok(exists(aborted)); storageFailure = false;
db.prepare('DELETE FROM training_sessions').run();
insert('gewonnen', old, 'x'.repeat(1_600_000)); insert('verloren', old, 'y'.repeat(1_600_000));
assert.equal((await (await call('export')).json()).records.length, 1);
db.close();
console.log('✓ Archive API + real SQLite: authentication, terminal/age filters, SHA-256, bounded batches, revision races, exact deletion, retries and storage errors');
