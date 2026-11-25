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

if __name__ == "__main__":
    unittest.main(verbosity=2)
