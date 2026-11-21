// Creates N load-test students in Cognito (idempotent) and writes their ID tokens to tokens.json.
//   node make-tokens.mjs <userPoolId> <clientId> <count> [password]
// Tokens are valid for 60 minutes - run this right before each test.
import { writeFileSync } from 'node:fs';
import {
  CognitoIdentityProviderClient, AdminCreateUserCommand, AdminSetUserPasswordCommand,
  AdminAddUserToGroupCommand, AdminInitiateAuthCommand,
} from '@aws-sdk/client-cognito-identity-provider';

const [poolId, clientId, countArg, pw = 'LoadTest-Passw0rd!'] = process.argv.slice(2);
if (!poolId || !clientId) {
  console.error('usage: node make-tokens.mjs <userPoolId> <clientId> <count> [password]');
  process.exit(1);
}
const count = Number(countArg || 500);
const cognito = new CognitoIdentityProviderClient({});
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function retry(fn) {
  for (let i = 0; ; i += 1) {
    try { return await fn(); } catch (e) {
      if (e.name === 'TooManyRequestsException' && i < 8) { await sleep(500 * 2 ** i); continue; }
      throw e;
    }
  }
}

async function one(i) {
  const email = `loadtest+${String(i).padStart(4, '0')}@example.com`;
  await retry(() => cognito.send(new AdminCreateUserCommand({
    UserPoolId: poolId, Username: email, MessageAction: 'SUPPRESS',
    UserAttributes: [{ Name: 'email', Value: email }, { Name: 'email_verified', Value: 'true' }],
  }))).catch((e) => { if (e.name !== 'UsernameExistsException') throw e; });
  await retry(() => cognito.send(new AdminSetUserPasswordCommand({ UserPoolId: poolId, Username: email, Password: pw, Permanent: true })));
  await retry(() => cognito.send(new AdminAddUserToGroupCommand({ UserPoolId: poolId, Username: email, GroupName: 'students' })));
  const r = await retry(() => cognito.send(new AdminInitiateAuthCommand({
    UserPoolId: poolId, ClientId: clientId, AuthFlow: 'ADMIN_USER_PASSWORD_AUTH',
    AuthParameters: { USERNAME: email, PASSWORD: pw },
  })));
  return r.AuthenticationResult.IdToken;
}

const tokens = [];
const CONCURRENCY = 5; // stays under Cognito admin API rate limits
for (let i = 0; i < count; i += CONCURRENCY) {
  const batch = await Promise.all(Array.from({ length: Math.min(CONCURRENCY, count - i) }, (_, k) => one(i + k)));
  tokens.push(...batch);
  process.stdout.write(`\r${tokens.length}/${count} users ready`);
}
writeFileSync(new URL('./tokens.json', import.meta.url), JSON.stringify(tokens));
console.log('\nwrote tokens.json');
