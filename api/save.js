import { currentUser, respond, fail, readBody } from './_lib/auth.js';

export default async function handler(req, res) {
  if (!['GET', 'PUT'].includes(req.method)) return fail(res, 405, 'Method not allowed.');
  try {
    const user = await currentUser(req);
    if (!user) return fail(res, 401, 'Sign in to continue.');
    if (req.method === 'GET') return respond(res, 200, { gameState: user.game_state || {} });
    const body = readBody(req);
    if (!body || !body.gameState || typeof body.gameState !== 'object' || Array.isArray(body.gameState)) return fail(res, 400, 'Invalid save data.');
    const encoded = JSON.stringify(body.gameState);
    if (encoded.length > 200_000) return fail(res, 413, 'Save data is too large.');
    const { neon } = await import('@neondatabase/serverless');
    const sql = neon(process.env.DATABASE_URL);
    await sql`UPDATE openrpg_users SET game_state = ${encoded}::jsonb, updated_at = NOW() WHERE id = ${user.id}`;
    return respond(res, 200, { ok: true });
  } catch (error) {
    console.error('Save request failed:', error.message);
    return fail(res, 500, 'Save service is unavailable.');
  }
}
