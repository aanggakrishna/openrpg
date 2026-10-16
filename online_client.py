"""Background HTTP transport; rendering never waits for the network."""
import json
import http.client
import queue
import ssl
import threading
import time
from urllib.parse import urlsplit
try:
    import asyncio
    from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False


class OnlineClient:
    def __init__(self,url,profile):
        parsed=urlsplit(url)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username:raise ValueError('Use http://IP:8765 or an HTTPS server URL')
        self.url=url.rstrip('/');self.profile=profile;self.token=profile.get('token','')
        self.parsed=urlsplit(self.url);self.connection=None
        self.commands=queue.Queue(maxsize=32);self.events=queue.SimpleQueue();self.keys={}
        self.stop=threading.Event();self.connected=False
        self.worker=threading.Thread(target=self.run,daemon=True);self.worker.start()

    def request(self,path,body):
        try:
            if self.connection is None:
                if self.parsed.scheme=='https':
                    self.connection=http.client.HTTPSConnection(self.parsed.hostname,self.parsed.port or 443,timeout=3,context=ssl.create_default_context())
                else:
                    self.connection=http.client.HTTPConnection(self.parsed.hostname,self.parsed.port or 80,timeout=3)
            endpoint=(self.parsed.path.rstrip('/') or '')+path
            payload=json.dumps(body).encode()
            self.connection.request('POST',endpoint,payload,{'Content-Type':'application/json','Authorization':'Bearer '+self.token,'Connection':'keep-alive'})
            response=self.connection.getresponse();raw=response.read(2_000_000)
            data=json.loads(raw or b'{}')
            if response.status>=400:raise ValueError(data.get('error','Server rejected request'))
            return data
        except (OSError, http.client.HTTPException, ValueError) as exc:
            if self.connection:
                try:self.connection.close()
                except OSError:pass
                self.connection=None
            if isinstance(exc,ValueError):raise
            raise ValueError('Online server connection lost') from exc

    def send(self,action,**kwargs):
        try:self.commands.put_nowait(dict(action=action,**kwargs))
        except queue.Full:self.events.put(('error','Please wait for the previous actions'))

    def run(self):
        try:
            data=self.request('/connect',self.profile);self.token=data['token'];self.connected=True
            self.events.put(('connected',data))
            while not self.stop.is_set():
                start=time.monotonic()
                try:
                    try:command=self.commands.get_nowait()
                    except queue.Empty:command=dict(action='input',keys=dict(self.keys))
                    data=self.request('/action',command);data['_action']=command['action'];self.events.put(('state',data))
                except ValueError as exc:self.events.put(('error',str(exc)))
                self.stop.wait(max(0,.085-(time.monotonic()-start)))
        except Exception as exc:self.events.put(('disconnected',str(exc)))
        finally:
            self.connected=False
            if self.token:
                try:self.request('/action',dict(action='disconnect'))
                except Exception:pass

    def close(self):
        self.keys={};self.stop.set()
        if self.connection:
            try:self.connection.close()
            except OSError:pass


class WebRTCClient:
    """Native WebRTC client; HTTP is used only for SDP signalling."""
    def __init__(self,url,profile):
        if not WEBRTC_AVAILABLE:raise ValueError('WebRTC needs aiortc. Install requirements.txt first.')
        parsed=urlsplit(url)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username:
            raise ValueError('Use an HTTP(S) signalling URL')
        self.url=url.rstrip('/');self.profile=profile;self.token=profile.get('token','')
        self.parsed=parsed;self.commands=queue.Queue(maxsize=32);self.events=queue.SimpleQueue();self.keys={}
        self.stop=threading.Event();self.connected=False;self.channel=None;self.pc=None
        self.loop=asyncio.new_event_loop()
        self.worker=threading.Thread(target=self._run,daemon=True,name='openrpg-webrtc-client');self.worker.start()

    def send(self,action,**kwargs):
        try:self.commands.put_nowait(dict(action=action,**kwargs))
        except queue.Full:self.events.put(('error','Please wait for the previous actions'))

    def _signal(self, offer):
        connection=(http.client.HTTPSConnection(self.parsed.hostname,self.parsed.port or 443,timeout=12,context=ssl.create_default_context())
                    if self.parsed.scheme=='https' else http.client.HTTPConnection(self.parsed.hostname,self.parsed.port or 80,timeout=12))
        try:
            path=(self.parsed.path.rstrip('/') or '')+'/webrtc/offer'
            connection.request('POST',path,json.dumps(offer).encode(),{'Content-Type':'application/json'})
            response=connection.getresponse();data=json.loads(response.read() or b'{}')
            if response.status>=400:raise ValueError(data.get('error','WebRTC signalling rejected'))
            return data
        finally:connection.close()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        try:self.loop.run_until_complete(self._connect())
        except Exception as exc:self.events.put(('disconnected',str(exc)))
        finally:
            self.connected=False
            if self.pc:self.loop.run_until_complete(self.pc.close())
            self.loop.close()

    async def _connect(self):
        self.pc=RTCPeerConnection(RTCConfiguration())
        channel=self.pc.createDataChannel('openrpg')
        self.channel=channel

        @channel.on('message')
        def on_message(raw):
            try:
                message=json.loads(raw);kind=message.get('kind');data=message.get('data',{})
                if kind=='connected':self.token=data['token'];self.connected=True
                if kind in ('connected','state','error'):self.events.put((kind,data))
            except (ValueError,TypeError,KeyError):
                self.events.put(('error','Invalid WebRTC server message'))

        offer=await self.pc.createOffer();await self.pc.setLocalDescription(offer)
        answer=await asyncio.to_thread(self._signal,{'sdp':self.pc.localDescription.sdp,'type':self.pc.localDescription.type})
        await self.pc.setRemoteDescription(RTCSessionDescription(sdp=answer['sdp'],type=answer['type']))
        for _ in range(150):
            if channel.readyState=='open':break
            if self.stop.is_set():return
            await asyncio.sleep(.04)
        if channel.readyState!='open':raise ValueError('WebRTC data channel timed out')
        channel.send(json.dumps({'kind':'connect','profile':self.profile}))
        while not self.stop.is_set():
            try:command=self.commands.get_nowait()
            except queue.Empty:command=dict(action='input',keys=dict(self.keys))
            if channel.readyState!='open':raise ValueError('WebRTC data channel closed')
            channel.send(json.dumps({'kind':'action','action':command},separators=(',',':')))
            await asyncio.sleep(.085)
        if channel.readyState=='open':channel.send(json.dumps({'kind':'action','action':{'action':'disconnect'}}))

    def close(self):
        self.keys={};self.stop.set()
