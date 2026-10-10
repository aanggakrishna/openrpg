Original prompt: Buat branch baru `openrpg-web`. Jadikan game compatible dengan Vercel: pemain baru mendaftar dengan username dan password, login lalu bermain di browser; terminal tidak perlu dibuat untuk web. Pertahankan fitur game lainnya, termasuk online multiplayer yang servernya sudah di-host pengguna, bukan di Vercel. Jelaskan apakah perubahan ini besar.

## Progress

- Created branch `openrpg-web`; existing uncommitted desktop-game work is preserved on the branch.
- Project has no web client yet, so this branch adds a browser canvas client and Vercel serverless auth/save API while keeping the Pygame app intact.
- Account storage is designed for Neon Postgres; deployment needs `DATABASE_URL` and `SESSION_SECRET` environment variables.
- Online room/PvP remains on the user's separate server. Browser production needs that server reachable over HTTPS (browser mixed-content rules block HTTP from a Vercel HTTPS site).
- Browser edition: implemented retro exploration, 16 on-demand biomes, Pokémon encounters and battles, Pokédex, save/load, daily quest, home/garden/market/center basics, and online rooms/PvP/trade/dungeons client.
- Vercel account/save endpoints use Neon Postgres, bcrypt password hashes, JWT sessions in secure HttpOnly cookies, and same-origin requests. Deploy still requires project environment variables and an HTTPS multiplayer endpoint with the matching CORS configuration.
- Performance follow-up from the attached screen recording: a first-time biome background took about 84–100 ms on the render thread, and a burst of completed sprite downloads could decode in one frame. Biome chunks are now rasterized on a worker and installed from the main thread with a four-chunk LRU cap; downloaded PokéAPI results are consumed one per frame.
- Verification: `node --check` on browser/API JavaScript, production asset build, `npm audit --omit=dev` (0 vulnerabilities), Python compile checks, and 28 Pygame unit tests passed. A real-time headless render profile averaged about 7 ms per frame; the recording still needs a visual retest on the user's machine to confirm the perceived motion improvement.
- Scope: sizeable port, not a one-click desktop-to-Vercel conversion. The browser edition is in progress and does not yet match every Pygame activity. No push or Vercel deployment has been made.
