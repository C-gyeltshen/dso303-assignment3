'use strict';
// SQS uploads-queue consumer (fed by S3 ObjectCreated events).
// Validates the file, records the submission and emails the tutor.
const { S3Client, GetObjectCommand, HeadObjectCommand, PutObjectTaggingCommand } = require('@aws-sdk/client-s3');
const db = require('./db');
const { queueEmail } = require('./email');

const s3 = new S3Client({});
const MAX_BYTES = 50 * 1024 * 1024;

// Magic bytes: PDF starts with "%PDF", ZIP with "PK\x03\x04"
function detectType(buf) {
  if (buf.subarray(0, 4).toString('latin1') === '%PDF') return 'pdf';
  if (buf[0] === 0x50 && buf[1] === 0x4b && buf[2] === 0x03 && buf[3] === 0x04) return 'zip';
  return null;
}

async function processObject(bucket, key) {
  // key = submissions/{assignmentId}/{studentSub}/{uuid}-{fileName}
  const [, assignmentId, studentSub, rest] = key.split('/');
  const fileName = rest.replace(/^[0-9a-f-]{36}-/, '');
  const head = await s3.send(new HeadObjectCommand({ Bucket: bucket, Key: key }));
  const first = await s3.send(new GetObjectCommand({ Bucket: bucket, Key: key, Range: 'bytes=0-7' }));
  const type = detectType(Buffer.from(await first.Body.transformToByteArray()));
  const expected = fileName.toLowerCase().endsWith('.pdf') ? 'pdf' : 'zip';

  let status = 'received';
  let reason = null;
  if (head.ContentLength > MAX_BYTES) { status = 'rejected'; reason = 'File larger than 50 MB'; }
  else if (type !== expected) { status = 'rejected'; reason = `File content is not a valid ${expected.toUpperCase()}`; }

  if (status === 'rejected') {
    await s3.send(new PutObjectTaggingCommand({
      Bucket: bucket, Key: key, Tagging: { TagSet: [{ Key: 'quarantine', Value: 'true' }] },
    }));
  }

  const studentEmail = head.Metadata?.['student-email'] || null;
  const ins = await db.query(
    `INSERT INTO submissions (assignment_id, student_sub, student_email, s3_key, file_name, size_bytes, status, reason)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (s3_key) DO NOTHING RETURNING id`,
    [assignmentId, studentSub, studentEmail, key, fileName, head.ContentLength, status, reason]);
  if (!ins.rows.length) return { duplicate: true }; // SQS is at-least-once: never email twice

  const a = await db.query('SELECT title, tutor_email FROM assignments WHERE id = $1', [assignmentId]);
  const assignment = a.rows[0];
  if (status === 'received' && assignment) {
    const mb = (head.ContentLength / 1024 / 1024).toFixed(1);
    await queueEmail(
      assignment.tutor_email,
      `New submission: ${assignment.title}`,
      `${studentEmail || studentSub} submitted "${fileName}" (${mb} MB) for "${assignment.title}".\n\n` +
      `View submissions: ${process.env.SITE_URL}/#/assignments/${assignmentId}`,
    );
  }
  return { status, reason };
}

exports.handler = async (event) => {
  const batchItemFailures = [];
  for (const rec of event.Records) {
    try {
      const body = JSON.parse(rec.body);
      if (body.Event === 's3:TestEvent') continue;
      for (const r of body.Records || []) {
        const key = decodeURIComponent(r.s3.object.key.replace(/\+/g, ' '));
        const out = await processObject(r.s3.bucket.name, key);
        console.log(JSON.stringify({ level: 'info', msg: 'upload processed', key, ...out }));
      }
    } catch (err) {
      console.error(JSON.stringify({ level: 'error', messageId: rec.messageId, message: err.message }));
      batchItemFailures.push({ itemIdentifier: rec.messageId });
    }
  }
  return { batchItemFailures };
};

exports._detectType = detectType;
