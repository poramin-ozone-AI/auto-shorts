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

    def test_reject_too_few_scenes(self):
        self.assertFalse(g.valid({"title": "ทดสอบ", "scenes": scene_set(count=3, chars=150)}))

    def test_reject_too_many_scenes(self):
        self.assertFalse(g.valid({"title": "ทดสอบ", "scenes": scene_set(count=19, chars=40)}))

    def test_reject_way_too_short_narration(self):
        self.assertFalse(g.valid({"title": "ทดสอบ", "scenes": scene_set(chars=20)}))  # 180 ตัวอักษร

    def test_reject_way_too_long_narration(self):
        self.assertFalse(g.valid({"title": "ทดสอบ", "scenes": scene_set(chars=210)}))  # 1,890 ตัวอักษร

    def test_accept_outside_intended_but_sane(self):
        for d in (scene_set(count=7, chars=100), scene_set(count=15, chars=50),
                  scene_set(chars=50), scene_set(chars=125)):
            self.assertTrue(g.valid({"title": "ทดสอบ", "scenes": d}))

    def test_soft_notes(self):
        self.assertEqual(g.soft_notes({"scenes": scene_set()}), [])  # 9 ฉาก 765 ตัวอักษร
        self.assertEqual(len(g.soft_notes({"scenes": scene_set(count=7, chars=50)})), 2)
        self.assertEqual(len(g.soft_notes({"scenes": scene_set(chars=125)})), 1)

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
    def setUp(self):
        g.usage.clear()

    def test_usage_counts(self):
        run_call([FakeResp(503), FakeResp(200, {"ok": 1})])
        self.assertEqual(g.usage["m"], {"5xx": 1, "ok": 1})
        g.requests.post = lambda *a, **k: FakeResp(429)
        try:
            g.call("m2", {})
        except g.QuotaError:
            pass
        self.assertEqual(g.usage["m2"], {"429": 1})
        text = "\n".join(g.usage_lines())
        self.assertIn("m: ส่งคำขอ 2 ครั้ง", text)
        self.assertNotIn("DUMMY", text)

    def test_usage_empty(self):
        self.assertEqual(g.usage_lines(), ["- ไม่มีการเรียก Gemini"])

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

import json, contextlib

@contextlib.contextmanager
def in_tmp():
    d, cwd = tempfile.mkdtemp(), os.getcwd()
    os.chdir(d); os.makedirs("work")
    try:
        yield d
    finally:
        os.chdir(cwd)

class ImgResp:
    def __init__(self, code, headers=None, content=b""):
        self.status_code, self.headers, self.content = code, headers or {}, content

class WikiTitleTests(unittest.TestCase):
    def test_similar_title(self):
        self.assertFalse(g.similar_title("Taika meteorite crater", "Shūjin Riku"))
        self.assertTrue(g.similar_title("Mars", "Mars (planet)"))
        self.assertTrue(g.similar_title("Tardigrade", "Tardigrade"))
        self.assertTrue(g.similar_title("Taika_meteorite_crater", "Taika crater"))

    def test_find_article_rejects_unrelated_search_hit(self):
        old_f, old_w = g.fetch_article, g.wiki_get
        g.fetch_article = lambda t: None
        g.wiki_get = lambda p: {"query": {"search": [{"title": "Shūjin Riku"}]}}
        try:
            self.assertIsNone(g.find_article("Taika_meteorite_crater"))
        finally:
            g.fetch_article, g.wiki_get = old_f, old_w

    def test_find_article_accepts_matching_search_hit(self):
        old_f, old_w = g.fetch_article, g.wiki_get
        art = ("Taika crater", "https://x", "a" * 2500)
        g.fetch_article = lambda t: art if t == "Taika crater" else None
        g.wiki_get = lambda p: {"query": {"search": [{"title": "Shūjin Riku"}, {"title": "Taika crater"}]}}
        try:
            self.assertEqual(g.find_article("Taika meteorite crater"), art)
        finally:
            g.fetch_article, g.wiki_get = old_f, old_w

class ImageThrottleTests(unittest.TestCase):
    def setUp(self):
        g._img_not_before, g._consec_402 = 0.0, 0
        self.sleeps = []
        self.old = (g.requests.get, g.time.sleep)
        g.time.sleep = self.sleeps.append

    def tearDown(self):
        g.requests.get, g.time.sleep = self.old

    def test_first_402_stops_without_retry(self):
        calls = []
        g.requests.get = lambda *a, **k: (calls.append(1), ImgResp(402, {"Retry-After": "5"}))[1]
        with in_tmp():
            with self.assertRaises(g.ImageBlocked):
                g.make_image("p", "work/img0.jpg", 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.sleeps, [])

    def test_success_writes_verified_image_cache(self):
        with in_tmp():
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                            "color=c=red:s=720x1280", "-frames:v", "1", "source.jpg"], check=True)
            with open("source.jpg", "rb") as image_file:
                image_bytes = image_file.read()
            g.requests.get = lambda *a, **k: ImgResp(200, {"content-type": "image/jpeg"}, image_bytes)
            self.assertTrue(g.make_image("p", "work/img0.jpg", 1))
            self.assertTrue(os.path.exists("work/img0.jpg.ok"))
            self.assertTrue(g.image_cache_valid("work/img0.jpg", "p", 1))
            self.assertFalse(g.image_cache_valid("work/img0.jpg", "different prompt", 1))
            with open("work/img0.jpg", "ab") as f:
                f.write(b"tampered")
            self.assertFalse(g.image_cache_valid("work/img0.jpg", "p", 1))
        self.assertEqual(g._consec_402, 0)


    def test_preflight_stops_on_429(self):
        calls = []
        old_get = g.requests.get
        g.requests.get = lambda *a, **k: (calls.append(1), ImgResp(429))[1]
        try:
            with in_tmp():
                self.assertFalse(g.preflight_image())
        finally:
            g.requests.get = old_get
        self.assertEqual(len(calls), 1)

    def test_image_generation_stops_on_429(self):
        calls = []
        old_get = g.requests.get
        g.requests.get = lambda *a, **k: (calls.append(1), ImgResp(429))[1]
        try:
            with in_tmp():
                with self.assertRaises(g.ImageBlocked):
                    g.make_image("prompt", "work/img0.jpg", 77)
        finally:
            g.requests.get = old_get
        self.assertEqual(len(calls), 1)

    def test_non_402_failures_never_raise(self):
        g.requests.get = lambda *a, **k: ImgResp(503)
        with in_tmp():
            self.assertFalse(g.make_image("p", "work/img0.jpg", 1))

    def test_gap_between_requests(self):
        g.requests.get = lambda *a, **k: ImgResp(200, {"content-type": "image/jpeg"}, b"x" * 6000)
        with in_tmp():
            g.make_image("p", "work/a.jpg", 1)
            g.make_image("p", "work/b.jpg", 1)
        self.assertTrue(any(s >= 45 for s in self.sleeps), self.sleeps)

class QuotaPolicyTests(unittest.TestCase):
    def test_topic_429_does_not_try_fallback_model(self):
        calls = []
        old = g.ask_json
        def fake(prompt, model, wait=True):
            calls.append(model)
            raise g.QuotaError(model)
        g.ask_json = fake
        try:
            with self.assertRaises(g.QuotaError):
                g.ask_topic("prompt")
        finally:
            g.ask_json = old
        self.assertEqual(calls, [g.TOPIC_MODEL])

    def test_writer_429_does_not_try_fallback_model(self):
        old_json, old_article, old_topic = g.ask_json, g.find_article, g.ask_topic
        calls = []
        g.ask_topic = lambda prompt: {"wiki_title": "Example"}
        g.ask_json = lambda prompt, model, wait=True: (calls.append(model), (_ for _ in ()).throw(g.QuotaError(model)))[1]
        g.find_article = lambda title: ("Example", "https://example.org", "x" * 2500)
        try:
            with self.assertRaises(SystemExit):
                g.get_script()
        finally:
            g.ask_json, g.find_article, g.ask_topic = old_json, old_article, old_topic
        self.assertEqual(calls, [g.TEXT_MODEL])

class WorkflowStaticTests(unittest.TestCase):
    def test_schedule_remains_disabled(self):
        path = ".github/workflows/make-short.yml"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("# schedule:", content)
        self.assertNotRegex(content, r"(?m)^\s+schedule:")

    def test_preflight_runs_offline_tests_before_generation(self):
        with open(".github/workflows/make-short.yml", encoding="utf-8") as f:
            content = f.read()
        test_pos = content.index("python -m unittest -v test_pipeline.py")
        generate_pos = content.index("run: python generate.py")
        self.assertLess(test_pos, generate_pos)

class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.old_env = os.environ.get("RESUME")

    def tearDown(self):
        if self.old_env is None:
            os.environ.pop("RESUME", None)
        else:
            os.environ["RESUME"] = self.old_env

    def test_roundtrip(self):
        script = {"title": "ทดสอบ", "scenes": scene_set()}
        with in_tmp():
            g.save_checkpoint(script, [{"title": "t", "uri": "https://example.org"}], 123)
            os.environ["RESUME"] = "1"
            ck = g.load_checkpoint()
            self.assertEqual(ck["script"], script)
            self.assertEqual(ck["clip_seed"], 123)

    def test_no_resume_flag_returns_none(self):
        os.environ["RESUME"] = "0"
        with in_tmp():
            g.save_checkpoint({"title": "t", "scenes": scene_set()}, [{"title": "src", "uri": "https://example.org"}], 1)
            self.assertIsNone(g.load_checkpoint())

    def test_resume_without_file_exits_not_calls_gemini(self):
        os.environ["RESUME"] = "1"
        with in_tmp():
            with self.assertRaises(SystemExit):
                g.load_checkpoint()

    def test_expired_checkpoint_exits(self):
        os.environ["RESUME"] = "1"
        with in_tmp():
            g.save_checkpoint({"title": "t", "scenes": scene_set()}, [{"title": "src", "uri": "https://example.org"}], 1)
            with open("checkpoint.json", encoding="utf-8") as f:
                ck = json.load(f)
            ck["created"] -= 13 * 3600
            with open("checkpoint.json", "w", encoding="utf-8") as f:
                json.dump(ck, f)
            with self.assertRaises(SystemExit):
                g.load_checkpoint()

class AdditionalSafetyTests(unittest.TestCase):
    def test_fingerprint_changes_when_prompt_or_seed_changes(self):
        a = g.scene_fingerprint("scene A", 1)
        self.assertNotEqual(a, g.scene_fingerprint("scene B", 1))
        self.assertNotEqual(a, g.scene_fingerprint("scene A", 2))

    def test_tts_quota_does_not_fall_back_to_edge(self):
        old_gemini, old_edge = g.tts_gemini, g.tts_edge
        edge_calls = []
        g.tts_gemini = lambda *a, **k: (_ for _ in ()).throw(g.QuotaError("tts"))
        g.tts_edge = lambda *a, **k: edge_calls.append(1)
        try:
            with self.assertRaises(g.QuotaError):
                g.make_voice(scene_set()[:2])
        finally:
            g.tts_gemini, g.tts_edge = old_gemini, old_edge
        self.assertEqual(edge_calls, [])

    def test_workflow_draft_publish_is_opt_in_and_separate(self):
        with open(".github/workflows/make-short.yml", encoding="utf-8") as workflow_file:
            content = workflow_file.read()
        self.assertIn("publish_draft:", content)
        self.assertIn("default: false", content)
        self.assertIn("publish-draft:", content)
        self.assertIn("if: ${{ inputs.publish_draft }}", content)
        self.assertIn("permissions:\n      contents: write", content)
        make_job = content.split("  publish-draft:", 1)[0]
        self.assertNotIn("contents: write", make_job)
        self.assertIn("actions/upload-artifact@v4", make_job)

    def test_legacy_marker_without_hash_metadata_is_not_reused(self):
        with in_tmp():
            with open("work/img0.jpg", "wb") as f:
                f.write(b"x" * 6001)
            with open("work/img0.jpg.ok", "w") as f:
                f.write("1")
            self.assertFalse(g.image_cache_valid("work/img0.jpg", "prompt", 1))

if __name__ == "__main__":
    unittest.main(verbosity=2)
