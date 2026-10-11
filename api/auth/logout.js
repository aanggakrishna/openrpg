import { clearSessionCookie, respond, fail } from '../_lib/auth.js';

export default async function handler(req, res) {
  if (req.method !== 'POST') return fail(res, 405, 'Method not allowed.');
  return respond(res, 200, { ok: true }, { 'Set-Cookie': clearSessionCookie });
}
