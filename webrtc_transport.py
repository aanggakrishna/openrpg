"""WebRTC DataChannel transport for OpenRPG.

The HTTP server remains only a short-lived, same-origin signalling endpoint.
After offer/answer, game commands and snapshots travel through a WebRTC
DataChannel.  `aiortc` is deliberately optional so a server can still expose
the lobby over HTTP on platforms where the dependency is unavailable.
"""
import asyncio
import json
import threading
import time

try:
    from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
    AVAILABLE = True
except ImportError:  # The normal HTTP client can still be used as a fallback.
    AVAILABLE = False


class WebRTCBridge:
    """Server-side peers.  World owns game state; this class owns connections."""
    def __init__(self, world, stun_url=''):
        if not AVAILABLE:
            raise RuntimeError('Install aiortc to enable WebRTC')
        self.world = world
        servers = [RTCIceServer(urls=stun_url)] if stun_url else []
        self.config = RTCConfiguration(iceServers=servers)
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True, name='openrpg-webrtc')
        self.thread.start()
        self.peers = set()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def answer(self, offer):
        future = asyncio.run_coroutine_threadsafe(self._answer(offer), self.loop)
        return future.result(timeout=20)

    async def _answer(self, offer):
        pc = RTCPeerConnection(self.config)
        self.peers.add(pc)
        session = {'token': '', 'uid': ''}

        def send(channel, kind, data):
            if channel.readyState == 'open':
                channel.send(json.dumps({'kind': kind, 'data': data}, separators=(',', ':')))

        @pc.on('datachannel')
        def on_datachannel(channel):
            @channel.on('message')
            def on_message(raw):
                try:
                    body = json.loads(raw)
                    if not isinstance(body, dict):
                        raise ValueError('Invalid WebRTC message')
                    if body.get('kind') == 'connect':
                        with self.world.lock:
                            data = self.world.connect(body.get('profile') or {})
                        session['token'], session['uid'] = data['token'], data['me']['id']
                        send(channel, 'connected', data)
                        return
                    if body.get('kind') != 'action' or not session['token']:
                        raise ValueError('Connect before sending actions')
                    with self.world.lock:
                        user = self.world.auth(session['token'])
                        action = body.get('action') or {}
                        self.world.action(user, action)
                        data = self.world.snapshot(user) if user['id'] in self.world.presence else {'disconnected': True}
                    data['_action'] = action.get('action', 'poll')
                    send(channel, 'state', data)
                except (ValueError, KeyError, TypeError) as exc:
                    send(channel, 'error', str(exc))
                except Exception:
                    send(channel, 'error', 'WebRTC server error')

        @pc.on('connectionstatechange')
        async def on_state():
            if pc.connectionState in ('failed', 'closed', 'disconnected'):
                if session['token']:
                    with self.world.lock:
                        try:
                            user = self.world.auth(session['token'])
                            self.world.action(user, {'action': 'disconnect'})
                        except ValueError:
                            pass
                self.peers.discard(pc)
                await pc.close()

        await pc.setRemoteDescription(RTCSessionDescription(sdp=offer['sdp'], type=offer['type']))
        await pc.setLocalDescription(await pc.createAnswer())
        return {'sdp': pc.localDescription.sdp, 'type': pc.localDescription.type}

    def close(self):
        async def shutdown():
            for peer in list(self.peers):
                await peer.close()
            self.peers.clear()
        if self.loop.is_running():
            asyncio.run_coroutine_threadsafe(shutdown(), self.loop).result(timeout=5)
            self.loop.call_soon_threadsafe(self.loop.stop)
