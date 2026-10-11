import bcrypt from 'bcryptjs';
import { SignJWT, jwtVerify } from 'jose';
import { neon } from '@neondatabase/serverless';

const usernamePattern = /^[a-zA-Z0-9_]{3,20}$/;
const cookieName = 'openrpg_session';

function database() {
  if (!process.env.DATABASE_URL) throw new Error('DATABASE_URL is not configured');
  return neon(process.env.DATABASE_URL);
}

function secret() {
  const value = process.env.SESSION_SECRET;
  if (!value || Buffer.byteLength(value) < 32) throw new Error('SESSION_SECRET must contain at least 32 bytes');
  return new TextEncoder().encode(value);
}

export async function ensureSchema(sql) {
  await sql`CREATE TABLE IF NOT EXISTS openrpg_users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    game_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  )`;
}

export function readBody(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  try { return JSON.parse(req.body || '{}'); } catch { return null; }
}

export function respond(res, status, body, extraHeaders = {}) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...extraHeaders });
  res.end(JSON.stringify(body));
}

export function fail(res, status, message) {
  return respond(res, status, { error: message });
}

export async function register(username, password) {
  if (typeof username !== 'string' || !usernamePattern.test(username)) {
    const error = new Error('Username must be 3–20 letters, numbers, or underscores.'); error.status = 400; throw error;
  }
  if (typeof password !== 'string' || password.length < 10 || password.length > 72) {
    const error = new Error('Password must be 10–72 characters.'); error.status = 400; throw error;
  }
  const sql = database();
  await ensureSchema(sql);
  const hash = await bcrypt.hash(password, 12);
  const id = crypto.randomUUID();
  const rows = await sql`INSERT INTO openrpg_users (id, username, password_hash)
    VALUES (${id}, ${username.toLowerCase()}, ${hash})
    ON CONFLICT (username) DO NOTHING RETURNING id, username, game_state`;
  if (!rows.length) { const error = new Error('That username is already taken.'); error.status = 409; throw error; }
  return { sql, user: rows[0] };
}

export async function login(username, password) {
  if (typeof username !== 'string' || typeof password !== 'string') {
    const error = new Error('Enter your username and password.'); error.status = 400; throw error;
  }
  const sql = database();
  await ensureSchema(sql);
  const rows = await sql`SELECT id, username, password_hash, game_state FROM openrpg_users WHERE username = ${username.toLowerCase()} LIMIT 1`;
  const user = rows[0];
  if (!user || !(await bcrypt.compare(password, user.password_hash))) {
    const error = new Error('Username or password is incorrect.'); error.status = 401; throw error;
  }
  return { sql, user };
}

export async function sessionCookie(user) {
  const token = await new SignJWT({ username: user.username })
    .setProtectedHeader({ alg: 'HS256' }).setSubject(user.id)
    .setIssuedAt().setExpirationTime('14d').sign(secret());
  const secure = process.env.NODE_ENV === 'production' ? '; Secure' : '';
  return `${cookieName}=${token}; HttpOnly; Path=/; SameSite=Lax; Max-Age=1209600${secure}`;
}

export async function currentUser(req, sql = database()) {
  const raw = req.headers.cookie || '';
  const token = raw.split(';').map(part => part.trim()).find(part => part.startsWith(`${cookieName}=`))?.slice(cookieName.length + 1);
  if (!token) return null;
  try {
    const { payload } = await jwtVerify(token, secret());
    await ensureSchema(sql);
    const rows = await sql`SELECT id, username, game_state FROM openrpg_users WHERE id = ${payload.sub} LIMIT 1`;
    return rows[0] || null;
  } catch { return null; }
}

export function publicUser(user) {
  return { id: user.id, username: user.username, gameState: user.game_state || {} };
}

export const clearSessionCookie = `${cookieName}=; HttpOnly; Path=/; SameSite=Lax; Max-Age=0${process.env.NODE_ENV === 'production' ? '; Secure' : ''}`;
