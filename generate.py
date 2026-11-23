import os, sys, re, json, time, base64, random, subprocess, urllib.parse
import requests

API_KEY = os.environ["GEMINI_API_KEY"]
NICHE = os.environ.get("NICHE", "").strip() or "ผสมหลายแนว (วิทยาศาสตร์ ร่างกายมนุษย์ สัตว์ อวกาศ ประวัติศาสตร์)"
VOICE = os.environ.get("VOICE_NAME", "").strip() or "Enceladus"

TEXT_MODEL = "gemini-3.8-flash"
TTS_MODELS = ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"]
EDGE_VOICE = "th-TH-NiwatNeural"
TTS_STYLE = "เล่าด้วยน้ำเสียงอยากรู้อยากเห็น กระชับ ชัดเจน เว้นจังหวะก่อนข้อเท็จจริงที่น่าทึ่งที่สุด:"
API = "https://generativelanguage.googleapis.com/v1beta/models/"
FPS = 30

STYLE = ("hand-drawn cartoon stickman style, thick black outlines, flat bright solid colors, "
         "simple clean background, vertical 9:16, absolutely no text, no letters, no numbers")
CHARACTER = ("the single main character is a white round-headed stickman with thick black stick limbs, "
             "big expressive eyes and an exaggerated facial expression")

WRITER = """คุณคือนักเขียนบทคลิปสั้นแนวตั้งภาษาไทยแนว "ความรู้แปลกๆ"
ทำตามลำดับ:
1) ใช้ Google Search ค้นข้อมูลจริงก่อน แล้วเลือกหัวข้อแนว: __NICHE__
   ต้องเป็นเรื่องที่คนส่วนใหญ่ไม่รู้หรือขัดความเชื่อเดิม และห้ามซ้ำหัวข้อเหล่านี้:
__PAST__
2) ใช้เฉพาะข้อเท็จจริงที่มีแหล่งในผลค้นหา ตัวเลขและปีต้องตรงแหล่ง ถ้านักวิชาการยังถกเถียงให้พูดว่า "นักวิทยาศาสตร์เชื่อว่า"
3) คิดประโยคฮุกหลายแบบ (ไม่เกิน 12 คำ) แล้วเลือกแบบที่แรงที่สุดแบบเดียว
โครงเรื่อง: ฉากแรกคือฮุก เข้าเรื่องทันที ไม่ทักทาย
→ ฉากกลางเฉลยทีละชั้นแบบเหตุ→ผล (ฉากที่ 2-3 ต้องมีข้อมูลใหม่หรือหักมุม)
→ ไคลแมกซ์ → ฉากสรุป 1 ประโยค
→ ฉากปิด (ไม่เกิน 2 ประโยค ชวนกดติดตามพร้อมเหตุผล และชวนคอมเมนต์)
กฎ "ครบแล้วจบ": อธิบายจนคนไม่มีพื้นฐานเข้าใจ นิยามคำยากก่อนใช้ ตอบคำถามฮุกให้ครบ ห้ามประโยคเติมหรือซ้ำ
ภาษาพูดธรรมชาติ ห้ามอีโมจิ เขียนตัวเลข หน่วย และคำอังกฤษเป็นคำอ่านไทยทั้งหมด (เช่น "สามดวง", "กิโลเมตร", "ดีเอ็นเอ")
จำนวนฉาก 5-14 ฉาก บทพูดแต่ละฉากยาวราว 40-110 ตัวอักษร (ประมาณ 3-6 วินาที)
ถ้าหัวข้อใหญ่เกินกว่าจะจบใน 14 ฉาก ให้เล่าเฉพาะตอนที่ 1 แล้วใส่ part_note
image_prompt เขียนเป็นภาษาอังกฤษ บรรยายเฉพาะการกระทำในฉากที่อธิบายกลไกของสิ่งที่พูด ไม่ต้องเขียนสไตล์หรือรูปร่างตัวละคร
ฉากแรกให้เป็นภาพ action ดึงสายตา ห้ามมีตัวหนังสือ ตัวเลข ในภาพ
ตอบเป็น JSON ล้วนๆ ไม่มี markdown รูปแบบ:
{"title":"ชื่อคลิปสั้นๆ ภาษาไทย","part_note":"","scenes":[{"narration":"บทพูด","image_prompt":"English scene","source":"ชื่อเว็บที่ใช้"}]}"""

CHECKER = """คุณคือผู้ตรวจข้อเท็จจริง ใช้ Google Search เทียบบทพูดด้านล่างกับแหล่งข้อมูลจริงทีละประโยค
ส่วนที่ไม่มีแหล่งรองรับ ตัวเลข/ปีที่ไม่ตรง ให้แก้ให้ถูกหรือตัดออก (ห้ามเพิ่มข้อมูลที่ไม่มีแหล่ง)
คงโครงเรื่อง ภาษาพูด ตัวเลขเป็นคำอ่านไทย และจำนวนฉาก 5-14 ฉากไว้
แหล่งที่พบตอนเขียนบท:
__SOURCES__
บทที่ต้องตรวจ:
__SCRIPT__
ตอบ JSON ล้วนๆ โครงเดิมทุกฟิลด์ เพิ่มฟิลด์ "changes" เป็นลิสต์ข้อความสั้นๆ ว่าแก้หรือตัดอะไร (ว่างได้)"""
warnings = []
os.makedirs("work", exist_ok=True)


def log(m):
    print(m, flush=True)


def run(cmd):
    subprocess.run(cmd, check=True)


def call(model, body, tries=4):
    for i in range(tries):
        try:
            r = requests.post(API + model + ":generateContent",
                              headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
                              json=body, timeout=240)
            if r.status_code == 200:
                return r.json()
            log(f"  [API {model}] {r.status_code}: {r.text[:300]}")
            if r.status_code not in (429, 500, 503):
                return None
        except requests.RequestException as e:
            log(f"  [API {model}] เชื่อมต่อไม่ได้: {e}")
        if i < tries - 1:
            time.sleep(15 * (i + 1))
    return None


def ask(prompt):
    resp = call(TEXT_MODEL, {"contents": [{"parts": [{"text": prompt}]}],
                             "tools": [{"google_search": {}}]})
    if not resp:
        return None, []
    data, srcs = None, []
    try:
        cand = resp["candidates"][0]
        text = "".join(p.get("text", "") for p in cand["content"]["parts"])
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0)) if m else None
        for c in cand.get("groundingMetadata", {}).get("groundingChunks", []):
            w = c.get("web")
            if w and w.get("uri"):
                srcs.append({"title": w.get("title", ""), "uri": w["uri"]})
    except Exception as e:
        log(f"  แกะคำตอบไม่ได้: {e}")
    return data, srcs


def valid(d):
    try:
        sc = d["scenes"]
        return (isinstance(d["title"], str) and d["title"].strip() and 5 <= len(sc) <= 14
                and all(s["narration"].strip() and s["image_prompt"].strip() for s in sc))
    except Exception:
        return False


def get_script():
    past = ""
    if os.path.exists("past_titles.txt"):
        past = open("past_titles.txt", encoding="utf-8").read().strip()
    prompt = WRITER.replace("__NICHE__", NICHE).replace("__PAST__", past or "(ยังไม่มี)")
    for n in range(1, 6):
        log(f"[ขั้น 1] เขียนบท รอบที่ {n}/5")
        data, srcs = ask(prompt)
        if data and valid(data) and srcs:
            log(f"  ได้หัวข้อ: {data['title']} ({len(data['scenes'])} ฉาก, {len(srcs)} แหล่ง)")
            return data, srcs
        log("  ไม่มีแหล่ง/โครงสร้างผิด ทิ้งหัวข้อแล้วลองใหม่")
    sys.exit("เขียนบทไม่สำเร็จครบ 5 ครั้ง")


def verify(script, srcs):
    log("[ขั้น 2] ตรวจความถูกต้องชั้นที่ 2")
    src_txt = "\n".join(f"- {s['title']} {s['uri']}" for s in srcs)
    prompt = (CHECKER.replace("__SOURCES__", src_txt)
              .replace("__SCRIPT__", json.dumps(script, ensure_ascii=False)))
    data, srcs2 = ask(prompt)
    if data and valid(data):
        for c in data.get("changes", []):
            log(f"  แก้: {c}")
        return data, srcs2
    warnings.append("การตรวจความถูกต้องชั้นที่ 2 ไม่สำเร็จ ใช้บทจากรอบแรก ต้องเช็กแหล่งเองให้ละเอียด")
    log("  ตรวจชั้น 2 ไม่สำเร็จ ใช้บทเดิม")
    return script, []
def audio_duration(wav):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", wav])
    return float(out.strip())


def tts_gemini(text, model, wav):
    body = {"contents": [{"parts": [{"text": TTS_STYLE + "\n" + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    resp = call(model, body, tries=2)
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
    for m in TTS_MODELS:
        log(f"[ขั้น 3] สร้างเสียงทั้งคลิปด้วย {m} (เสียง {VOICE})")
        try:
            if tts_gemini(text, m, wav):
                return wav
        except Exception as e:
            log(f"  ผิดพลาด: {e}")
    log("[ขั้น 3] ถอยไปใช้ edge-tts")
    warnings.append("เสียงพากย์ใช้ edge-tts (Gemini TTS ล้มเหลวหรือเกินโควตา)")
    tts_edge(text, wav)
    return wav
def solid_image(path):
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0xFFE066:s=1080x1920",
         "-frames:v", "1", path])


def make_image(prompt, path):
    full = f"{STYLE}, {CHARACTER}, {prompt}"
    for t in range(1, 4):
        url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(full) +
               f"?width=1080&height=1920&model=flux&nologo=true&seed={random.randint(1, 10**6)}")
        try:
            r = requests.get(url, timeout=180)
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
    vf = ("scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
          f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={FPS},"
          "format=yuv420p")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", img, "-vf", vf, "-frames:v", str(frames),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-r", str(FPS), out])
def main():
    script, srcs = get_script()
    script, srcs2 = verify(script, srcs)
    seen, all_srcs = set(), []
    for s in srcs + srcs2:
        if s["uri"] not in seen:
            seen.add(s["uri"])
            all_srcs.append(s)
    scenes = script["scenes"]
    n = len(scenes)

    wav = make_voice(scenes)
    total = audio_duration(wav)
    weights = [max(1, len(re.sub(r"\s", "", s["narration"]))) for s in scenes]
    durs = [total * w / sum(weights) for w in weights]
    log(f"  เสียงยาว {total:.1f} วินาที")

    clips, prev, failed = [], None, 0
    for i, s in enumerate(scenes):
        log(f"[ขั้น 4] ฉาก {i + 1}/{n}: ภาพ + คลิป ({durs[i]:.1f} วินาที)")
        img = f"work/img{i}.jpg"
        if not make_image(s["image_prompt"], img):
            failed += 1
            if prev:
                img = prev
                log("  ภาพล้ม ใช้ภาพฉากก่อนหน้าแทน")
            else:
                solid_image(img)
                log("  ภาพล้ม ใช้พื้นสีเรียบแทน")
        prev = img
        clip = f"work/clip{i}.mp4"
        make_clip(img, durs[i], i, clip)
        clips.append(clip)
        time.sleep(3)
    if failed:
        warnings.append(f"ภาพล้ม {failed} ฉาก ใช้ภาพแทน")

    log("[ขั้น 5] ประกอบวิดีโอ")
    open("work/list.txt", "w").write("".join(f"file '{os.path.basename(c)}'\n" for c in clips))
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "work/list.txt",
         "-i", wav, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "output.mp4"])

    title = script["title"].strip().replace("\n", " ")
    if script.get("part_note"):
        title += f" ({script['part_note']})"
    open("title.txt", "w", encoding="utf-8").write(title)
    lines = [f"# {title}", ""]
    if warnings:
        lines += ["## คำเตือน", *[f"- {w}" for w in warnings], ""]
    lines += ["## แหล่งแต่ละฉาก"]
    lines += [f"{i + 1}. {s.get('source', '-')}" for i, s in enumerate(scenes)]
    lines += ["", "## ลิงก์แหล่งข้อมูล (เปิดเช็กก่อนอัปโหลด)"]
    lines += [f"- {s['title']}: {s['uri']}" for s in all_srcs]
    lines += ["", "เนื้อหานี้สร้างด้วย AI โปรดติดป้าย AI ตอนอัปโหลด"]
    open("notes.md", "w", encoding="utf-8").write("\n".join(lines))
    log("เสร็จ: output.mp4")


if __name__ == "__main__":
    main()
