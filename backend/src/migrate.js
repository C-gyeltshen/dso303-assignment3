'use strict';
// Applies schema.sql. Invoked by the CI pipeline after `terraform apply`
// (the DB is private, so migrations run from inside the VPC).
const fs = require('node:fs');
const path = require('node:path');
const db = require('./db');

exports.handler = async (event = {}) => {
  const sql = fs.readFileSync(path.join(__dirname, 'schema.sql'), 'utf8');
  await db.query(sql);
  const out = { migrated: true };
  if (event.seed) Object.assign(out, await seed());
  if (event.loadtest) Object.assign(out, await seedLoadTest(event.loadtest.exams || 6));
  const t = await db.query("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY 1");
  return { ...out, tables: t.rows.map((r) => r.table_name) };
};

// Demo data so the walkthroughs can be shown straight after deploy.
async function seed() {
  const existing = await db.query("SELECT id FROM exams WHERE title = 'Demo: Cloud Computing Quiz'");
  if (existing.rows.length) return { seeded: false };
  const e = await db.query(
    `INSERT INTO exams (title, course, opens_at, closes_at, duration_mins, created_by)
     VALUES ('Demo: Cloud Computing Quiz', 'CS301', now() - interval '1 hour', now() + interval '30 days', 30, 'seed')
     RETURNING id`);
  const id = e.rows[0].id;
  const qs = [
    ['mcq', 'Which service keeps 50 MB uploads off the API?', ['Amazon EBS', 'S3 presigned POST', 'API Gateway', 'NAT Gateway'], 1, 2],
    ['mcq', 'RDS Multi-AZ replicates to the standby…', ['Asynchronously', 'Synchronously', 'Daily', 'Never'], 1, 2],
    ['mcq', 'Which tier should the database live in?', ['Public subnet', 'Private data subnet', 'CloudFront', 'Internet gateway'], 1, 2],
    ['short', 'In one or two sentences, explain why SQS is used for marking.', null, null, 4],
  ];
  for (const [i, [type, text, options, correct, marks]] of qs.entries()) {
    await db.query(
      'INSERT INTO questions (exam_id, position, type, text, options, correct_option, marks) VALUES ($1,$2,$3,$4,$5,$6,$7)',
      [id, i, type, text, options ? JSON.stringify(options) : null, correct, marks]);
  }
  await db.query(
    `INSERT INTO assignments (title, due_at, tutor_email, created_by)
     VALUES ('Demo: Architecture Report', now() + interval '30 days', $1, 'seed')`, [process.env.SES_SENDER]);
  return { seeded: true, examId: id };
}

// Load-test exams (scripts/loadtest): N open exams with 10 MCQs each, so 500 test users x 6 exams = 3,000 attempts.
async function seedLoadTest(n) {
  const ids = [];
  for (let k = 1; k <= n; k += 1) {
    const title = `Load test exam ${k}`;
    const found = await db.query('SELECT id FROM exams WHERE title = $1', [title]);
    if (found.rows.length) { ids.push(found.rows[0].id); continue; }
    const e = await db.query(
      `INSERT INTO exams (title, course, opens_at, closes_at, duration_mins, created_by)
       VALUES ($1, 'LOAD', now() - interval '5 minutes', now() + interval '2 days', 120, 'loadtest') RETURNING id`, [title]);
    for (let i = 0; i < 10; i += 1) {
      await db.query(
        'INSERT INTO questions (exam_id, position, type, text, options, correct_option, marks) VALUES ($1,$2,$3,$4,$5,$6,1)',
        [e.rows[0].id, i, 'mcq', `Load question ${i + 1}`, JSON.stringify(['A', 'B', 'C', 'D']), i % 4]);
    }
    ids.push(e.rows[0].id);
  }
  return { loadTestExamIds: ids };
}
