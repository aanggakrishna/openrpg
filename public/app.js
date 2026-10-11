const $ = selector => document.querySelector(selector);
let mode = 'login', saveTimer, currentUser;

window.render_game_to_text = () => JSON.stringify({ screen: currentUser ? 'game' : 'auth', user: currentUser?.username || null });
window.advanceTime = ms => new Promise(resolve => setTimeout(resolve, Math.max(0, ms)));

function message(text = '', bad = false) { const node = $('#message'); node.textContent = text; node.style.color = bad ? '#ff9b9b' : '#75e2b4'; }
function selectMode(next) {
  mode = next;
  document.querySelectorAll('[data-mode]').forEach(button => button.classList.toggle('selected', button.dataset.mode === mode));
  $('#submit').textContent = mode === 'login' ? 'Log in' : 'Create account';
  $('input[name=password]').autocomplete = mode === 'login' ? 'current-password' : 'new-password'; message();
}
async function request(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}
function startGame(user) {
  currentUser = user;
  window.OPENRPG_WASM_SAVE = typeof user.gameState === 'string' ? user.gameState : JSON.stringify(user.gameState || {});
  window.OPENRPG_CONFIG = window.OPENRPG_CONFIG || { onlineServerUrl: '' };
  $('#player').textContent = `Trainer: ${user.username}`;
  $('#auth-shell').hidden = true; $('#game-shell').hidden = false;
  const frame = $('#game'); frame.src = '/desktop/index.html';
}
async function saveGame(serialized) {
  try { await request('/api/save', { method: 'PUT', body: JSON.stringify({ gameState: serialized }) }); }
  catch (error) { console.warn('Cloud save failed:', error.message); }
}
window.addEventListener('message', event => {
  let payload; try { payload = typeof event.data === 'string' ? JSON.parse(event.data) : event.data; } catch { return; }
  if (!payload || payload.type !== 'openrpg-wasm-save') return;
  clearTimeout(saveTimer); saveTimer = setTimeout(() => saveGame(payload.save), 450);
});
window.addEventListener('message', event => {
  let payload; try { payload = typeof event.data === 'string' ? JSON.parse(event.data) : event.data; } catch { return; }
  if (payload?.type === 'openrpg-wasm-error') console.error('OpenRPG browser startup error:', payload.error);
});
document.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => selectMode(button.dataset.mode)));
$('#auth-form').addEventListener('submit', async event => {
  event.preventDefault(); const form = new FormData(event.currentTarget); const body = Object.fromEntries(form);
  message(mode === 'login' ? 'Signing in…' : 'Creating account…');
  try { startGame(await request(`/api/auth/${mode}`, { method: 'POST', body: JSON.stringify(body) })); }
  catch (error) { message(error.message, true); }
});
$('#logout').addEventListener('click', async () => { await request('/api/auth/logout', { method: 'POST' }).catch(() => {}); location.reload(); });
request('/api/auth/me').then(data => data.user && startGame(data.user)).catch(() => {});
