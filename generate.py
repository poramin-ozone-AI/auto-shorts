import os, sys, re, json, time, base64, random, subprocess, urllib.parse, difflib, unicodedata, hashlib
import requests

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()  # strip กันช่องว่าง/บรรทัดใหม่ติดมากับ Secret
if not API_KEY:
    sys.exit("ไม่พบ GEMINI_API_KEY ใน Secret (Settings > Secrets and variables > Actions)")
CATEGORIES = ["ร่างกายมนุษย์", "สัตว์", "อวกาศและดาราศาสตร์", "ประวัติศาสตร์",
              "ธรรมชาติและภูมิศาสตร์", "สมองและจิตวิทยา", "มหาสมุทรและสัตว์ทะเล"]
NICHE = os.environ.get("NICHE", "").strip() or random.choice(CATEGORIES)
VOICE = os.environ.get("VOICE_NAME", "").strip() or "Enceladus"

TEXT_MODEL = "gemini-3.8-flash"          # โมเดลเขียนบท
TOPIC_MODEL = "gemini-3.5-flash-lite"    # เลือกหัวข้อ (โควตาแยก ถ้าใช้ไม่ได้จะถอยไปใช้ TEXT_MODEL)
# เขียนบท: ลอง 3.8 Flash ก่อน ถ้า 503/โควตาเต็ม/บทผิดเกณฑ์ ถอยไป flash-lite (ถ้าบทผิดเกณฑ์ที่ lite ลองซ้ำได้อีก 1 ครั้ง)
WRITER_MODELS = [TEXT_MODEL, TOPIC_MODEL, TOPIC_MODEL]
# TTS fallback order: expressive Gemini Flash -> faster/lower-cost Gemini Flash-Lite -> Thai Edge Neural.
# HTTP 429 is a hard stop (do not cascade to another provider when quota is exhausted).
TTS_MODELS = ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"]
EDGE_VOICE = "th-TH-NiwatNeural"
TTS_STYLE = "พูดภาษาไทยแบบคนเล่าเรื่องให้เพื่อนฟัง ชัดเจนทุกคำ และเว้นจังหวะก่อนข้อเท็จจริงที่น่าทึ่งที่สุด:"
API = "https://generativelanguage.googleapis.com/v1beta/models/"
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
FPS = 30
PAST_LIMIT = 30
TOPIC_TRIES = 2

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_HEADERS = {"User-Agent": "auto-shorts/1.0 (https://github.com/poramin-ozone-AI/auto-shorts)"}
ARTICLE_MAX = 14000
ARTICLE_MIN = 2000

STYLE = ("rough amateur hand-drawn colored-pencil and crayon cartoon illustration, landscape horizontal 16:9, "
         "visible uneven scribble strokes and paper texture, imperfect thick black pencil outlines, "
         "slightly shaky sketch lines, naturally varied line weight, simple readable shapes, "
         "flat hand-colored areas with imperfect coloring, restrained rough pencil shading, "
         "choose colors naturally to match the actual subject, location, time of day and story mood; "
         "do not use a fixed palette, do not force blue/yellow/green, "
         "no polished vector finish, no photorealism, no 3D, no glossy gradients, "
         "no generated text, no letters, no numbers, no people, no stickman, "
         "leave a clear foreground area for the real mascot overlay")
CHARACTER = ("The channel mascot is a white round-headed stickman with the exact alternating green-and-white spiky mohawk, "
             "black expressive eyes and mouth, thin black stick limbs, black rounded hands and feet. "
             "The real transparent character pose is composited by the program; never generate another character.")
REFERENCE_STYLE_NOTE = ("Match the supplied style reference in medium and line quality only: casual hand-drawn colored-pencil/crayon marks, "
                       "visible scribble texture, imperfect dark outlines, uneven human-drawn strokes and simple cartoon construction. "
                       "The reference does not prescribe scene content or a fixed color palette. Choose the scene's colors from its subject and mood.")
POSE_OPTIONS = ("neutral", "friendly", "side", "back", "explain", "walk", "point", "surprised")

TOPIC_PROMPT = """คุณคือผู้คัดหัวข้อคลิปสั้นแนว "ความรู้แปลกๆ"
เลือก 1 หัวข้อในหมวด: __NICHE__ (ต้องอยู่ในหมวดนี้เท่านั้น)
เงื่อนไข:
- ต้องมีบทความภาษาอังกฤษใน Wikipedia ที่ตรงตัวกับหัวข้อนี้ และบทความต้องยาวพอมีรายละเอียด
- เป็นเรื่องเฉพาะเจาะจงที่คนส่วนใหญ่ไม่รู้หรือขัดความเชื่อเดิม ไม่ใช่เรื่องดังที่ใครๆ ก็เล่า
- เลี่ยง การเมือง ศาสนา คำแนะนำทางการแพทย์ ความรุนแรงโหดร้าย เรื่องที่พาดพิงบุคคลจริงในทางเสียหาย
- ห้ามซ้ำหรือใกล้เคียงหัวข้อเหล่านี้ (รวมถึงเรื่องเดียวกันที่ตั้งชื่อต่างกัน):
__PAST__
ตอบ JSON ล้วนๆ ไม่มี markdown รูปแบบ:
{"wiki_title":"ชื่อบทความภาษาอังกฤษใน Wikipedia ให้ตรงตัวที่สุด"}"""

WRITER = """คุณคือนักเขียนบทคลิปสั้นภาษาไทยแนว "ความรู้แปลกๆ" สำหรับวิดีโอแนวนอน 16:9
ด้านล่างคือเนื้อหาบทความ Wikipedia หัวข้อ: __TITLE__
กฎเหล็ก: ใช้ข้อเท็จจริง ตัวเลข และปี จากบทความนี้เท่านั้น ห้ามเติมข้อมูลจากความจำหรือจากที่อื่น
ถ้าบทความบอกว่ายังถกเถียงหรือไม่แน่ชัด ให้พูดว่า "นักวิทยาศาสตร์เชื่อว่า" หรือ "มีหลักฐานชี้ว่า" ข้อที่บทความไม่ยืนยันให้ตัดทิ้ง
เลือกมุมที่น่าทึ่งที่สุดของเรื่องนี้ แล้วเขียนบททำตามลำดับ:
1) คิดประโยคฮุกหลายแบบ (ไม่เกิน 12 คำ) แล้วเลือกแบบที่แรงที่สุดแบบเดียว
   รูปแบบที่ใช้ได้: คำถามที่ขัดความเชื่อ / ข้อเท็จจริงที่ฟังดูเป็นไปไม่ได้ / ผลลัพธ์ที่น่าตกใจ
   ฮุกต้องเป็นสัญญาที่คลิปเฉลยครบ ห้ามหลอกให้รอแล้วไม่เฉลย
โครงเรื่อง: ฉากแรกคือฮุก เข้าเรื่องทันที ไม่ทักทาย
→ ฉากกลางเฉลยทีละชั้นแบบเหตุ→ผล (ฉากที่ 2-3 ต้องมีข้อมูลใหม่หรือหักมุม)
→ ไคลแมกซ์ → ฉากสรุป 1 ประโยค
→ ฉากปิด (ไม่เกิน 2 ประโยค ชวนกดติดตามพร้อมเหตุผลที่เกี่ยวกับเรื่องที่เพิ่งเล่า และชวนคอมเมนต์)
กฎ "ครบแล้วจบ": อธิบายจนคนไม่มีพื้นฐานเข้าใจ นิยามคำยากก่อนใช้ ตอบคำถามฮุกให้ครบ ห้ามประโยคเติมหรือซ้ำ
ภาษาพูดธรรมชาติ ห้ามอีโมจิ เขียนตัวเลข หน่วย และคำอังกฤษเป็นคำอ่านไทยทั้งหมด (เช่น "สามดวง", "กิโลเมตร", "ดีเอ็นเอ", "เปอร์เซ็นต์")
บทพูดห้ามมีสัญลักษณ์ วงเล็บ หรือเครื่องหมายคำพูด เพราะระบบเสียงอ่านจะเพี้ยน
จำนวนฉาก 8-14 ฉาก บทพูดแต่ละฉากยาวราว 50-90 ตัวอักษร บทพูดรวมทั้งคลิปยาวราว 700-1,100 ตัวอักษร (ประมาณ 45-80 วินาที) แต่ละฉากต้องเป็นประโยคที่จบสมบูรณ์ในตัวเอง เพื่อให้เสียงเว้นจังหวะระหว่างฉาก
ถ้าหัวข้อใหญ่เกินกว่าจะจบใน 14 ฉาก ให้เล่าเฉพาะตอนที่ 1 แล้วใส่ part_note
image_prompt เขียนเป็นภาษาอังกฤษ บรรยายฉากหลัง สถานที่ วัตถุ การกระทำ และองค์ประกอบภาพให้ตรงกับบทฉากนั้นเท่านั้น ไม่ต้องบรรยายตัวละครหรือสไตล์ภาพ เพราะระบบวางตัวละครจริงและเติมสไตล์มาตรฐานให้อัตโนมัติ สีต้องเลือกตามเนื้อหาและบรรยากาศ ห้ามใช้ชุดสีตายตัว
pose เลือกหนึ่งค่าให้ตรงกับการกระทำ: neutral, friendly, side, back, explain, walk, point, surprised
image_text ใส่ข้อความภาษาไทยสั้นๆ ที่ควรปรากฏเป็นส่วนหนึ่งของภาพเฉพาะฉากที่จำเป็นเท่านั้น ถ้าไม่จำเป็นให้เป็นสตริงว่าง ห้ามใส่คำบรรยายหรือประโยคยาว
แต่ละฉากต้องเขียนให้ครบในตัว (ระบุสถานที่ วัตถุ การกระทำ) เพราะภาพแต่ละฉากถูกสร้างแยกกัน
ฉากแรกให้เป็นภาพ action ดึงสายตา
ห้ามมีตัวหนังสือ ตัวเลขในภาพ และห้ามใส่วัตถุที่มักมีตัวหนัง เช่น ป้าย กราฟ แผนภูมิ หนังสือ หนังสือพิมพ์ จอคอมพิวเตอร์ ฉลาก ให้ใช้ภาพเปรียบเทียบแทน
ชื่อคลิป (title) ต้องสั้น ภาษาไทย และระบุหัวข้อจริงชัดเจน (เช่น ชื่อสัตว์ ชื่อปรากฏการณ์) ห้ามตั้งชื่อกำกวม
ทุกฉากต้องมีตัวละครสติกแมนประจำช่องอยู่ในภาพ ระบบจะวางภาพตัวละครจริงจาก Character Reference ทับภายหลัง ให้ image_prompt บรรยายฉากหลังและวัตถุสำคัญเท่านั้น
ห้ามเริ่มสองฉากติดกันด้วยคำเชื่อมซ้ำ เช่น แล้ว, ดังนั้น, และ
ฉากสรุปต้องเป็นประโยคที่คนจำได้ และห้ามพูดซ้ำคำที่ใช้ในฉากฮุก
ห้ามใส่เครื่องหมาย " ภายในข้อความใดๆ ใน JSON
ตอบเป็น JSON ล้วนๆ ไม่มี markdown รูปแบบ:
{"title":"ชื่อคลิปสั้นๆ ภาษาไทย","part_note":"","scenes":[{"narration":"บทพูด","image_prompt":"English scene","pose":"explain","image_text":"ข้อความสั้นหรือสตริงว่าง"}]}

เนื้อหาบทความ:
__ARTICLE__"""

warnings = []
usage = {}  # โมเดล -> {ผลลัพธ์: จำนวนคำขอ} สำหรับสรุปใน notes.md (ไม่มี API Key)
os.makedirs("work", exist_ok=True)


def count_usage(model, kind):
    d = usage.setdefault(model, {})
    d[kind] = d.get(kind, 0) + 1


def usage_lines():
    names = {"ok": "สำเร็จ", "429": "429 โควตาเต็ม", "5xx": "5xx", "4xx": "4xx อื่นๆ", "conn": "เชื่อมต่อไม่ได้"}
    if not usage:
        return ["- ไม่มีการเรียก Gemini"]
    out = []
    for m, d in usage.items():
        detail = ", ".join(f"{names[k]} {d[k]}" for k in names if k in d)
        out.append(f"- {m}: ส่งคำขอ {sum(d.values())} ครั้ง ({detail})")
    return out


class QuotaError(Exception):
    pass


def log(m):
    print(m, flush=True)


def run(cmd):
    subprocess.run(cmd, check=True)


def call(model, body, wait=True):
    # ลองซ้ำ 1 ครั้งเฉพาะ 5xx หรือเน็ตหลุด ส่วน 429 หยุดทันที ไม่ยิงซ้ำ
    # wait=False: มีรุ่นสำรองรออยู่ ถ้า 5xx ให้คืนค่าทันที ไม่ต้องรอ 20 วินาที
    for attempt in (1, 2):
        try:
            r = requests.post(API + model + ":generateContent",
                              headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
                              json=body, timeout=(15, 120))
        except requests.RequestException as e:
            log(f"  [API {model}] เชื่อมต่อไม่ได้: {e}")
            count_usage(model, "conn")
            r = None
        if r is not None:
            if r.status_code == 200:
                count_usage(model, "ok")
                return r.json()
            if r.status_code == 429:
                count_usage(model, "429")
                log(f"  [API {model}] 429 โควตาเต็ม")
                raise QuotaError(model)
            count_usage(model, "5xx" if r.status_code >= 500 else "4xx")
            log(f"  [API {model}] {r.status_code}: {r.text[:300]}")
            if r.status_code < 500:
                return None
        if attempt == 1 and not wait:
            return None
        if attempt == 1:
            log("  รอ 20 วินาทีแล้วลองอีกครั้งเดียว")
            time.sleep(20)
    return None


def ask_json(prompt, model=TEXT_MODEL, wait=True):
    resp = call(model, {"contents": [{"parts": [{"text": prompt}]}],
                             "generationConfig": {"responseMimeType": "application/json"}}, wait=wait)
    if not resp:
        return None
    try:
        cand = resp["candidates"][0]
        text = "".join(p.get("text", "") for p in cand["content"]["parts"])
        try:
            data = json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, re.S)
            data = json.loads(m.group(0)) if m else None
        return data if isinstance(data, dict) else None
    except Exception as e:
        log(f"  แกะคำตอบไม่ได้: {e}")
        return None


def ask_topic(prompt):
    # ถ้าเจอ 429 ให้หยุดทั้งงานทันที ไม่ลองโมเดลอื่นเพื่อหลีกเลี่ยงการใช้โควตาต่อ
    for tm in (TOPIC_MODEL, TEXT_MODEL):
        data = ask_json(prompt, tm, wait=(tm == TEXT_MODEL))
        if data:
            return data
        log(f"  {tm} ไม่ได้คำตอบ ลองรุ่นถัดไป")
    return None
def wiki_get(params):
    for attempt in (1, 2, 3):
        try:
            r = requests.get(WIKI_API, params={**params, "format": "json"}, headers=WIKI_HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == 3:
                raise
            log(f"  Wikipedia ตอบไม่ได้ ({e}) ลองใหม่")
            time.sleep(3 * attempt)


def fetch_article(title):
    d = wiki_get({"action": "query", "prop": "extracts|info", "explaintext": 1,
                  "redirects": 1, "inprop": "url", "titles": title})
    for p in d.get("query", {}).get("pages", {}).values():
        if "missing" in p or not p.get("extract"):
            continue
        text = p["extract"]
        if re.search(r"may refer to|disambiguation", text[:400], re.I):
            continue  # หน้าแก้ความกำกวม ใช้ไม่ได้
        cut = re.search(r"\n== ?(References|See also|External links|Notes|Further reading|Bibliography|Sources) ?==", text)
        if cut:
            text = text[:cut.start()]
        return p["title"], p.get("fullurl") or ("https://en.wikipedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_"))), text[:ARTICLE_MAX].strip()
    return None


def _norm_title(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def similar_title(want, got):
    a, b = _norm_title(want), _norm_title(got)
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = set(a.split()), set(b.split())
    jaccard = len(ta & tb) / len(ta | tb)
    return jaccard >= 0.5 or difflib.SequenceMatcher(None, a, b).ratio() >= 0.65


def find_article(title):
    try:
        art = fetch_article(title)
        if art and len(art[2]) >= ARTICLE_MIN:
            return art
        d = wiki_get({"action": "query", "list": "search", "srsearch": title, "srlimit": 5})
        for h in d.get("query", {}).get("search", []):
            if not similar_title(title, h["title"]):
                log(f"  ผลค้นหา '{h['title']}' ไม่ตรงกับหัวข้อ '{title}' ข้าม")
                continue
            art = fetch_article(h["title"])
            if art and len(art[2]) >= ARTICLE_MIN:
                return art
    except Exception as e:
        log(f"  ดึง Wikipedia ไม่สำเร็จ: {e}")
    return None


# เกณฑ์บังคับ (กว้าง) กันบทเสียรูป/ระบบพัง ส่วนช่วงที่ตั้งใจ (8-14 ฉาก, 700-1,100 ตัวอักษร) เป็นแค่คำเตือน
HARD_SCENES = (4, 18)
HARD_CHARS = (300, 1800)
SOFT_SCENES = (8, 14)
SOFT_CHARS = (700, 1100)


def _total_chars(d):
    return sum(len(re.sub(r"\s", "", s["narration"])) for s in d["scenes"])


def valid(d):
    try:
        sc = d["scenes"]
        total = _total_chars(d)
        return (isinstance(d["title"], str) and bool(d["title"].strip())
                and isinstance(sc, list)
                and HARD_SCENES[0] <= len(sc) <= HARD_SCENES[1]
                and all(isinstance(s.get("narration"), str) and s["narration"].strip()
                        and isinstance(s.get("image_prompt"), str) and s["image_prompt"].strip()
                        and (s.get("pose") is None or s.get("pose") in POSE_OPTIONS)
                        and (s.get("image_text") is None or (isinstance(s.get("image_text"), str) and len(s.get("image_text")) <= 48))
                        for s in sc)
                and HARD_CHARS[0] <= total <= HARD_CHARS[1])
    except Exception:
        return False


def soft_notes(d):
    # ผ่านเกณฑ์บังคับแล้ว แต่ออกนอกช่วงที่ตั้งใจ -> แค่เตือนใน notes.md ไม่ปฏิเสธบท
    out = []
    n, total = len(d["scenes"]), _total_chars(d)
    if not SOFT_SCENES[0] <= n <= SOFT_SCENES[1]:
        out.append(f"จำนวนฉาก {n} อยู่นอกช่วงที่ตั้งใจ ({SOFT_SCENES[0]}-{SOFT_SCENES[1]} ฉาก)")
    if not SOFT_CHARS[0] <= total <= SOFT_CHARS[1]:
        out.append(f"บทพากย์ {total} ตัวอักษร อยู่นอกช่วงที่ตั้งใจ ({SOFT_CHARS[0]}-{SOFT_CHARS[1]})")
    return out


def get_script():
    past = ""
    if os.path.exists("past_titles.txt"):
        lines = [x.strip() for x in open("past_titles.txt", encoding="utf-8").read().splitlines() if x.strip()]
        past = "\n".join(lines[:PAST_LIMIT])
    log(f"[หมวดรอบนี้] {NICHE}")
    avoid = []
    art = None
    try:
        for n in range(1, TOPIC_TRIES + 1):
            log(f"[ขั้น 1] เลือกหัวข้อ รอบที่ {n}/{TOPIC_TRIES}")
            past_txt = (past + "\n" + "\n".join(avoid)).strip() or "(ยังไม่มี)"
            data = ask_topic(TOPIC_PROMPT.replace("__NICHE__", NICHE).replace("__PAST__", past_txt))
            wt = (data or {}).get("wiki_title", "")
            if not isinstance(wt, str) or not wt.strip():
                log("  ไม่ได้ชื่อบทความ")
                continue
            log(f"  เสนอหัวข้อ: {wt}")
            art = find_article(wt.strip())
            if art:
                break
            log("  หา/ดึงบทความ Wikipedia ที่ยาวพอไม่ได้ ลองหัวข้ออื่น")
            avoid.append(wt.strip())
        if not art:
            sys.exit("เลือกหัวข้อไม่สำเร็จ: ไม่พบบทความ Wikipedia ที่ใช้ได้ ลองกดรันใหม่")
        title_en, url, text = art
        log(f"[ขั้น 2] เขียนบทจากบทความ: {title_en} ({len(text)} ตัวอักษร)")
        prompt = (WRITER.replace("__TITLE__", title_en).replace("__ARTICLE__", text))
        data = None
        for w, wm in enumerate(WRITER_MODELS, 1):
            last = (w == len(WRITER_MODELS))
            log(f"  เขียนบทครั้งที่ {w}/{len(WRITER_MODELS)} ด้วย {wm}")
            try:
                data = ask_json(prompt, wm, wait=last)
            except QuotaError:
                # 429 คือสัญญาณให้หยุด ไม่ยิงโมเดลสำรองต่อ
                raise
            if data and valid(data):
                warnings.extend(soft_notes(data))
                if wm != TEXT_MODEL:
                    warnings.append(f"บทเขียนด้วย {wm} (รุ่นสำรอง เพราะ {TEXT_MODEL} ใช้ไม่ได้หรือบทไม่ผ่านเกณฑ์) ตรวจภาษาและข้อเท็จจริงให้ละเอียด")
                break
            log("  ไม่ได้บท หรือบทผิดเกณฑ์" + ("" if last else " ลองรุ่นถัดไป"))
            data = None
    except QuotaError:
        sys.exit("โควตา Gemini เต็ม (429) รอรีเซ็ตแล้วค่อยกดรันใหม่ ถ้าเกิดตั้งแต่ครั้งแรกของวัน ให้เช็กหน้า aistudio.google.com/rate-limit")
    if not data:
        sys.exit("เขียนบทไม่สำเร็จ: ทุกรุ่นไม่ตอบ (503) หรือบทผิดเกณฑ์ รอสักพักแล้วกดรันใหม่")
    if not valid(data):
        sys.exit("เขียนบทไม่สำเร็จ: โครงสร้างหรือความยาวบทผิดเกณฑ์ ลองกดรันใหม่")
    log(f"  ได้หัวข้อ: {data['title']} ({len(data['scenes'])} ฉาก)")
    return data, [{"title": "Wikipedia: " + title_en, "uri": url}]
def audio_duration(wav):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", wav])
    return float(out.strip())


def find_silences(wav):
    r = subprocess.run(["ffmpeg", "-i", wav, "-af", "silencedetect=noise=-35dB:d=0.12",
                        "-f", "null", "-"], capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return [(s + e) / 2 for s, e in zip(starts, ends)]


def snap_durations(durs, total, wav, window=1.0):
    try:
        mids = find_silences(wav)
        bounds, acc = [], 0.0
        for d in durs[:-1]:
            acc += d
            near = [m for m in mids if abs(m - acc) <= window]
            bounds.append(min(near, key=lambda m: abs(m - acc)) if near else acc)
        edges = [0.0] + bounds + [total]
        out = [edges[i + 1] - edges[i] for i in range(len(durs))]
        if all(x > 0.8 for x in out):
            return out
    except Exception as e:
        log(f"  จัดจังหวะฉากไม่สำเร็จ ใช้เวลาแบบสัดส่วนตัวอักษร: {e}")
    return durs


def tts_gemini(text, model, wav):
    # Keep transcript verbatim; pass delivery direction as metadata so it is not spoken aloud.
    body = {"contents": [{"parts": [{"text": text, "speechMetadata": {"style": TTS_STYLE}}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    resp = call(model, body)
    if not resp:
        return False
    try:
        part = resp["candidates"][0]["content"]["parts"][0]
        inline = part.get("inlineData") or part.get("inline_data")
        if not inline or not inline.get("data"):
            raise ValueError("ไม่พบข้อมูลเสียง inlineData")
        audio_bytes = base64.b64decode(inline["data"], validate=True)
        mime = (inline.get("mimeType") or inline.get("mime_type") or "").lower()
        raw_path = "work/voice_audio.bin"
        with open(raw_path, "wb") as f:
            f.write(audio_bytes)
        rate = 24000
        m_rate = re.search(r"rate=(\d{4,6})", mime)
        if m_rate:
            rate = int(m_rate.group(1))
        if audio_bytes[:4] == b"RIFF" or "wav" in mime:
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw_path, "-ar", "24000", "-ac", "1", wav])
        else:
            run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(rate), "-ac", "1",
                 "-i", raw_path, "-ar", "24000", wav])
        if not os.path.exists(wav) or os.path.getsize(wav) < 1000:
            raise ValueError("ไฟล์เสียงที่แปลงได้ว่างหรือเล็กผิดปกติ")
        return True
    except Exception as e:
        log(f"  แปลงเสียงไม่สำเร็จ: {e}")
        return False


def tts_edge(text, wav):
    open("work/voice.txt", "w", encoding="utf-8").write(text)
    run(["edge-tts", "--voice", EDGE_VOICE, "--file", "work/voice.txt", "--write-media", "work/voice.mp3"])
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", "work/voice.mp3", "-ar", "24000", "-ac", "1", wav])


def make_voice(scenes):
    text = "\n".join(s["narration"].strip() for s in scenes)
    wav = "work/voice.wav"
    reasons = []
    for index, m in enumerate(TTS_MODELS):
        role = "ตัวหลัก" if index == 0 else "Gemini ตัวสำรอง"
        log(f"[ขั้น 3b] สร้างเสียงทั้งคลิปด้วย {m} ({role}, เสียง {VOICE})")
        try:
            if tts_gemini(text, m, wav):
                if reasons:
                    warnings.append(f"เสียงพากย์ใช้ {m} ({'; '.join(reasons)})")
                return wav
            reasons.append(f"{m} ล้มเหลว")
        except QuotaError:
            # ไม่ใช้ TTS รุ่นอื่นหรือบริการสำรองต่อเมื่อผู้ให้บริการแจ้งโควตาเต็ม
            raise
        except Exception as e:
            log(f"  ผิดพลาด: {e}")
            reasons.append(f"{m} ผิดพลาด")
    log("[ขั้น 3b] Gemini ทั้งสองรุ่นไม่สำเร็จ จึงใช้ Edge TTS (ตัวสำรองสุดท้าย)")
    warnings.append(f"เสียงพากย์ใช้ Edge TTS / {EDGE_VOICE} ({'; '.join(reasons)})")
    tts_edge(text, wav)
    return wav

IMG_BUDGET = 25 * 60  # เกินงบเวลาให้หยุด ไม่ใช้ภาพฉากอื่นแทน
IMG_GAP = 50  # วินาทีระหว่างคำขอภาพแต่ละครั้ง (Pollinations ฟรีกำหนดอย่างน้อย 45 วินาทีต่อ IP)
try:
    CROP_BOTTOM = max(0.0, min(15.0, float(os.environ.get("CROP_BOTTOM", "0") or 0))) / 100
except ValueError:
    CROP_BOTTOM = 0.0  # ตัดขอบล่างของภาพกี่เปอร์เซ็นต์ (กรณีมีลายน้ำมุมล่าง)


class ImageBlocked(Exception):
    pass


_img_not_before = 0.0


def img_get(url, timeout):
    # ทุกคำขอภาพผ่านตัวควบคุมช่วงห่าง; 402/403/429 จะหยุดทันทีที่ caller
    global _img_not_before
    wait = _img_not_before - time.time()
    if wait > 0:
        log(f"  รอ {wait:.0f} วินาที (จำกัดช่วงห่างคำขอภาพ)")
        time.sleep(wait)
    _img_not_before = time.time() + IMG_GAP
    r = requests.get(url, timeout=timeout)
    return r


def infer_pose(scene, scene_index=0):
    """Choose one of the supplied full-body poses from scene action/narration."""
    requested = scene.get("pose") if isinstance(scene, dict) else None
    if requested in POSE_OPTIONS:
        return requested
    text = " ".join(str(scene.get(k, "")) for k in ("narration", "image_prompt")) if isinstance(scene, dict) else str(scene)
    if any(k in text for k in ("ตกใจ", "ช็อก", "กลัว", "惊", "surpris", "shocked", "afraid", "scared")):
        return "surprised"
    if any(k in text for k in ("ชี้", "ชี้ให้ดู", "point", "indicate")):
        return "point"
    if any(k in text for k in ("วิ่ง", "เดิน", "หนี", "วิ่งหนี", "walk", "run", "escape")):
        return "walk"
    if any(k in text for k in ("ด้านหลัง", "หันหลัง", "มองออกไป", "back view", "from behind")):
        return "back"
    if any(k in text for k in ("ด้านข้าง", "หันข้าง", "side view", "profile")):
        return "side"
    if any(k in text for k in ("อธิบาย", "แสดงให้เห็น", "นำเสนอ", "explain", "present")):
        return "explain"
    if any(k in text for k in ("ยิ้ม", "ดีใจ", "ทักทาย", "ยินดี", "happy", "welcome")):
        return "friendly"
    return "neutral"


def _pose_path(pose):
    pose = pose if pose in POSE_OPTIONS else "neutral"
    pose_index = {"neutral": 1, "friendly": 5, "side": 3, "back": 4,
                  "explain": 5, "walk": 6, "point": 7, "surprised": 8}[pose]
    path = os.path.join(ASSET_DIR, "characters", f"pose_{pose_index}.png")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"ไม่พบ Character Reference pose: {path}")
    return path


def render_image_text(image_path, text):
    """Render optional Thai words as artwork, never as subtitles."""
    text = (text or "").strip()
    if not text:
        return
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        raise RuntimeError("ต้องติดตั้ง Pillow เพื่อวางข้อความภาษาไทยในภาพ") from e
    image = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(image)
    font_candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansThai-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansThai-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    font_path = next((f for f in font_candidates if os.path.isfile(f)), None)
    if not font_path:
        raise RuntimeError("ไม่พบฟอนต์ที่รองรับภาษาไทยสำหรับข้อความในภาพ")
    try:
        font = ImageFont.truetype(font_path, 64, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        font = ImageFont.truetype(font_path, 64)
    # วางมุมบนซ้ายในพื้นที่ปลอดภัย จำกัดไม่ให้ทับขอบภาพ
    max_width = 760
    lines, line = [], ""
    # Thai often has no spaces; wrap by grapheme-like clusters so marks stay with their base.
    clusters, i = [], 0
    while i < len(text):
        cluster = text[i]
        if cluster in "เแโใไ" and i + 1 < len(text):
            cluster += text[i + 1]; i += 2
        else:
            i += 1
        while i < len(text) and unicodedata.category(text[i]).startswith("M"):
            cluster += text[i]; i += 1
        clusters.append(cluster)
    for cluster in clusters:
        candidate = line + cluster
        if line and draw.textbbox((0, 0), candidate, font=font, stroke_width=3)[2] > max_width:
            lines.append(line); line = cluster
        else:
            line = candidate
    if line: lines.append(line)
    if len(lines) > 2:
        lines = lines[:2]
    y = 72
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=5)
        w = bbox[2] - bbox[0]
        x = max(55, (image.width - w) // 2)
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255),
                  stroke_width=7, stroke_fill=(20, 20, 20, 255))
        y += 88
    tmp = image_path + ".text.tmp.jpg"
    image.convert("RGB").save(tmp, format="JPEG", quality=95, optimize=True)
    os.replace(tmp, image_path)


def compose_character(background_path, output_path, scene_index, scene=None):
    """Overlay the supplied transparent mascot pose; placement alternates to suit wide scenes."""
    scene = scene or {}
    pose = _pose_path(infer_pose(scene, scene_index))
    composed = output_path + ".composed.jpg"
    # Vary side and size across shots so the mascot does not occupy the same fixed position.
    side = "left" if scene_index % 2 == 0 else "right"
    x_expr = "120" if side == "left" else "W-w-120"
    height = 660 if scene_index % 3 else 720
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", background_path, "-i", pose,
         "-filter_complex", f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080[bg];"
                           f"[1:v]scale=-1:{height}[mascot];[bg][mascot]overlay=x={x_expr}:y=H-h-45:format=auto,format=yuvj444p[out]",
         "-map", "[out]", "-frames:v", "1", composed])
    os.replace(composed, output_path)
    render_image_text(output_path, scene.get("image_text", ""))


def make_image(prompt, path, base_seed, scene_index=0, scene=None):
    reserved_side = "left" if scene_index % 2 == 0 else "right"
    layout_note = f"Keep the {reserved_side} foreground visually uncluttered for the mascot; place the main story subject toward the opposite side."
    full = f"{STYLE}, {REFERENCE_STYLE_NOTE}, {layout_note}, background scene: {prompt}"
    for stale in (path, path + ".ok", path + ".meta.json", path + ".meta.json.tmp", path + ".part.jpg"):
        try: os.remove(stale)
        except FileNotFoundError: pass
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(full) +
           f"?width=1280&height=720&model=flux&nologo=true&seed={base_seed}")
    for t in range(1, 3):
        try:
            r = img_get(url, 90)
            if r.status_code in (402, 403, 429):
                raise ImageBlocked(f"HTTP {r.status_code}: บริการจำกัดหรือปฏิเสธการใช้ หยุดทันทีโดยไม่ลองซ้ำ")
            if (r.status_code == 200 and r.headers.get("content-type", "").startswith("image") and len(r.content) > 5000):
                raw = path + ".part.jpg"
                with open(raw, "wb") as f: f.write(r.content)
                compose_character(raw, path, scene_index, scene)
                os.remove(raw)
                probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height", "-of", "json", path], capture_output=True, text=True)
                streams = json.loads(probe.stdout).get("streams", []) if probe.returncode == 0 else []
                if not streams or (int(streams[0].get("width", 0)), int(streams[0].get("height", 0))) != (1920, 1080):
                    raise ValueError("ภาพประกอบตัวละครไม่ใช่ 1920x1080")
                decode = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-frames:v", "1", "-f", "null", "-"], capture_output=True, text=True)
                if decode.returncode != 0: raise ValueError("FFmpeg ถอดรหัสภาพไม่สำเร็จ")
                with open(path + ".ok", "w", encoding="utf-8") as f: f.write("1")
                write_image_cache_metadata(path, scene, base_seed, scene_index)
                return True
            log(f"  ภาพลองที่ {t} ล้ม: HTTP {r.status_code}")
        except ImageBlocked: raise
        except (requests.RequestException, OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError, RuntimeError) as e:
            log(f"  ภาพลองที่ {t} ล้ม: {e}")
    for stale in (path, path + ".ok", path + ".meta.json", path + ".part.jpg"):
        try: os.remove(stale)
        except FileNotFoundError: pass
    return False


def preflight_image():
    # Deliberately offline: do not consume a real image-generation request as a health check.
    log("  ข้ามการสร้างภาพทดสอบออนไลน์ เพื่อไม่เสียคำขอภาพก่อนเริ่มงานจริง")
    return True

def make_clip(img, dur, i, out):
    frames = max(1, round(dur * FPS))
    step = 0.18 / frames
    if i % 2 == 0:
        z = f"min(zoom+{step:.6f},1.18)"
    else:
        z = f"if(eq(on,1),1.18,max(zoom-{step:.6f},1.0))"
    pre = f"crop=iw:ih*{1 - CROP_BOTTOM:.4f}:0:0," if CROP_BOTTOM > 0 else ""
    vf = (pre + "scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160,"
          f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1920x1080:fps={FPS},"
          "setparams=range=tv,format=yuv420p")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", img, "-vf", vf, "-frames:v", str(frames),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-color_range", "tv", "-r", str(FPS), out])


CKPT = "checkpoint.json"
CKPT_MAX_AGE = 12 * 3600  # วินาที


def scene_fingerprint(scene, clip_seed, scene_index=0):
    """Stable identity for the exact image prompt + style + seed."""
    ref_hashes = {}
    ref_names = [os.path.join(ASSET_DIR, "character_reference.png"), os.path.join(ASSET_DIR, "background_style_reference.png")] + [
        os.path.join(ASSET_DIR, "characters", f"pose_{i}.png") for i in range(1, 9)]
    for ref_name in ref_names:
        if os.path.isfile(ref_name):
            ref_hashes[ref_name] = image_sha256(ref_name)
    payload = json.dumps(
        {"scene": scene, "seed": clip_seed, "style": STYLE, "character": CHARACTER,
         "scene_index": scene_index, "layout": "1920x1080", "ref_version": 3, "references": ref_hashes},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def image_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def image_cache_valid(path, scene, clip_seed, scene_index=0):
    """Reuse only a complete image whose bytes and scene identity still match."""
    meta_path = path + ".meta.json"
    try:
        if not (os.path.isfile(path) and os.path.getsize(path) > 5000
                and os.path.isfile(path + ".ok") and os.path.isfile(meta_path)):
            return False
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("version") != 3:
            return False
        if meta.get("fingerprint") != scene_fingerprint(scene, clip_seed, scene_index):
            return False
        if meta.get("size") != os.path.getsize(path):
            return False
        if meta.get("sha256") != image_sha256(path):
            return False
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "json", path],
            capture_output=True, text=True, check=True
        )
        streams = json.loads(probe.stdout).get("streams", [])
        if not (streams and int(streams[0].get("width", 0)) == 1920
                and int(streams[0].get("height", 0)) == 1080):
            return False
        decode = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", path, "-frames:v", "1", "-f", "null", "-"],
            capture_output=True, text=True
        )
        return decode.returncode == 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, json.JSONDecodeError):
        return False


def write_image_cache_metadata(path, scene, clip_seed, scene_index=0):
    meta = {
        "version": 3,
        "fingerprint": scene_fingerprint(scene, clip_seed, scene_index),
        "sha256": image_sha256(path),
        "size": os.path.getsize(path),
    }
    tmp = path + ".meta.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path + ".meta.json")


def save_checkpoint(script, srcs, clip_seed):
    try:
        tmp = CKPT + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "created": time.time(), "niche": NICHE, "script": script,
                       "sources": srcs, "clip_seed": clip_seed, "warnings": list(warnings)},
                      f, ensure_ascii=False)
        os.replace(tmp, CKPT)
        log("  บันทึก checkpoint ของบทแล้ว")
        return True
    except Exception as e:
        log(f"  บันทึก checkpoint ไม่สำเร็จ: {e}")
        return False


def load_checkpoint():
    # RESUME=1: ใช้บทและภาพเดิม ไม่เรียก Gemini ถ้าใช้ checkpoint ไม่ได้ให้หยุด ไม่ย้อนไปเรียก Gemini เอง
    if os.environ.get("RESUME", "").strip().lower() not in ("1", "true", "yes"):
        return None
    try:
        with open(CKPT, encoding="utf-8") as f:
            ck = json.load(f)
        age = time.time() - ck["created"]
        sources = ck.get("sources")
        if (ck.get("version") != 1 or not 0 <= age <= CKPT_MAX_AGE or not valid(ck["script"])
                or type(ck.get("clip_seed")) is not int or not isinstance(sources, list)
                or not sources or any(not isinstance(x, dict) or not isinstance(x.get("title"), str)
                                      or not x["title"].strip() or not isinstance(x.get("uri"), str)
                                      or not x["uri"].startswith("https://") for x in sources)):
            raise ValueError("checkpoint เก่าเกิน 12 ชั่วโมงหรือข้อมูลไม่ถูกต้อง")
        return ck
    except Exception as e:
        sys.exit(f"[resume] ใช้ checkpoint ไม่ได้ ({e}) หยุดเพื่อไม่ให้เรียก Gemini โดยไม่ตั้งใจ ให้รันแบบปกติ (ไม่ติ๊ก resume) หากต้องการเริ่มใหม่")


def main():
    global NICHE
    ck = load_checkpoint()
    need_img = ck is None or any(
        not image_cache_valid(f"work/img{i}.jpg", scene, ck["clip_seed"], i)
        for i, scene in enumerate(ck["script"]["scenes"])
    )
    if need_img:
        log("[ขั้น 0] เช็กบริการสร้างภาพ")
        if not preflight_image():
            sys.exit("บริการสร้างภาพ (Pollinations) ไม่ตอบหรือจำกัดการใช้ หยุดก่อนใช้โควตา Gemini รอสักพักแล้วกดรันใหม่")

    if ck:
        script, all_srcs, clip_seed = ck["script"], ck["sources"], ck["clip_seed"]
        NICHE = ck.get("niche") or NICHE
        warnings.extend(ck.get("warnings", []))
        warnings.append("ใช้บทจาก checkpoint (resume) ไม่ได้เรียก Gemini เลือกหัวข้อ/เขียนบทใหม่")
        log("[resume] ใช้บทและภาพเดิมจาก checkpoint ไม่เรียก Gemini เลือกหัวข้อ/เขียนบท")
    else:
        script, all_srcs = get_script()
        clip_seed = random.randint(1, 10**6)
        if not save_checkpoint(script, all_srcs, clip_seed):
            sys.exit("บันทึก checkpoint ไม่สำเร็จ หยุดก่อนสร้างภาพและเสียงเพื่อไม่ให้เสียโควตาซ้ำ")
    scenes = script["scenes"]
    n = len(scenes)

    # Generate or reuse only images whose hashes and scene fingerprints match.
    imgs = []
    log(f"  [seed คลิปนี้] {clip_seed}")
    t0 = time.time()
    for i, s in enumerate(scenes):
        log(f"[ขั้น 3] ภาพฉาก {i + 1}/{n}")
        img = f"work/img{i}.jpg"
        if ck and image_cache_valid(img, s, clip_seed, i):
            log("  ใช้ภาพเดิมที่ผ่านการตรวจ Hash และ Scene Fingerprint")
            ok = True
        elif time.time() - t0 > IMG_BUDGET:
            sys.exit(f"เกินงบเวลาสร้างภาพที่ฉาก {i + 1}; หยุดโดยไม่ใช้ภาพฉากอื่นแทน")
        else:
            try:
                ok = make_image(s["image_prompt"], img, clip_seed, i, s)
            except ImageBlocked as e:
                sys.exit(f"{e}; บทและภาพที่ได้แล้วถูกบันทึกเป็น checkpoint ตรวจสถานะบริการก่อน resume")
        if not ok:
            sys.exit(f"สร้างภาพฉาก {i + 1} ไม่สำเร็จ หยุดเพื่อไม่ใช้ภาพผิดฉากหรือภาพเปล่า และไม่เรียก TTS ต่อ; checkpoint ถูกเก็บไว้สำหรับ resume")
        imgs.append(img)

    try:
        wav = make_voice(scenes)
    except QuotaError:
        sys.exit("Gemini TTS ตอบ HTTP 429: หยุดทันที ไม่ลองโมเดลหรือบริการเสียงสำรอง รอรอบโควตาถัดไปแล้วค่อยรันใหม่")
    total = audio_duration(wav)
    weights = [max(1, len(re.sub(r"\s", "", s["narration"]))) for s in scenes]
    durs = [total * w / sum(weights) for w in weights]
    durs = snap_durations(durs, total, wav)
    durs[-1] += 0.4  # กันเสียงท้ายถูกตัดจากการปัดเฟรม (-shortest จะตัดวิดีโอส่วนเกินตามเสียงเอง)
    log(f"  เสียงยาว {total:.1f} วินาที")
    if total < 40 or total > 100:
        warnings.append(f"เสียงยาว {total:.0f} วินาที อยู่นอกช่วงที่ตั้งใจ (45-80 วินาที)")

    clips = []
    for i in range(n):
        log(f"[ขั้น 4] คลิปฉาก {i + 1}/{n} ({durs[i]:.1f} วินาที)")
        clip = f"work/clip{i}.mp4"
        make_clip(imgs[i], durs[i], i, clip)
        clips.append(clip)

    log("[ขั้น 5] ประกอบวิดีโอ")
    open("work/list.txt", "w").write("".join(f"file '{os.path.basename(c)}'\n" for c in clips))
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "work/list.txt",
         "-i", wav, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "output.mp4"])

    # Final media QC: fail closed rather than publish a broken MP4.
    if not os.path.exists("output.mp4") or os.path.getsize("output.mp4") < 100_000:
        sys.exit("ตรวจคุณภาพไม่ผ่าน: output.mp4 ไม่มีหรือมีขนาดเล็กผิดปกติ")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,pix_fmt,width,height,r_frame_rate,duration:format=duration",
         "-of", "json", "output.mp4"], capture_output=True, text=True, check=True)
    media = json.loads(probe.stdout)
    videos = [x for x in media.get("streams", []) if x.get("codec_type") == "video"]
    audios = [x for x in media.get("streams", []) if x.get("codec_type") == "audio"]
    if not videos or not audios:
        sys.exit("ตรวจคุณภาพไม่ผ่าน: ต้องมีทั้งภาพและเสียง")
    v = videos[0]
    if (v.get("width"), v.get("height"), v.get("r_frame_rate")) != (1920, 1080, "30/1"):
        sys.exit("ตรวจคุณภาพไม่ผ่าน: ต้องเป็น 1920x1080 / 30 FPS")
    if v.get("codec_name") != "h264" or v.get("pix_fmt") != "yuv420p":
        sys.exit("ตรวจคุณภาพไม่ผ่าน: วิดีโอต้องเป็น H.264 / yuv420p")
    if audios[0].get("codec_name") != "aac":
        sys.exit("ตรวจคุณภาพไม่ผ่าน: เสียงต้องเป็น AAC")
    duration = float(media.get("format", {}).get("duration", 0))
    if not (10 <= duration <= 175):
        sys.exit(f"ตรวจคุณภาพไม่ผ่าน: ระยะเวลา {duration:.1f}s อยู่นอกช่วง 10-175 วินาที (Shorts ไม่เกิน 3 นาที)")
    if abs(duration - total) > 1.0:
        sys.exit(f"ตรวจคุณภาพไม่ผ่าน: ความยาวคลิป {duration:.1f}s ไม่ตรงกับเสียง {total:.1f}s")
    log(f"[QC ผ่าน] 1920x1080 / 30 FPS / {duration:.1f}s / มีเสียง")

    title = script["title"].strip().replace("\n", " ")
    if script.get("part_note"):
        title += f" ({script['part_note']})"
    open("title.txt", "w", encoding="utf-8").write(title)
    lines = [f"# {title}", ""]
    lines += [f"หมวด: {NICHE}", ""]
    warnings.append("แหล่งข้อมูลมีเพียง Wikipedia หน้าเดียว ไม่ได้ตรวจซ้ำด้วย AI ต้องเปิดลิงก์เช็กเองทุกข้อ และตรวจว่าภาพไม่มีลายน้ำ")
    lines += ["## คำเตือน", *[f"- {w}" for w in warnings], ""]
    lines += ["## การเรียก Gemini (จำนวนคำขอที่ส่งจริงรอบนี้)", *usage_lines(), ""]
    lines += ["## ลิงก์แหล่งข้อมูล (เปิดเช็กก่อนอัปโหลด)"]
    lines += [f"- {s['title']}: {s['uri']}" for s in all_srcs]
    lines += ["", "เนื้อหานี้สร้างด้วย AI โปรดติดป้าย AI ตอนอัปโหลด"]
    open("notes.md", "w", encoding="utf-8").write("\n".join(lines))
    log("เสร็จ: output.mp4")


if __name__ == "__main__":
    main()
