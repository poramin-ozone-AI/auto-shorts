import os, importlib.util, unittest

os.environ["GEMINI_API_KEY"] = "DUMMY_NOT_A_REAL_KEY"
spec = importlib.util.spec_from_file_location("generator", "generate.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

def scene_set(count=9, chars=85, prompt="Stickman examining an object"):
    return [{"narration": "ก" * chars, "image_prompt": prompt} for _ in range(count)]

class SafeTests(unittest.TestCase):
    def test_creative_identity(self):
        self.assertIn("ความรู้แปลกๆ", g.TOPIC_PROMPT)
        self.assertIn("white round-headed stickman", g.CHARACTER)
        self.assertIn("white and green mohawk", g.CHARACTER)
        self.assertIn("→ ฉากกลางเฉลยทีละชั้น", g.WRITER)

    def test_valid_nine_scenes(self):
        self.assertTrue(g.valid({"title": "ทดสอบ", "scenes": scene_set()}))

    def test_reject_seven_scenes(self):
        self.assertFalse(g.valid({"title": "ทดสอบ", "scenes": scene_set(count=7, chars=100)}))

    def test_reject_fifteen_scenes(self):
        self.assertFalse(g.valid({"title": "ทดสอบ", "scenes": scene_set(count=15, chars=50)}))

    def test_reject_short_total_narration(self):
        self.assertFalse(g.valid({"title": "ทดสอบ", "scenes": scene_set(chars=50)}))

    def test_reject_long_total_narration(self):
        self.assertFalse(g.valid({"title": "ทดสอบ", "scenes": scene_set(chars=125)}))

    def test_reject_empty_prompt(self):
        self.assertFalse(g.valid({"title": "ทดสอบ", "scenes": scene_set(prompt="")}))

    def test_reject_missing_title(self):
        self.assertFalse(g.valid({"scenes": scene_set()}))

import base64, struct, math, tempfile, subprocess, shutil

class FakeResp:
    def __init__(self, code, j=None):
        self.status_code, self._j, self.text = code, j, ""
    def json(self):
        return self._j

def run_call(seq, wait=True):
    calls = []
    it = iter(seq)
    def post(*a, **k):
        calls.append(1)
        return next(it)
    old_post, old_sleep = g.requests.post, g.time.sleep
    g.requests.post, g.time.sleep = post, lambda x: None
    try:
        return g.call("m", {}, wait=wait), len(calls)
    finally:
        g.requests.post, g.time.sleep = old_post, old_sleep

class MockApiTests(unittest.TestCase):
    def test_429_stops_immediately(self):
        old = g.requests.post
        n = []
        g.requests.post = lambda *a, **k: (n.append(1), FakeResp(429))[1]
        try:
            with self.assertRaises(g.QuotaError):
                g.call("m", {})
        finally:
            g.requests.post = old
        self.assertEqual(len(n), 1)

    def test_5xx_retries_once_then_ok(self):
        out, n = run_call([FakeResp(503), FakeResp(200, {"ok": 1})])
        self.assertEqual((out, n), ({"ok": 1}, 2))

    def test_5xx_no_wait_returns_fast(self):
        out, n = run_call([FakeResp(503), FakeResp(200, {"ok": 1})], wait=False)
        self.assertEqual((out, n), (None, 1))

    def test_4xx_no_retry(self):
        out, n = run_call([FakeResp(400)])
        self.assertEqual((out, n), (None, 1))

@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class MockTtsTests(unittest.TestCase):
    def _tts(self, mime, seconds=2, rate=24000):
        pcm = b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(rate * seconds))
        old = g.call
        g.call = lambda m, b, wait=True: {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": mime, "data": base64.b64encode(pcm).decode()}}]}}]}
        d = tempfile.mkdtemp()
        cwd = os.getcwd()
        try:
            os.chdir(d); os.makedirs("work")
            ok = g.tts_gemini("x", "m", "work/v.wav")
            return ok, g.audio_duration("work/v.wav")
        finally:
            os.chdir(cwd); g.call = old

    def test_pcm_24k(self):
        ok, dur = self._tts("audio/L16;codec=pcm;rate=24000")
        self.assertTrue(ok); self.assertAlmostEqual(dur, 2.0, delta=0.1)

    def test_pcm_other_rate_keeps_duration(self):
        ok, dur = self._tts("audio/L16;codec=pcm;rate=16000", rate=16000)
        self.assertTrue(ok); self.assertAlmostEqual(dur, 2.0, delta=0.1)

if __name__ == "__main__":
    unittest.main(verbosity=2)
