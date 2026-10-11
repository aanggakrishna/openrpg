import { writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';

const output = join(process.cwd(), 'public');
await mkdir(output, { recursive: true });
const onlineServerUrl = process.env.NEXT_PUBLIC_ONLINE_SERVER_URL || '';
await writeFile(join(output, 'config.js'), `window.OPENRPG_CONFIG = { onlineServerUrl: ${JSON.stringify(onlineServerUrl)} };\n`);
