'use strict';
// PostgreSQL through RDS Proxy with IAM authentication (A3).
// The token is signed locally from the Lambda role's credentials, so no network call to
// Secrets Manager is needed at runtime (and no NAT gateway). Tokens last 15 minutes;
// pg calls the password function for every new connection, so they never go stale.
const { Pool } = require('pg');
const { Signer } = require('@aws-sdk/rds-signer');

const signer = new Signer({
  hostname: process.env.DB_HOST,
  port: 5432,
  username: process.env.DB_USER,
  region: process.env.AWS_REGION,
});

let pool;

function getPool() {
  if (!pool) {
    pool = new Pool({
      host: process.env.DB_HOST,
      database: process.env.DB_NAME,
      user: process.env.DB_USER,
      password: () => signer.getAuthToken(),
      port: 5432,
      ssl: { rejectUnauthorized: true }, // RDS Proxy presents an ACM (publicly trusted) certificate
      max: 2,                            // one request per Lambda at a time; RDS Proxy does the pooling
      idleTimeoutMillis: 60000,
      connectionTimeoutMillis: 5000,
    });
    pool.on('error', () => { pool = undefined; });
  }
  return pool;
}

const RETRYABLE = ['ECONNRESET', 'ETIMEDOUT', '57P01', '57P03', '08006', '08003'];

async function query(text, params) {
  try {
    return await getPool().query(text, params);
  } catch (err) {
    // During a Multi-AZ failover existing connections drop: retry once on a fresh connection.
    if (RETRYABLE.includes(err.code)) return getPool().query(text, params);
    throw err;
  }
}

async function tx(fn) {
  const client = await getPool().connect();
  try {
    await client.query('BEGIN');
    const out = await fn(client);
    await client.query('COMMIT');
    return out;
  } catch (e) {
    await client.query('ROLLBACK').catch(() => {});
    throw e;
  } finally {
    client.release();
  }
}

module.exports = { query, tx, getPool };
