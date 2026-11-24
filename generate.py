import os, sys, re, json, time, base64, random, subprocess, urllib.parse
import requests

API_KEY = os.environ["GEMINI_API_KEY"]
CATEGORIES = ["ร่างกายมนุษย์", "สัตว์", "อวกาศและดาราศาสตร์", "ประวัติศาสตร์",
              "ธรรมชาติและภูมิศาสตร์", "สมองและจิตวิทยา", "มหาสมุทรและสัตว์ทะเล"]
NICHE = os.environ.get("NICHE", "").strip() or random.choice(CATEGORIES)
VOICE = os.environ.get("VOICE_NAME", "").strip() or "Enceladus"

TEXT_MODEL = "gemini-3.8-flash"
TTS_MODEL = "gemini-3.8-flash-tts"
EDGE_VOICE = "th-TH-NiwatNeural"
TTS_STYLE = "พูดภาษาไทยแบบคนเล่าเรื่องให้เพื่อนฟัง ชัดเจนทุกคำ และเว้นจังหวะก่อนข้อเท็จจริงที่น่าทึ่งที่สุด:"
API = "https://generativelanguage.googleapis.com/v1beta/models/"
FPS = 30
PAST_LIMIT = 30

STYLE = ("hand-drawn cartoon stickman style, thick black outlines, flat bright solid colors, "
         "simple clean background, vertical 9:16, absolutely no text, no letters, no numbers")
CHARACTER = ("the single main character is a white round-headed stickman with a white and green mohawk, "
             "thick black stick limbs, big expressive eyes and an exaggerated facial expression")

WRITER = """คุณคือนักเขียนบทคลิปสั้นแนวตั้งภาษาไทยแนว "ความรู้แปลกๆ"
ทำตามลำดับ:
1) ใช้ Google Search ค้นข้อมูลจริงก่อน แล้วเลือกหัวข้อในหมวด: __NICHE__ (ต้องอยู่ในหมวดนี้เท่านั้น เลือกเรื่องเฉพาะเจาะจงที่ไม่ใช่เรื่องดังที่ใครๆ ก็เล่า)
   ต้องเป็นเรื่องที่คนส่วนใหญ่ไม่รู้หรือขัดความเชื่อเดิม และห้ามซ้ำหรือใกล้เคียงหัวข้อเหล่านี้ (รวมถึงเรื่องเดียวกันที่ตั้งชื่อต่างกัน):
__PAST__
2) ค้นรอบที่สองเพื่อยืนยันข้อเท็จจริงหลักทุกข้อ ใช้แหล่งที่น่าเชื่อถือ เช่น มหาวิทยาลัย วารสารวิชาการ พิพิธภัณฑ์ หน่วยงานรัฐ องค์กรวิทยาศาสตร์ สำนักข่าวใหญ่ ห้ามใช้บล็อก ฟอรัม เว็บถามตอบ
   ข้อเท็จจริงที่ยืนยันไม่ได้ให้ตัดทิ้ง ตัวเลขและปีต้องตรงแหล่ง ถ้านักวิชาการยังถกเถียงให้พูดว่า "นักวิทยาศาสตร์เชื่อว่า"
3) เลี่ยงหัวข้อ: การเมือง ศาสนา คำแนะนำทางการแพทย์ที่คนอาจเอาไปทำตาม ความรุนแรงโหดร้าย เรื่องที่พาดพิงบุคคลจริงในทางเสียหาย
4) คิดประโยคฮุกหลายแบบ (ไม่เกิน 12 คำ) แล้วเลือกแบบที่แรงที่สุดแบบเดียว
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
ช่อง source ใส่ชื่อเว็บที่พบจริงในผลค้นหาของฉากนั้น ห้ามแต่งชื่อเอง
ทุกฉากต้องมีตัวละครสติกแมนตัวเดียวเป็นผู้กระทำ ระบุในภาพว่าสติกแมนกำลังทำอะไรกับวัตถุไหน
ห้ามเริ่มสองฉากติดกันด้วยคำเชื่อมซ้ำ เช่น แล้ว, ดังนั้น, และ
ฉากสรุปต้องเป็นประโยคที่คนจำได้ และห้ามพูดซ้ำคำที่ใช้ในฉากฮุก
ห้ามใส่เครื่องหมาย " ภายในข้อความใดๆ ใน JSON
ตอบเป็น JSON ล้วนๆ ไม่มี markdown รูปแบบ:
{"title":"ชื่อคลิปสั้นๆ ภาษาไทย","part_note":"","scenes":[{"narration":"บทพูด","image_prompt":"English scene","source":"ชื่อเว็บที่ใช้"}]}"""

warnings = []
os.makedirs("work", exist_ok=True)


class QuotaError(Exception):
    pass


def log(m):
    print(m, flush=True)


def run(cmd):
    subprocess.run(cmd, check=True)


def call(model, body):
    # ยิงครั้งเดียว ไม่ลองซ้ำ เพื่อประหยัดโควตา
    try:
        r = requests.post(API + model + ":generateContent",
                          headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
                          json=body, timeout=240)
    except requests.RequestException as e:
        log(f"  [API {model}] เชื่อมต่อไม่ได้: {e}")
        return None
    if r.status_code == 200:
        return r.json()
    if r.status_code == 429:
        log(f"  [API {model}] 429 โควตาเต็ม")
        raise QuotaError(model)
    log(f"  [API {model}] {r.status_code}: {r.text[:300]}")
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
        total = sum(len(re.sub(r"\s", "", s["narration"])) for s in sc)
        return (isinstance(d["title"], str) and d["title"].strip() and 6 <= len(sc) <= 14
                and all(s["narration"].strip() and s["image_prompt"].strip() for s in sc)
                and 550 <= total <= 1300)
    except Exception:
        return False


def get_script():
    past = ""
    if os.path.exists("past_titles.txt"):
        lines = [x.strip() for x in open("past_titles.txt", encoding="utf-8").read().splitlines() if x.strip()]
        past = "\n".join(lines[:PAST_LIMIT])
    log(f"[หมวดรอบนี้] {NICHE}")
    prompt = WRITER.replace("__NICHE__", NICHE).replace("__PAST__", past or "(ยังไม่มี)")
    log("[ขั้น 1] เขียนบท (รอบเดียว)")
    try:
        data, srcs = ask(prompt)
    except QuotaError:
        sys.exit("โควตา Gemini เต็ม (429) รอรีเซ็ตแล้วค่อยกดรันใหม่ ไม่ต้องแก้โค้ด")
    if not data:
        sys.exit("เขียนบทไม่สำเร็จ: ไม่ได้รับ JSON ที่แกะได้ ลองกดรันใหม่")
    if not valid(data):
        sys.exit("เขียนบทไม่สำเร็จ: โครงสร้างหรือความยาวบทผิดเกณฑ์ ลองกดรันใหม่")
    if not srcs:
        sys.exit("เขียนบทไม่สำเร็จ: API ไม่ส่งแหล่งข้อมูลกลับมา ลองกดรันใหม่")
    log(f"  ได้หัวข้อ: {data['title']} ({len(data['scenes'])} ฉาก, {len(srcs)} แหล่ง)")
    return data, srcs


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


def tts_gemini(text, wav):
    body = {"contents": [{"parts": [{"text": TTS_STYLE + "\n" + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    resp = call(TTS_MODEL, body)
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
    log(f"[ขั้น 3] สร้างเสียงทั้งคลิปด้วย {TTS_MODEL} (เสียง {VOICE})")
    reason = "Gemini TTS ล้มเหลว"
    try:
        if tts_gemini(text, wav):
            return wav
    except QuotaError:
        reason = "โควตา Gemini TTS เต็ม"
    except Exception as e:
        log(f"  ผิดพลาด: {e}")
    log("[ขั้น 3] ถอยไปใช้ edge-tts")
    warnings.append(f"เสียงพากย์ใช้ edge-tts ({reason})")
    tts_edge(text, wav)
    return wav


IMG_BUDGET = 18 * 60  # วินาที เกินนี้ฉากที่เหลือใช้ภาพก่อนหน้า


def solid_image(path):
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0xFFE066:s=1080x1920",
         "-frames:v", "1", path])


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
    vf = ("scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
          f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={FPS},"
          "format=yuv420p")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", img, "-vf", vf, "-frames:v", str(frames),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-r", str(FPS), out])


def main():
    script, srcs = get_script()
    seen, all_srcs = set(), []
    for s in srcs:
        if s["uri"] not in seen:
            seen.add(s["uri"])
            all_srcs.append(s)
    scenes = script["scenes"]
    n = len(scenes)

    wav = make_voice(scenes)
    total = audio_duration(wav)
    weights = [max(1, len(re.sub(r"\s", "", s["narration"]))) for s in scenes]
    durs = [total * w / sum(weights) for w in weights]
    durs = snap_durations(durs, total, wav)
    log(f"  เสียงยาว {total:.1f} วินาที")
    if total < 40 or total > 90:
        warnings.append(f"เสียงยาว {total:.0f} วินาที อยู่นอกช่วงที่ตั้งใจ (45-80 วินาที)")

    clips, prev, failed = [], None, 0
    clip_seed = random.randint(1, 10**6)
    log(f"  [seed คลิปนี้] {clip_seed}")
    t0 = time.time()
    for i, s in enumerate(scenes):
        log(f"[ขั้น 4] ฉาก {i + 1}/{n}: ภาพ + คลิป ({durs[i]:.1f} วินาที)")
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
    lines += [f"หมวด: {NICHE}", ""]
    warnings.append("ไม่ได้ตรวจซ้ำด้วย AI ต้องเปิดลิงก์แหล่งข้อมูลเช็กเองทุกข้อก่อนอัปโหลด")
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
  
