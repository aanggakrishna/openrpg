import { cp, mkdir, access } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = path.join(root, 'assets', 'pokemon-sprites');
const target = path.join(root, 'public', 'assets', 'pokemon-sprites');
const audioSource = path.join(root, 'assets', 'audio');
const audioTarget = path.join(root, 'public', 'assets', 'audio');
const config = `window.OPENRPG_CONFIG = ${JSON.stringify({ onlineServerUrl: process.env.NEXT_PUBLIC_ONLINE_SERVER_URL || '' })};\n`;
await mkdir(path.join(root, 'public'), { recursive: true });
await (await import('node:fs/promises')).writeFile(path.join(root, 'public', 'config.js'), config);
await mkdir(path.dirname(target), { recursive: true });
try {
  await access(source);
  await cp(source, target, { recursive: true, force: false, errorOnExist: false });
  console.log('Prepared bundled Pokémon sprites for lazy browser loading.');
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
  console.warn('Pokémon sprites are missing; browser will use PokéAPI URLs as fallback.');
}
await cp(audioSource, audioTarget, { recursive: true, force: true });
console.log('Prepared music and sound effects for lazy browser playback.');
