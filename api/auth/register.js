import { register, sessionCookie, publicUser, readBody, respond, fail } from '../_lib/auth.js';

export default async function handler(req, res) {
  if (req.method !== 'POST') return fail(res, 405, 'Method not allowed.');
  const body = readBody(req);
  if (!body) return fail(res, 400, 'Invalid request body.');
  try {
    const { user } = await register(body.username, body.password);
    return respond(res, 201, { user: publicUser(user) }, { 'Set-Cookie': await sessionCookie(user) });
  } catch (error) {
    console.error('Registration failed:', error.message);
    return fail(res, error.status || 500, error.status ? error.message : 'Account service is unavailable.');
  }
}
