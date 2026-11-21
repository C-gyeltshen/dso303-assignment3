'use strict';
// A3: functions inside the VPC no longer call SES directly (that needed a NAT gateway).
// They queue the email; the mailer Lambda, which runs outside the VPC, sends it.
const { SQSClient, SendMessageCommand } = require('@aws-sdk/client-sqs');

const sqs = new SQSClient({});

async function queueEmail(to, subject, text, dedupeKey) {
  return sqs.send(new SendMessageCommand({
    QueueUrl: process.env.EMAIL_QUEUE,
    MessageBody: JSON.stringify({ to, subject, text, dedupeKey }),
  }));
}

module.exports = { queueEmail, sendEmail: queueEmail };
