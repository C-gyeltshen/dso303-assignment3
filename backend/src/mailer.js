'use strict';
// email-queue consumer, outside the VPC. Event-source maximum concurrency (5) keeps the
// send rate under the SES account quota; throttled sends are retried, then go to the DLQ.
const { SESv2Client, SendEmailCommand } = require('@aws-sdk/client-sesv2');

const ses = new SESv2Client({});

exports.handler = async (event) => {
  const batchItemFailures = [];
  for (const rec of event.Records) {
    try {
      const { to, subject, text } = JSON.parse(rec.body);
      await ses.send(new SendEmailCommand({
        FromEmailAddress: process.env.SES_SENDER,
        Destination: { ToAddresses: [to] },
        Content: { Simple: { Subject: { Data: subject }, Body: { Text: { Data: text } } } },
      }));
    } catch (err) {
      console.error(JSON.stringify({ level: 'ERROR', messageId: rec.messageId, name: err.name, message: err.message }));
      batchItemFailures.push({ itemIdentifier: rec.messageId });
    }
  }
  return { batchItemFailures };
};
