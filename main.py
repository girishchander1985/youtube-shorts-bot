import os
import json
import requests
import subprocess
from pathlib import Path
from google import genai
import azure.cognitiveservices.speech as speechsdk
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from db_manager import get_recent_topics, record_published_short
from notifier import send_telegram_alert, send_telegram_error

WORKDIR = Path(__file__).resolve().parent
OUTPUT_DIR = WORKDIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
AZURE_SPEECH_KEY = os.environ.get("AZURE_SPEECH_KEY")
AZURE_REGION = os.environ.get("AZURE_REGION", "eastus")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

def generate_content(niche="Bizarre Historical Secrets"):
    past_topics = get_recent_topics(50)
    exclusion = ""
    if past_topics:
        exclusion = "CRITICAL: Do NOT repeat these covered topics:\n- " + "\n- ".join(past_topics)

    prompt = f"""
    You are a viral YouTube Shorts creator in '{niche}'.
    Write a high-retention 40-word script. Open immediately with an intriguing hook.
    Also generate a dark cinematic image prompt (9:16 vertical) and an engaging title.
    {exclusion}

    Output JSON strictly:
    {{
      "title": "Title with #Shorts",
      "script": "Narration text only",
      "image_prompt": "Cinematic visual description",
      "topic_summary": "1-sentence summary of the event",
      "tags": ["history", "facts", "mystery", "shorts"]
    }}
    """
    res = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(res.text)

def synthesize_audio(text: str, filename="narration.wav"):
    audio_path = OUTPUT_DIR / filename
    cfg = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_REGION)
    cfg.speech_synthesis_voice_name = "en-US-ChristopherNeural"
    out_cfg = speechsdk.audio.AudioOutputConfig(filename=str(audio_path))
    synth = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=out_cfg)

    words = []
    def on_word(evt):
        words.append({
            "word": evt.text,
            "start": evt.audio_offset / 10_000_000,
            "end": (evt.audio_offset / 10_000_000) + evt.duration.total_seconds()
        })

    synth.synthesis_word_boundary.connect(on_word)
    result = synth.speak_text_async(text).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise RuntimeError("Azure synthesis failed")
    return str(audio_path), words

def build_subtitles(words, filename="subs.srt"):
    srt_path = OUTPUT_DIR / filename
    def fmt(t):
        hrs, rem = divmod(t, 3600)
        mins, secs = divmod(rem, 60)
        ms = int((secs - int(secs)) * 1000)
        return f"{int(hrs):02d}:{int(mins):02d}:{int(secs):02d},{ms:03d}"

    with open(srt_path, "w", encoding="utf-8") as f:
        idx = 1
        for i in range(0, len(words), 2):
            chunk = words[i:i+2]
            f.write(f"{idx}\n{fmt(chunk[0]['start'])} --> {fmt(chunk[-1]['end'])}\n{' '.join([w['word'] for w in chunk]).upper()}\n\n")
            idx += 1
    return str(srt_path)

def build_video(image_prompt: str, audio_path: str, srt_path: str, output_name="short.mp4"):
    img_path = OUTPUT_DIR / "bg.png"
    encoded = requests.utils.quote(f"{image_prompt}, 8k, dark moody lighting, vertical 9:16")
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true"
    with open(img_path, "wb") as f:
        f.write(requests.get(url, timeout=30).content)

    final_video = OUTPUT_DIR / output_name
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(img_path),
        "-i", audio_path,
        "-vf", (
            f"zoompan=z='min(zoom+0.0016,1.25)':d=750:s=1080x1920:fps=30,"
            f"subtitles={srt_path}:force_style='FontSize=24,FontName=Arial Black,"
            f"PrimaryColour=&H00FFFF,OutlineColour=&H000000,BorderStyle=3,Outline=3,Alignment=2'"
        ),
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(final_video)
    ]
    subprocess.run(cmd, check=True)
    return str(final_video)

def get_yt_client():
    token_file = WORKDIR / "token.json"
    creds = Credentials.from_authorized_user_file(str(token_file))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def upload_short(yt, video_path, title, tags):
    body = {
        "snippet": {"title": title, "description": f"{title}\n\n#Shorts #History #Mysteries", "tags": tags, "categoryId": "27"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    res = yt.videos().insert(part="snippet,status", body=body, media_body=media).execute()
    return res["id"]

def reply_recent_comments(yt, video_id):
    try:
        res = yt.commentThreads().list(part="snippet", videoId=video_id, maxResults=5).execute()
        for item in res.get("items", []):
            cid = item["snippet"]["topLevelComment"]["id"]
            author = item["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"]
            text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            prompt = f"Write an authentic 1-sentence creator reply to @{author}'s comment: '{text}'"
            reply = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text.strip()
            yt.comments().insert(part="snippet", body={"snippet": {"parentId": cid, "textOriginal": reply}}).execute()
    except Exception as e:
        print(f"Comment processing skipped: {e}")

if __name__ == "__main__":
    try:
        content = generate_content()
        audio_file, words = synthesize_audio(content["script"])
        srt_file = build_subtitles(words)
        video_file = build_video(content["image_prompt"], audio_file, srt_file)
        
        yt = get_yt_client()
        vid_id = upload_short(yt, video_file, content["title"], content["tags"])
        record_published_short(content["topic_summary"], vid_id)
        send_telegram_alert(content["title"], vid_id, content["topic_summary"])
        reply_recent_comments(yt, vid_id)
    except Exception as exc:
        send_telegram_error(str(exc))
        raise