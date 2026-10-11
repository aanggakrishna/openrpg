import { currentUser, publicUser, respond, fail } from '../_lib/auth.js';

export default async function handler(req, res) {
  if (req.method !== 'GET') return fail(res, 405, 'Method not allowed.');
  try {
    const user = await currentUser(req);
    if (!user) return fail(res, 401, 'Sign in to continue.');
    return respond(res, 200, { user: publicUser(user) });
  } catch (error) {
    console.error('Session lookup failed:', error.message);
    return fail(res, 500, 'Account service is unavailable.');
  }
}
