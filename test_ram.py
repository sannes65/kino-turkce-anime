import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import server
from ram_cache import RamCache, byte_range


MEDIA = b'#EXTM3U\n#EXT-X-TARGETDURATION:5\n#EXTINF:5,\na.ts\n#EXTINF:5,\nb.ts\n#EXT-X-ENDLIST\n'


class RamTests(unittest.TestCase):
    def setUp(self):
        self.files = {'https://example.org/video.m3u8': MEDIA,
                      'https://example.org/a.ts': b'first-segment',
                      'https://example.org/b.ts': b'second-segment'}
        self.requests = []
        self.cache = RamCache(self.fetch, limit=1048576, workers=2)

    def tearDown(self):
        for e in list(self.cache.entries.values()):
            self.cache.cancel(e['id'])

    def fetch(self, url, ref, limit, cancel):
        self.requests.append((url,ref))
        data = self.files[url]
        if len(data)>limit: raise ValueError('oversized')
        return data, url, 'video/mp2t'

    def prepare(self,key='anime:1:720',url='https://example.org/video.m3u8',**kw):
        return self.cache.prepare(key,url,'https://ref.example/',**kw)

    def wait(self,entry,state='ready'):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            current=self.cache.status(entry['id'])['entry']
            if current and current['state'] in ('ready','error'):
                self.assertEqual(current['state'],state,current)
                return current
            time.sleep(.005)
        self.fail('cache did not finish')

    def test_ready_playlist_is_fully_local_and_read_without_upstream(self):
        e=self.wait(self.prepare())
        before=len(self.requests)
        manifest=self.cache.asset(e['id'],e['playlist'].rsplit('/',1)[1])[0].decode()
        self.assertNotIn('https:',manifest)
        for line in manifest.splitlines():
            if line and not line.startswith('#'):
                self.assertTrue(self.cache.asset(e['id'],line.rsplit('/',1)[1]))
        self.assertEqual(len(self.requests),before)
        self.assertEqual(e['percent'],100)

    def test_cache_reuse_does_not_download_twice(self):
        e=self.wait(self.prepare())
        count=len(self.requests)
        self.assertEqual(self.prepare()['id'],e['id'])
        self.assertEqual(len(self.requests),count)

    def test_selects_720_and_downloads_audio_keys_and_map(self):
        self.files['https://example.org/master.m3u8']=b'#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",DEFAULT=YES,NAME="Audio",URI="audio.m3u8"\n#EXT-X-STREAM-INF:BANDWIDTH=5000,RESOLUTION=1920x1080,AUDIO="aud"\nhigh.m3u8\n#EXT-X-STREAM-INF:BANDWIDTH=2000,RESOLUTION=1280x720,AUDIO="aud"\nvideo.m3u8\n'
        self.files['https://example.org/audio.m3u8']=b'#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key"\n#EXT-X-MAP:URI="init.mp4"\n#EXTINF:10,\nsound.aac\n#EXT-X-ENDLIST\n'
        for name in ('key','init.mp4','sound.aac'): self.files['https://example.org/'+name]=b'1234567890123456'
        e=self.wait(self.prepare(url='https://example.org/master.m3u8'))
        self.assertEqual(e['height'],720)
        self.assertFalse(any('high.m3u8' in u for u,r in self.requests))
        self.assertEqual(e['done'],5)
        manifests=[b.decode() for name,(b,m) in self.cache.entries[e['id']]['assets'].items() if name.endswith('.m3u8')]
        self.assertEqual(len(manifests),3)
        self.assertTrue(all('https:' not in x for x in manifests))

    def test_byte_range_segments_are_deduplicated(self):
        self.files['https://example.org/video.m3u8']=b'#EXTM3U\n#EXT-X-TARGETDURATION:5\n#EXTINF:5,\n#EXT-X-BYTERANGE:5@0\na.ts\n#EXTINF:5,\n#EXT-X-BYTERANGE:5@5\na.ts\n#EXT-X-ENDLIST\n'
        e=self.wait(self.prepare())
        self.assertEqual(e['total'],1)

    def test_live_playlist_fails_without_pretending_to_be_ready(self):
        self.files['https://example.org/video.m3u8']=MEDIA.replace(b'#EXT-X-ENDLIST',b'')
        e=self.wait(self.prepare(),state='error')
        self.assertIsNone(e['playlist'])
        self.assertEqual(self.cache.used,0)

    def test_memory_limit_clears_partial_cache(self):
        self.cache.limit=200
        self.files['https://example.org/a.ts']=b'x'*150
        self.files['https://example.org/b.ts']=b'y'*150
        e=self.wait(self.prepare(),state='error')
        self.assertEqual(self.cache.used,0)
        self.assertEqual(e['bytes'],0)
        self.assertFalse(self.cache.asset(e['id'],'asset-0'))

    def test_prefetch_promotes_without_redownload_and_drops_previous(self):
        one=self.wait(self.prepare())
        two=self.wait(self.prepare(key='anime:2:720',role='next',owner='anime:1:720'))
        count=len(self.requests)
        self.assertEqual(len(self.cache.entries),2)
        promoted=self.prepare(key='anime:2:720')
        self.assertEqual(promoted['id'],two['id'])
        self.assertEqual(len(self.requests),count)
        self.assertIsNone(self.cache.status(one['id'])['entry'])
        self.assertEqual(len(self.cache.entries),1)

    def test_stale_prefetch_owner_is_rejected(self):
        self.wait(self.prepare())
        with self.assertRaises(ValueError): self.prepare(key='anime:2:720',role='next',owner='old:1:720')

    def test_ttl_reclaims_memory(self):
        e=self.wait(self.prepare())
        self.cache.entries[e['id']]['touched']-=601
        self.cache.reap()
        self.assertEqual(self.cache.used,0)
        self.assertFalse(self.cache.entries)

    def test_cancel_during_download_cannot_repopulate_cache(self):
        started=threading.Event(); release=threading.Event()
        real=self.fetch
        def delayed(url,ref,limit,cancel):
            if not url.endswith('.m3u8'):
                started.set(); release.wait(2)
            return real(url,ref,limit,cancel)
        self.cache.download=delayed
        e=self.prepare(); self.assertTrue(started.wait(2))
        self.cache.cancel(e['id']); release.set(); time.sleep(.05)
        self.assertFalse(self.cache.entries)
        self.assertEqual(self.cache.used,0)

    def test_error_retry_gets_new_job(self):
        original=self.files.pop('https://example.org/a.ts')
        failed=self.wait(self.prepare(),state='error')
        self.files['https://example.org/a.ts']=original
        e=self.wait(self.prepare(retry=True))
        self.assertNotEqual(failed['id'],e['id'])

    def test_http_ram_is_available_after_upstream_is_disabled(self):
        e=self.wait(self.prepare())
        self.cache.download=lambda *args: self.fail('RAM read attempted upstream')
        http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        threading.Thread(target=http.serve_forever,daemon=True).start()
        try:
            with patch.object(server,'RAM',self.cache):
                url='http://127.0.0.1:%d/ram/%s/asset-0'%(http.server_port,e['id'])
                request=urllib.request.Request(url,headers={'Range':'bytes=2-5'})
                with urllib.request.urlopen(request,timeout=2) as response:
                    self.assertEqual(response.status,206)
                    self.assertEqual(response.read(),b'rst-')
                    self.assertEqual(response.headers['X-Kino-Source'],'RAM')
                with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=2) as response:
                    self.assertEqual(response.read(),b'')
                with self.assertRaises(urllib.error.HTTPError) as failure:
                    urllib.request.urlopen(urllib.request.Request(url,headers={'Range':'bytes=999-'}),timeout=2)
                self.assertEqual(failure.exception.code,416)
                failure.exception.close()
        finally: http.shutdown(); http.server_close()

    def test_ranges(self):
        self.assertEqual(byte_range('bytes=2-5',10),(2,5))
        self.assertEqual(byte_range('bytes=-3',10),(7,9))
        self.assertEqual(byte_range('bytes=2-',10),(2,9))
        self.assertEqual(byte_range('bytes=2-999',10),(2,9))
        for invalid in ('bytes=','bytes=10-','bytes=3-2','bytes=0-1,3-4','bytes=-0'):
            with self.assertRaises(ValueError): byte_range(invalid,10)

    def test_download_blocks_private_target_before_fetch(self):
        with patch.object(server,'px_allowed',return_value=False),patch.object(server.urllib.request,'build_opener') as opener:
            with self.assertRaises(ValueError): server.ram_download('http://127.0.0.1/a','',10,threading.Event())
            opener.assert_not_called()

if __name__=='__main__': unittest.main(verbosity=2)
