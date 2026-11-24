import os, sys, re, json, time, base64, random, subprocess, urllib.parse
import requests

API_KEY = os.environ["GEMINI_API_KEY"]
CATEGORIES = ["ร่างกายมนุษย์", "สัตว์", "อวกาศและดาราศาสตร์", "ประวัติศาสตร์",
              "ธรรมชาติและภูมิศาสตร์", "สมองและจิตวิทยา", "มหาสมุทรและสัตว์ทะเล"]
NICHE = os.environ.get("NICHE", "").strip() or random.choice(CATEGORIES)
VOICE = os.environ.get("VOICE_NAME", "").strip() or "Enceladus"

TEXT_MODEL = "gemini-3.8-flash"          # เขียนบท (โควตาน้อย 20 ครั้ง/วัน ใช้ครั้งเดียวต่อคลิป)
TOPIC_MODEL = "gemini-3.5-flash-lite"    # เลือกหัวข้อ (โควตาแยก ถ้าใช้ไม่ได้จะถอยไปใช้ TEXT_MODEL)
TTS_MODELS = ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"]
EDGE_VOICE = "th-TH-NiwatNeural"
TTS_STYLE = "พูดภาษาไทยแบบคนเล่าเรื่องให้เพื่อนฟัง ชัดเจนทุกคำ และเว้นจังหวะก่อนข้อเท็จจริงที่น่าทึ่งที่สุด:"
API = "https://generativelanguage.googleapis.com/v1beta/models/"
FPS = 30
PAST_LIMIT = 30
TOPIC_TRIES = 2

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_HEADERS = {"User-Agent": "auto-shorts/1.0 (https://github.com/poramin-ozone-AI/auto-shorts)"}
ARTICLE_MAX = 14000
ARTICLE_MIN = 2000

STYLE = ("hand-drawn cartoon stickman style, thick black outlines, flat bright solid colors, "
         "simple clean background, vertical 9:16, absolutely no text, no letters, no numbers")
CHARACTER = ("the single main character is a white round-headed stickman with a white and green mohawk, "
             "thick black stick limbs, big expressive eyes and an exaggerated facial expression")

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

WRITER = """คุณคือนักเขียนบทคลิปสั้นแนวตั้งภาษาไทยแนว "ความรู้แปลกๆ"
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
image_prompt เขียนเป็นภาษาอังกฤษ บรรยายเฉพาะการกระทำในฉากที่อธิบายกลไกของสิ่งที่พูด ไม่ต้องเขียนสไตล์หรือรูปร่างตัวละคร
แต่ละฉากต้องเขียนให้ครบในตัว (ระบุสถานที่ วัตถุ การกระทำ) เพราะภาพแต่ละฉากถูกสร้างแยกกัน
ฉากแรกให้เป็นภาพ action ดึงสายตา
ห้ามมีตัวหนังสือ ตัวเลขในภาพ และห้ามใส่วัตถุที่มักมีตัวหนัง เช่น ป้าย กราฟ แผนภูมิ หนังสือ หนังสือพิมพ์ จอคอมพิวเตอร์ ฉลาก ให้ใช้ภาพเปรียบเทียบแทน
ชื่อคลิป (title) ต้องสั้น ภาษาไทย และระบุหัวข้อจริงชัดเจน (เช่น ชื่อสัตว์ ชื่อปรากฏการณ์) ห้ามตั้งชื่อกำกวม
ทุกฉากต้องมีตัวละครสติกแมนตัวเดียวเป็นผู้กระทำ ระบุในภาพว่าสติกแมนกำลังทำอะไรกับวัตถุไหน
ห้ามเริ่มสองฉากติดกันด้วยคำเชื่อมซ้ำ เช่น แล้ว, ดังนั้น, และ
ฉากสรุปต้องเป็นประโยคที่คนจำได้ และห้ามพูดซ้ำคำที่ใช้ในฉากฮุก
ห้ามใส่เครื่องหมาย " ภายในข้อความใดๆ ใน JSON
ตอบเป็น JSON ล้วนๆ ไม่มี markdown รูปแบบ:
{"title":"ชื่อคลิปสั้นๆ ภาษาไทย","part_note":"","scenes":[{"narration":"บทพูด","image_prompt":"English scene"}]}

เนื้อหาบทความ:
__ARTICLE__"""

warnings = []
os.makedirs("work", exist_ok=True)


class QuotaError(Exception):
    pass


def log(m):
    print(m, flush=True)


def run(cmd):
    subprocess.run(cmd, check=True)


def call(model, body):
    # ลองซ้ำ 1 ครั้งเฉพาะ 5xx หรือเน็ตหลุด ส่วน 429 หยุดทันที ไม่ยิงซ้ำ
    for attempt in (1, 2):
        try:
            r = requests.post(API + model + ":generateContent",
                              headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
                              json=body, timeout=180)
        except requests.RequestException as e:
            log(f"  [API {model}] เชื่อมต่อไม่ได้: {e}")
            r = None
        if r is not None:
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                log(f"  [API {model}] 429 โควตาเต็ม")
                raise QuotaError(model)
            log(f"  [API {model}] {r.status_code}: {r.text[:300]}")
            if r.status_code < 500:
                return None
        if attempt == 1:
            log("  รอ 20 วินาทีแล้วลองอีกครั้งเดียว")
            time.sleep(20)
    return None


def ask_json(prompt, model=TEXT_MODEL):
    resp = call(model, {"contents": [{"parts": [{"text": prompt}]}],
                             "generationConfig": {"responseMimeType": "application/json"}})
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
    # ลองรุ่นเล็ก (โควตาแยก) ก่อน แล้วค่อยถอยไปรุ่นเขียนบท ถ้าโควตาเต็มทั้งคู่ให้หยุด
    quota = 0
    for tm in (TOPIC_MODEL, TEXT_MODEL):
        try:
            data = ask_json(prompt, tm)
        except QuotaError:
            log(f"  {tm} โควตาเต็ม ลองรุ่นถัดไป")
            quota += 1
            continue
        if data:
            return data
        log(f"  {tm} ไม่ได้คำตอบ ลองรุ่นถัดไป")
    if quota == 2:
        raise QuotaError("topic")
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
        cut = re.search(r"\n== ?(References|See also|External links|Notes|Further reading|Bibliography|Sources) ?==", text)
        if cut:
            text = text[:cut.start()]
        return p["title"], p.get("fullurl") or ("https://en.wikipedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_"))), text[:ARTICLE_MAX].strip()
    return None


def find_article(title):
    try:
        art = fetch_article(title)
        if art and len(art[2]) >= ARTICLE_MIN:
            return art
        d = wiki_get({"action": "query", "list": "search", "srsearch": title, "srlimit": 1})
        hits = d.get("query", {}).get("search", [])
        if hits:
            art = fetch_article(hits[0]["title"])
            if art and len(art[2]) >= ARTICLE_MIN:
                return art
    except Exception as e:
        log(f"  ดึง Wikipedia ไม่สำเร็จ: {e}")
    return None


def valid(d):
    try:
        sc = d["scenes"]
        total = sum(len(re.sub(r"\s", "", s["narration"])) for s in sc)
        return (isinstance(d["title"], str) and d["title"].strip() and 6 <= len(sc) <= 14
                and all(s["narration"].strip() and s["image_prompt"].strip() for s in sc)
                and 500 <= total <= 1400)
    except Exception:
        return False


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
        for w in (1, 2):  # ลองเขียนซ้ำได้ 1 ครั้ง เฉพาะกรณีได้บทที่ผิดเกณฑ์ (ไม่ใช่ 429)
            data = ask_json(prompt)
            if data and valid(data):
                break
            log(f"  บทรอบที่ {w} ผิดเกณฑ์หรือแกะไม่ได้" + (" ลองเขียนใหม่" if w == 1 else ""))
    except QuotaError:
        sys.exit("โควตา Gemini เต็ม (429) รอรีเซ็ตแล้วค่อยกดรันใหม่ ถ้าเกิดตั้งแต่ครั้งแรกของวัน ให้เช็กหน้า aistudio.google.com/rate-limit")
    if not data:
        sys.exit("เขียนบทไม่สำเร็จ: ไม่ได้รับ JSON ที่แกะได้ ลองกดรันใหม่")
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
    body = {"contents": [{"parts": [{"text": TTS_STYLE + "\n" + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    resp = call(model, body)
    if not resp:
        return False
    try:
        part = resp["candidates"][0]["content"]["parts"][0]
        b64 = (part.get("inlineData") or part["inline_data"])["data"]
        open("work/voice.pcm", "wb").write(base64.b64decode(b64))
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", "24000", "-ac", "1",
             "-i", "work/voice.pcm", wav])
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
    for m in TTS_MODELS:
        log(f"[ขั้น 3b] สร้างเสียงทั้งคลิปด้วย {m} (เสียง {VOICE})")
        try:
            if tts_gemini(text, m, wav):
                if reasons:
                    warnings.append(f"เสียงพากย์ใช้ {m} ({'; '.join(reasons)})")
                return wav
            reasons.append(f"{m} ล้มเหลว")
        except QuotaError:
            reasons.append(f"{m} โควตาเต็ม")
        except Exception as e:
            log(f"  ผิดพลาด: {e}")
            reasons.append(f"{m} ผิดพลาด")
    log("[ขั้น 3b] ถอยไปใช้ edge-tts")
    warnings.append(f"เสียงพากย์ใช้ edge-tts ({'; '.join(reasons)})")
    tts_edge(text, wav)
    return wav


IMG_BUDGET = 18 * 60  # วินาที เกินนี้ฉากที่เหลือใช้ภาพก่อนหน้า
try:
    CROP_BOTTOM = max(0.0, min(15.0, float(os.environ.get("CROP_BOTTOM", "0") or 0))) / 100
except ValueError:
    CROP_BOTTOM = 0.0  # ตัดขอบล่างของภาพกี่เปอร์เซ็นต์ (กรณีมีลายน้ำมุมล่าง)


def solid_image(path):
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0xFFE066:s=1080x1920",
         "-frames:v", "1", "-pix_fmt", "yuvj420p", path])


def make_image(prompt, path, base_seed):
    full = f"{STYLE}, {CHARACTER}, {prompt}"
    for t in range(1, 3):
        seed = base_seed if t == 1 else random.randint(1, 10**6)
        url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(full) +
               f"?width=720&height=1280&model=flux&nologo=true&seed={seed}")
        try:
            r = requests.get(url, timeout=90)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image") and len(r.content) > 5000:
                open(path, "wb").write(r.content)
                return True
            log(f"  ภาพลองที่ {t} ล้ม: {r.status_code}")
        except requests.RequestException as e:
            log(f"  ภาพลองที่ {t} ล้ม: {e}")
        time.sleep(5 * t)
    return False


def make_clip(img, dur, i, out):
    frames = max(1, round(dur * FPS))
    step = 0.18 / frames
    if i % 2 == 0:
        z = f"min(zoom+{step:.6f},1.18)"
    else:
        z = f"if(eq(on,1),1.18,max(zoom-{step:.6f},1.0))"
    pre = f"crop=iw:ih*{1 - CROP_BOTTOM:.4f}:0:0," if CROP_BOTTOM > 0 else ""
    vf = (pre + "scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
          f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={FPS},"
          "format=yuv420p")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", img, "-vf", vf, "-frames:v", str(frames),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-r", str(FPS), out])


def preflight_image():
    # เช็กว่า Pollinations ตอบก่อนเริ่ม เพื่อไม่เสียโควตา Gemini ฟรีๆ ถ้าบริการภาพล่ม
    for t in (1, 2):
        try:
            r = requests.get("https://image.pollinations.ai/prompt/" + urllib.parse.quote("a red circle on white background")
                             + "?width=256&height=256&model=flux&nologo=true", timeout=60)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image") and len(r.content) > 1000:
                return True
            log(f"  เช็กบริการภาพครั้งที่ {t} ล้ม: {r.status_code}")
        except requests.RequestException as e:
            log(f"  เช็กบริการภาพครั้งที่ {t} ล้ม: {e}")
        time.sleep(5)
    return False


def main():
    log("[ขั้น 0] เช็กบริการสร้างภาพ")
    if not preflight_image():
        sys.exit("บริการสร้างภาพ (Pollinations) ไม่ตอบ หยุดก่อนใช้โควตา Gemini รอสักพักแล้วกดรันใหม่")

    script, all_srcs = get_script()
    scenes = script["scenes"]
    n = len(scenes)

    # สร้างภาพทุกฉากก่อน (ไม่กินโควตา Gemini) ถ้าล้มเกินครึ่งให้หยุดก่อนใช้โควตาเสียง
    imgs, prev, failed = [], None, 0
    clip_seed = random.randint(1, 10**6)
    log(f"  [seed คลิปนี้] {clip_seed}")
    t0 = time.time()
    for i, s in enumerate(scenes):
        log(f"[ขั้น 3] ภาพฉาก {i + 1}/{n}")
        img = f"work/img{i}.jpg"
        if time.time() - t0 > IMG_BUDGET:
            ok = False
            log("  เกินเวลาเจนภาพ ข้ามการเจนภาพ")
        else:
            ok = make_image(s["image_prompt"], img, clip_seed)
        if not ok:
            failed += 1
            if prev:
                img = prev
                log("  ภาพล้ม ใช้ภาพฉากก่อนหน้าแทน")
            else:
                solid_image(img)
                log("  ภาพล้ม ใช้พื้นสีเรียบแทน")
        prev = img
        imgs.append(img)
    if failed * 2 >= n:
        sys.exit(f"ภาพล้ม {failed}/{n} ฉาก หยุดก่อนสร้างเสียงเพื่อรักษาโควตา รอบนี้ใช้โควตาบทไปแล้ว 1 ครั้ง")
    if failed:
        warnings.append(f"ภาพล้ม {failed} ฉาก ใช้ภาพแทน")

    wav = make_voice(scenes)
    total = audio_duration(wav)
    weights = [max(1, len(re.sub(r"\s", "", s["narration"]))) for s in scenes]
    durs = [total * w / sum(weights) for w in weights]
    durs = snap_durations(durs, total, wav)
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

    title = script["title"].strip().replace("\n", " ")
    if script.get("part_note"):
        title += f" ({script['part_note']})"
    open("title.txt", "w", encoding="utf-8").write(title)
    lines = [f"# {title}", ""]
    lines += [f"หมวด: {NICHE}", ""]
    warnings.append("แหล่งข้อมูลมีเพียง Wikipedia หน้าเดียว ไม่ได้ตรวจซ้ำด้วย AI ต้องเปิดลิงก์เช็กเองทุกข้อ และตรวจว่าภาพไม่มีลายน้ำ")
    lines += ["## คำเตือน", *[f"- {w}" for w in warnings], ""]
    lines += ["## ลิงก์แหล่งข้อมูล (เปิดเช็กก่อนอัปโหลด)"]
    lines += [f"- {s['title']}: {s['uri']}" for s in all_srcs]
    lines += ["", "เนื้อหานี้สร้างด้วย AI โปรดติดป้าย AI ตอนอัปโหลด"]
    open("notes.md", "w", encoding="utf-8").write("\n".join(lines))
    log("เสร็จ: output.mp4")


if __name__ == "__main__":
    main()
  
