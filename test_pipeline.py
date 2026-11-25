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
        self.text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)

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

MANGA = ("Shūjin Riku (囚人リク) is a Japanese manga series written and illustrated by Yuji Nishi. " + "x" * 2600)

class ArticleGateTests(unittest.TestCase):
    def _with(self, fetch, search=()):
        old_f, old_w = g.fetch_article, g.wiki_get
        g.fetch_article = fetch
        g.wiki_get = lambda p: {"query": {"search": [{"title": x} for x in search]}}
        return old_f, old_w

    def test_redirect_to_unrelated_manga_rejected(self):
        old = self._with(lambda t: ("Shūjin Riku", "https://x", MANGA))
        try:
            self.assertIsNone(g.find_article("Taika_meteorite_crater"))
        finally:
            g.fetch_article, g.wiki_get = old

    def test_redirect_to_related_article_accepted(self):
        art = ("Tardigrade", "https://x", "Tardigrades, known colloquially as water bears, are animals. " + "a" * 2600)
        old = self._with(lambda t: art)
        try:
            self.assertEqual(g.find_article("Water bear"), art)
        finally:
            g.fetch_article, g.wiki_get = old

    def test_same_title_accepted(self):
        art = ("Mars", "https://x", "Mars is the fourth planet from the Sun. " + "a" * 2600)
        self.assertTrue(g.article_ok("Mars", art))

    def test_offtopic_types_rejected_even_if_title_matches(self):
        for lead in ("X is a 2019 American film directed by Y.", "X is a Japanese anime series.",
                     "X is a video game developed by Y."):
            self.assertFalse(g.article_ok("X", ("X", "u", lead + " " + "a" * 2600)), lead)

    def test_science_leads_not_rejected(self):
        for title, lead in (("Axolotl", "The axolotl is a paedomorphic salamander."),
                            ("Tardigrade", "Tardigrades are eight-legged micro-animals."),
                            ("Antikythera mechanism", "The Antikythera mechanism is an ancient Greek hand-powered orrery.")):
            self.assertTrue(g.article_ok(title, (title, "u", lead + " " + "a" * 2600)), lead)

class WriterOrderTests(unittest.TestCase):
    def test_default_lite_first_flash_last(self):
        self.assertEqual(g.WRITER_MODELS, [g.TOPIC_MODEL, g.TOPIC_MODEL, g.TEXT_MODEL])

    def test_flash_primary_switch_restores_old_order(self):
        old = os.environ.get("WRITER_PRIMARY")
        os.environ["WRITER_PRIMARY"] = "flash"
        try:
            spec2 = importlib.util.spec_from_file_location("generator2", "generate.py")
            g2 = importlib.util.module_from_spec(spec2)
            spec2.loader.exec_module(g2)
            self.assertEqual(g2.WRITER_MODELS, [g2.TEXT_MODEL, g2.TOPIC_MODEL, g2.TOPIC_MODEL])
        finally:
            if old is None:
                os.environ.pop("WRITER_PRIMARY", None)
            else:
                os.environ["WRITER_PRIMARY"] = old

class CloudflareImageProviderTests(unittest.TestCase):
    def setUp(self):
        self.old = (g.CF_ACCOUNT_ID, g.CF_API_TOKEN, g.requests.post, g.time.sleep)
        g.CF_ACCOUNT_ID, g.CF_API_TOKEN = "account-test", "token-test"
        g.time.sleep = lambda _: None

    def tearDown(self):
        g.CF_ACCOUNT_ID, g.CF_API_TOKEN, g.requests.post, g.time.sleep = self.old

    def test_missing_credentials_stops_without_network(self):
        g.CF_ACCOUNT_ID, g.CF_API_TOKEN = "", ""
        calls = []
        g.requests.post = lambda *a, **k: calls.append(1)
        with in_tmp():
            with self.assertRaises(g.ImageProviderError):
                g.make_image("scene", "work/img0.jpg", 42, scene_set()[0])
        self.assertEqual(calls, [])

    def test_success_uses_multipart_and_writes_scene_bound_marker(self):
        png = b"\x89PNG\r\n\x1a\n" + b"x" * 6000
        seen = {}
        def fake(url, **kwargs):
            seen.update(kwargs)
            return ImgResp(200, {"content-type": "image/png"}, png)
        g.requests.post = fake
        scene = scene_set()[0]
        with in_tmp():
            self.assertTrue(g.make_image("scene", "work/img0.jpg", 42, scene))
            self.assertTrue(g.validate_image_file("work/img0.jpg", g.scene_fingerprint(scene)))
            self.assertIn("files", seen)
            self.assertEqual(seen["files"]["width"], (None, str(g.IMG_W)))
            self.assertEqual(seen["files"]["height"], (None, str(g.IMG_H)))
            self.assertEqual(seen["headers"]["Authorization"], "Bearer token-test")
            self.assertFalse(g.validate_image_file("work/img0.jpg", "wrong-scene-hash"))

    def test_success_decodes_cloudflare_json_base64_image(self):
        png = b"\x89PNG\r\n\x1a\n" + b"x" * 6000
        encoded = g.base64.b64encode(png).decode("ascii")
        class JsonResp(ImgResp):
            def json(self):
                return {"success": True, "result": {"image": encoded}}
        g.requests.post = lambda *a, **k: JsonResp(200, {"content-type": "application/json"}, b'{"result":{"image":"..."}}')
        scene = scene_set()[0]
        with in_tmp():
            self.assertTrue(g.make_image("scene", "work/img0.jpg", 42, scene))
            with open("work/img0.jpg", "rb") as f:
                self.assertEqual(f.read(), png)
            self.assertTrue(g.validate_image_file("work/img0.jpg", g.scene_fingerprint(scene)))

    def test_success_decodes_top_level_base64_image(self):
        png = b"\x89PNG\r\n\x1a\n" + b"x" * 6000
        encoded = g.base64.b64encode(png).decode("ascii")
        class JsonResp(ImgResp):
            def json(self):
                return {"image": encoded}
        g.requests.post = lambda *a, **k: JsonResp(200, {"content-type": "application/json"}, b'{"image":"..."}')
        with in_tmp():
            self.assertTrue(g.make_image("scene", "work/img0.jpg", 42, scene_set()[0]))

    def test_bad_base64_image_is_rejected(self):
        class JsonResp(ImgResp):
            def json(self):
                return {"success": True, "result": {"image": "not-valid-base64!!!"}}
        g.requests.post = lambda *a, **k: JsonResp(200, {"content-type": "application/json"}, b'{"result":{"image":"bad"}}')
        with in_tmp():
            with self.assertRaises(g.ImageProviderError):
                g.make_image("scene", "work/img0.jpg", 42, scene_set()[0])

    def test_402_stops_without_retry(self):
        calls = []
        g.requests.post = lambda *a, **k: (calls.append(1), ImgResp(402, {}, b"quota"))[1]
        with in_tmp():
            with self.assertRaises(g.ImageQuotaError):
                g.make_image("scene", "work/img0.jpg", 42, scene_set()[0])
        self.assertEqual(len(calls), 1)

    def test_429_stops_without_retry(self):
        calls = []
        g.requests.post = lambda *a, **k: (calls.append(1), ImgResp(429, {"Retry-After": "30"}, b"busy"))[1]
        with in_tmp():
            with self.assertRaises(g.ImageQuotaError):
                g.make_image("scene", "work/img0.jpg", 42, scene_set()[0])
        self.assertEqual(len(calls), 1)

    def test_5xx_retries_once_then_succeeds(self):
        png = b"\x89PNG\r\n\x1a\n" + b"x" * 6000
        calls = []
        def fake(*a, **k):
            calls.append(1)
            return ImgResp(503) if len(calls) == 1 else ImgResp(200, {"content-type": "image/png"}, png)
        g.requests.post = fake
        with in_tmp():
            self.assertTrue(g.make_image("scene", "work/img0.jpg", 42, scene_set()[0]))
        self.assertEqual(len(calls), 2)

    def test_bad_200_body_is_rejected(self):
        g.requests.post = lambda *a, **k: ImgResp(200, {"content-type": "application/json"}, b"not an image" * 1000)
        with in_tmp():
            with self.assertRaises(g.ImageProviderError):
                g.make_image("scene", "work/img0.jpg", 42, scene_set()[0])


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
            g.save_checkpoint(script, [{"title": "t", "uri": "u"}], 123)
            os.environ["RESUME"] = "1"
            ck = g.load_checkpoint()
            self.assertEqual(ck["script"], script)
            self.assertEqual(ck["clip_seed"], 123)

    def test_no_resume_flag_returns_none(self):
        os.environ["RESUME"] = "0"
        with in_tmp():
            g.save_checkpoint({"title": "t", "scenes": scene_set()}, [], 1)
            self.assertIsNone(g.load_checkpoint())

    def test_resume_without_file_exits_not_calls_gemini(self):
        os.environ["RESUME"] = "1"
        with in_tmp():
            with self.assertRaises(SystemExit):
                g.load_checkpoint()

    def test_checkpoint_v2_persists_image_manifest(self):
        script = {"title": "ทดสอบ", "scenes": scene_set()}
        images = {"0": {"scene_hash": "abc", "sha256": "def", "file": "img0.jpg"}}
        with in_tmp():
            g.save_checkpoint(script, [], 99, images)
            os.environ["RESUME"] = "1"
            ck = g.load_checkpoint()
            self.assertEqual(ck["version"], 2)
            self.assertEqual(ck["images"], images)

    def test_expired_checkpoint_exits(self):
        os.environ["RESUME"] = "1"
        with in_tmp():
            g.save_checkpoint({"title": "t", "scenes": scene_set()}, [], 1)
            with open("checkpoint.json", encoding="utf-8") as f:
                ck = json.load(f)
            ck["created"] -= 13 * 3600
            with open("checkpoint.json", "w", encoding="utf-8") as f:
                json.dump(ck, f)
            with self.assertRaises(SystemExit):
                g.load_checkpoint()


class WorkflowStaticTests(unittest.TestCase):
    def test_create_clip_step_passes_all_required_secrets(self):
        with open(".github/workflows/make-short.yml", encoding="utf-8") as f:
            workflow = f.read()
        start = workflow.index("      - name: สร้างคลิป")
        end = workflow.find("\\n      - name:", start + 1)
        step = workflow[start:] if end < 0 else workflow[start:end]
        self.assertIn("GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}", step)
        self.assertIn("CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}", step)
        self.assertIn("CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}", step)
        self.assertIn("run: python generate.py", step)
        self.assertNotRegex(step, r"(?i)echo\\s+.*(?:GEMINI_API_KEY|CLOUDFLARE_API_TOKEN)")

if __name__ == "__main__":
    unittest.main(verbosity=2)
