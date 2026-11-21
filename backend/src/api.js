'use strict';
// API Lambda: one function behind `ANY /api/{proxy+}` with a small router.
const crypto = require('node:crypto');
const { S3Client } = require('@aws-sdk/client-s3');
const { createPresignedPost } = require('@aws-sdk/s3-presigned-post');
const { getSignedUrl } = require('@aws-sdk/cloudfront-signer');
const { SQSClient, SendMessageCommand } = require('@aws-sdk/client-sqs');
const { SecretsManagerClient, GetSecretValueCommand } = require('@aws-sdk/client-secrets-manager');
const db = require('./db');
const { HttpError, json, getUser, requireRole, parseBody } = require('./http');
const { markAttempt } = require('./marking');

const s3 = new S3Client({});
const sqs = new SQSClient({});
const sm = new SecretsManagerClient({});

// CloudFront signing key: fetched once per container (via the Secrets Manager endpoint), only when a tutor downloads.
let cfKeyPromise;
const cfPrivateKey = () => {
  if (!cfKeyPromise) {
    cfKeyPromise = sm.send(new GetSecretValueCommand({ SecretId: process.env.CF_KEY_SECRET }))
      .then((r) => r.SecretString)
      .catch((e) => { cfKeyPromise = undefined; throw e; });
  }
  return cfKeyPromise;
};

const GRACE_SECONDS = 60;
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const ALLOWED_TYPES = { pdf: 'application/pdf', zip: 'application/zip' };

const routes = [];
const route = (method, pattern, fn) => {
  const keys = [];
  const re = new RegExp('^' + pattern.replace(/\{(\w+)\}/g, (_, k) => { keys.push(k); return '([^/]+)'; }) + '$');
  routes.push({ method, re, keys, fn });
};

// ---------- health (public; used in the AZ-failure demo) ----------
route('GET', '/api/health', async () => {
  const r = await db.query("SELECT now() AS time, host(inet_server_addr()) AS db_ip, pg_is_in_recovery() AS replica");
  const ip = r.rows[0].db_ip || '';
  return json(200, {
    ok: true,
    region: process.env.AWS_REGION,
    dbTime: r.rows[0].time,
    dbServerIp: ip,
    dbSubnet: ip.startsWith('10.0.20.') ? 'private-data AZ-a' : ip.startsWith('10.0.21.') ? 'private-data AZ-b' : 'unknown',
  });
});

route('GET', '/api/me', async (_e, user) => json(200, user));

// ---------- exams ----------
route('GET', '/api/exams', async (_e, user) => {
  const isStaff = user.groups.includes('tutors') || user.groups.includes('admins');
  const r = isStaff
    ? await db.query('SELECT * FROM exams ORDER BY opens_at DESC')
    : await db.query(
      `SELECT e.id, e.title, e.course, e.opens_at, e.closes_at, e.duration_mins, e.results_released,
              a.id AS attempt_id, a.status AS attempt_status, a.deadline
         FROM exams e LEFT JOIN attempts a ON a.exam_id = e.id AND a.student_sub = $1
        WHERE e.closes_at > now() - interval '30 days'
        ORDER BY e.opens_at`, [user.sub]);
  return json(200, r.rows);
});

route('POST', '/api/exams', async (event, user) => {
  requireRole(user, 'tutors', 'admins');
  const b = parseBody(event);
  if (!b.title || !b.opensAt || !b.closesAt || !b.durationMins || !Array.isArray(b.questions) || !b.questions.length) {
    throw new HttpError(400, 'title, opensAt, closesAt, durationMins and questions[] are required');
  }
  const exam = await db.tx(async (c) => {
    const e = await c.query(
      `INSERT INTO exams (title, course, opens_at, closes_at, duration_mins, created_by)
       VALUES ($1,$2,$3,$4,$5,$6) RETURNING *`,
      [b.title, b.course || null, b.opensAt, b.closesAt, b.durationMins, user.sub]);
    for (const [i, q] of b.questions.entries()) {
      if (!['mcq', 'short'].includes(q.type) || !q.text) throw new HttpError(400, `Question ${i + 1} invalid`);
      if (q.type === 'mcq' && (!Array.isArray(q.options) || q.options.length < 2 || !Number.isInteger(q.correctOption))) {
        throw new HttpError(400, `Question ${i + 1}: MCQ needs options[] and correctOption`);
      }
      await c.query(
        `INSERT INTO questions (exam_id, position, type, text, options, correct_option, marks)
         VALUES ($1,$2,$3,$4,$5,$6,$7)`,
        [e.rows[0].id, i, q.type, q.text, q.type === 'mcq' ? JSON.stringify(q.options) : null,
          q.type === 'mcq' ? q.correctOption : null, q.marks || 1]);
    }
    return e.rows[0];
  });
  return json(201, exam);
});

route('POST', '/api/exams/{id}/start', async (_e, user, p) => {
  requireRole(user, 'students');
  const ex = await db.query(
    'SELECT * FROM exams WHERE id = $1 AND now() BETWEEN opens_at AND closes_at', [p.id]);
  if (!ex.rows.length) throw new HttpError(403, 'Exam is not open');
  const exam = ex.rows[0];
  // Idempotent: a refresh or a second device resumes the same attempt with the same deadline.
  const att = await db.query(
    `INSERT INTO attempts (exam_id, student_sub, student_email, deadline)
     VALUES ($1, $2, $3, LEAST(now() + make_interval(mins => $4), $5))
     ON CONFLICT (exam_id, student_sub) DO UPDATE SET exam_id = EXCLUDED.exam_id
     RETURNING id, status, deadline, answers, client_seq, saved_at`,
    [exam.id, user.sub, user.email, exam.duration_mins, exam.closes_at]);
  const qs = await db.query(
    'SELECT id, type, text, options, marks FROM questions WHERE exam_id = $1 ORDER BY position', [exam.id]);
  return json(200, { exam: { id: exam.id, title: exam.title }, attempt: att.rows[0], questions: qs.rows, serverTime: new Date() });
});

route('GET', '/api/exams/{id}/attempts', async (_e, user, p) => {
  requireRole(user, 'tutors', 'admins');
  await closeExpired(p.id);
  const r = await db.query(
    `SELECT id, student_email, status, submitted_at, mcq_score, total_score, max_score, answers, short_marks
       FROM attempts WHERE exam_id = $1 ORDER BY student_email`, [p.id]);
  const qs = await db.query('SELECT * FROM questions WHERE exam_id = $1 ORDER BY position', [p.id]);
  return json(200, { questions: qs.rows, attempts: r.rows });
});

route('POST', '/api/exams/{id}/release', async (_e, user, p) => {
  requireRole(user, 'tutors', 'admins');
  await closeExpired(p.id);
  const r = await db.query(
    'UPDATE exams SET results_released = TRUE, released_at = now() WHERE id = $1 RETURNING id', [p.id]);
  if (!r.rows.length) throw new HttpError(404, 'Exam not found');
  // Fan-out happens asynchronously in the notifier so 3,000 emails never block this request.
  await sqs.send(new SendMessageCommand({
    QueueUrl: process.env.NOTIFY_QUEUE,
    MessageBody: JSON.stringify({ type: 'release', examId: Number(p.id) }),
  }));
  return json(202, { released: true });
});

// ---------- attempts ----------
async function ownAttempt(id, user) {
  const r = await db.query('SELECT * FROM attempts WHERE id = $1 AND student_sub = $2', [id, user.sub]);
  if (!r.rows.length) throw new HttpError(404, 'Attempt not found');
  return r.rows[0];
}

route('GET', '/api/attempts/{id}', async (_e, user, p) => {
  const a = await ownAttempt(p.id, user);
  return json(200, { id: a.id, status: a.status, deadline: a.deadline, answers: a.answers, savedAt: a.saved_at, clientSeq: a.client_seq });
});

// Autosave (every 30 s). Only newer saves win, and only before deadline + grace.
route('PUT', '/api/attempts/{id}/answers', async (event, user, p) => {
  requireRole(user, 'students');
  const b = parseBody(event);
  if (typeof b.answers !== 'object' || b.answers === null || !Number.isInteger(b.clientSeq)) {
    throw new HttpError(400, 'answers{} and integer clientSeq required');
  }
  if (JSON.stringify(b.answers).length > 200000) throw new HttpError(413, 'Answers too large');
  const r = await db.query(
    `UPDATE attempts SET answers = $3, client_seq = $4, saved_at = now()
      WHERE id = $1 AND student_sub = $2 AND status = 'in_progress'
        AND now() <= deadline + make_interval(secs => $5) AND client_seq < $4
      RETURNING saved_at, client_seq`,
    [p.id, user.sub, JSON.stringify(b.answers), b.clientSeq, GRACE_SECONDS]);
  if (r.rows.length) return json(200, { savedAt: r.rows[0].saved_at, clientSeq: r.rows[0].client_seq });
  const a = await ownAttempt(p.id, user);
  if (a.client_seq >= b.clientSeq) return json(200, { savedAt: a.saved_at, clientSeq: a.client_seq, stale: true });
  throw new HttpError(409, 'Attempt is closed');
});

route('POST', '/api/attempts/{id}/submit', async (_e, user, p) => {
  requireRole(user, 'students');
  const r = await db.query(
    `UPDATE attempts SET status = 'submitted', submitted_at = now()
      WHERE id = $1 AND student_sub = $2 AND status = 'in_progress' RETURNING id`, [p.id, user.sub]);
  if (!r.rows.length) {
    await ownAttempt(p.id, user);
    return json(200, { submitted: true, alreadySubmitted: true });
  }
  await sqs.send(new SendMessageCommand({
    QueueUrl: process.env.MARKING_QUEUE, MessageBody: JSON.stringify({ attemptId: Number(p.id) }),
  }));
  return json(202, { submitted: true });
});

route('PUT', '/api/attempts/{id}/marks', async (event, user, p) => {
  requireRole(user, 'tutors', 'admins');
  const b = parseBody(event);
  const r = await db.query(
    "UPDATE attempts SET short_marks = short_marks || $2::jsonb WHERE id = $1 AND status <> 'in_progress' RETURNING id",
    [p.id, JSON.stringify(b.marks || {})]);
  if (!r.rows.length) throw new HttpError(404, 'Attempt not found or still in progress');
  return json(200, await markAttempt(p.id));
});

route('GET', '/api/results', async (_e, user) => {
  const r = await db.query(
    `SELECT e.id AS exam_id, e.title, a.total_score, a.max_score, a.status, e.released_at
       FROM attempts a JOIN exams e ON e.id = a.exam_id
      WHERE a.student_sub = $1 AND e.results_released ORDER BY e.released_at DESC`, [user.sub]);
  return json(200, r.rows);
});

// Attempts whose time ran out without "submit" are closed and marked.
async function closeExpired(examId) {
  const r = await db.query(
    `UPDATE attempts SET status = 'submitted', submitted_at = deadline
      WHERE exam_id = $1 AND status = 'in_progress' AND now() > deadline + make_interval(secs => $2)
      RETURNING id`, [examId, GRACE_SECONDS]);
  for (const row of r.rows) await markAttempt(row.id);
}

// ---------- assignments ----------
route('GET', '/api/assignments', async (_e, user) => {
  const r = await db.query(
    `SELECT a.*, (SELECT count(*) FROM submissions s WHERE s.assignment_id = a.id AND s.status = 'received')::int AS submissions,
            (SELECT max(received_at) FROM submissions s WHERE s.assignment_id = a.id AND s.student_sub = $1 AND s.status = 'received') AS my_last_submission
       FROM assignments a ORDER BY due_at`, [user.sub]);
  return json(200, r.rows);
});

route('POST', '/api/assignments', async (event, user) => {
  requireRole(user, 'tutors', 'admins');
  const b = parseBody(event);
  if (!b.title || !b.dueAt) throw new HttpError(400, 'title and dueAt required');
  const r = await db.query(
    'INSERT INTO assignments (title, due_at, tutor_email, created_by) VALUES ($1,$2,$3,$4) RETURNING *',
    [b.title, b.dueAt, b.tutorEmail || user.email, user.sub]);
  return json(201, r.rows[0]);
});

// Presigned POST: browser uploads straight to S3; policy enforces size and key prefix.
route('POST', '/api/assignments/{id}/upload-url', async (event, user, p) => {
  requireRole(user, 'students');
  const b = parseBody(event);
  const ext = String(b.fileName || '').split('.').pop().toLowerCase();
  if (!ALLOWED_TYPES[ext]) throw new HttpError(400, 'Only PDF or ZIP files are accepted');
  const a = await db.query('SELECT id FROM assignments WHERE id = $1 AND due_at > now()', [p.id]);
  if (!a.rows.length) throw new HttpError(403, 'Assignment not found or past due date');
  const safeName = String(b.fileName).replace(/[^\w.\-]/g, '_').slice(-100);
  const key = `submissions/${p.id}/${user.sub}/${crypto.randomUUID()}-${safeName}`;
  const post = await createPresignedPost(s3, {
    Bucket: process.env.UPLOAD_BUCKET,
    Key: key,
    Expires: 300,
    Conditions: [
      ['content-length-range', 1, MAX_UPLOAD_BYTES],
      ['eq', '$Content-Type', ALLOWED_TYPES[ext]],
    ],
    Fields: {
      'Content-Type': ALLOWED_TYPES[ext],
      'x-amz-meta-student-email': user.email,
    },
  });
  return json(200, { ...post, key, maxBytes: MAX_UPLOAD_BYTES });
});

route('GET', '/api/assignments/{id}/submissions', async (_e, user, p) => {
  requireRole(user, 'tutors', 'admins');
  const r = await db.query(
    'SELECT * FROM submissions WHERE assignment_id = $1 ORDER BY received_at DESC', [p.id]);
  // A3: signed CloudFront URLs (1 TB/month free) instead of S3 presigned GETs ($0.12/GB from Singapore).
  const privateKey = r.rows.length ? await cfPrivateKey() : null;
  const expires = new Date(Date.now() + 15 * 60 * 1000).toISOString();
  const rows = r.rows.map((s) => ({
    ...s,
    downloadUrl: s.status === 'received'
      ? getSignedUrl({
        url: `${process.env.SITE_URL}/${s.s3_key.split('/').map(encodeURIComponent).join('/')}`,
        keyPairId: process.env.CF_KEY_PAIR_ID,
        privateKey,
        dateLessThan: expires,
      })
      : null,
  }));
  return json(200, rows);
});

// Admin routes (/api/admin/*) are served by src/admin.js, a separate Lambda outside the VPC.

// ---------- dispatcher ----------
exports.handler = async (event) => {
  const method = event.requestContext?.http?.method || 'GET';
  const path = (event.rawPath || '/').replace(/\/+$/, '') || '/';
  try {
    for (const r of routes) {
      const m = method === r.method && path.match(r.re);
      if (!m) continue;
      const params = Object.fromEntries(r.keys.map((k, i) => [k, decodeURIComponent(m[i + 1])]));
      if (params.id !== undefined && !/^\d+$/.test(params.id)) throw new HttpError(400, 'Invalid id');
      const user = path === '/api/health' ? null : getUser(event);
      return await r.fn(event, user, params);
    }
    return json(404, { error: 'Not found' });
  } catch (err) {
    if (err instanceof HttpError) return json(err.status, { error: err.message });
    console.error(JSON.stringify({ level: 'ERROR', path, method, code: err.code, message: err.message, stack: err.stack }));
    return json(500, { error: 'Internal error' });
  }
};

exports._routes = routes; // for tests
