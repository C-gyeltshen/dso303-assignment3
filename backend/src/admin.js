'use strict';
// Admin API (POST /api/admin/users). Runs outside the VPC because it only talks to Cognito.
const {
  CognitoIdentityProviderClient, AdminCreateUserCommand, AdminAddUserToGroupCommand,
} = require('@aws-sdk/client-cognito-identity-provider');
const { HttpError, json, getUser, requireRole, parseBody } = require('./http');

const cognito = new CognitoIdentityProviderClient({});

exports.handler = async (event) => {
  try {
    const method = event.requestContext?.http?.method;
    const path = (event.rawPath || '').replace(/\/+$/, '');
    if (method !== 'POST' || path !== '/api/admin/users') return json(404, { error: 'Not found' });
    const user = getUser(event);
    requireRole(user, 'admins');
    const b = parseBody(event);
    if (!b.email || !['students', 'tutors', 'admins'].includes(b.group)) throw new HttpError(400, 'email and group required');
    await cognito.send(new AdminCreateUserCommand({
      UserPoolId: process.env.USER_POOL_ID,
      Username: b.email,
      UserAttributes: [{ Name: 'email', Value: b.email }, { Name: 'email_verified', Value: 'true' }],
      DesiredDeliveryMediums: ['EMAIL'],
    }));
    await cognito.send(new AdminAddUserToGroupCommand({ UserPoolId: process.env.USER_POOL_ID, Username: b.email, GroupName: b.group }));
    return json(201, { created: b.email, group: b.group });
  } catch (err) {
    if (err instanceof HttpError) return json(err.status, { error: err.message });
    if (err.name === 'UsernameExistsException') return json(409, { error: 'User already exists' });
    console.error(JSON.stringify({ level: 'ERROR', message: err.message }));
    return json(500, { error: 'Internal error' });
  }
};
