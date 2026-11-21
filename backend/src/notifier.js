'use strict';
// SQS notify-queue consumer. Two message types:
//   {type:'release', examId}  -> fan out one 'email' message per attempt (batches of 10)
//   {type:'email', attemptId} -> send the result email (idempotent via notified_at)
const { SQSClient, SendMessageBatchCommand } = require('@aws-sdk/client-sqs');
const db = require('./db');
const { queueEmail } = require('./email');

const sqs = new SQSClient({});

async function fanOut(examId) {
  const r = await db.query(
    'SELECT id FROM attempts WHERE exam_id = $1 AND notified_at IS NULL AND status <> $2', [examId, 'in_progress']);
  for (let i = 0; i < r.rows.length; i += 10) {
    const chunk = r.rows.slice(i, i + 10);
    await sqs.send(new SendMessageBatchCommand({
      QueueUrl: process.env.NOTIFY_QUEUE,
      Entries: chunk.map((row) => ({ Id: String(row.id), MessageBody: JSON.stringify({ type: 'email', attemptId: row.id }) })),
    }));
  }
  return r.rows.length;
}

async function emailResult(attemptId) {
  // Claim the row first so a retried message can't send a second email.
  const r = await db.query(
    `UPDATE attempts a SET notified_at = now() FROM exams e
      WHERE a.id = $1 AND e.id = a.exam_id AND e.results_released AND a.notified_at IS NULL
      RETURNING a.student_email, e.title`, [attemptId]);
  if (!r.rows.length) return false;
  const { student_email: to, title } = r.rows[0];
  try {
    await queueEmail(to, `Results released: ${title}`,
      `Your result for "${title}" is now available.\n\nSign in to view it: ${process.env.SITE_URL}/#/results`);
  } catch (e) {
    await db.query('UPDATE attempts SET notified_at = NULL WHERE id = $1', [attemptId]); // allow retry
    throw e;
  }
  return true;
}

exports.handler = async (event) => {
  const batchItemFailures = [];
  for (const rec of event.Records) {
    try {
      const m = JSON.parse(rec.body);
      if (m.type === 'release') console.log(JSON.stringify({ msg: 'fan-out', examId: m.examId, count: await fanOut(m.examId) }));
      else if (m.type === 'email') await emailResult(m.attemptId);
    } catch (err) {
      console.error(JSON.stringify({ level: 'error', messageId: rec.messageId, message: err.message }));
      batchItemFailures.push({ itemIdentifier: rec.messageId });
    }
  }
  return { batchItemFailures };
};
