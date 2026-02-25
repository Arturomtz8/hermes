import os
import subprocess
import asyncio
import mlx_whisper as whisper
import yt_dlp
from googletrans import Translator
from tqdm import tqdm
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

def download_video(url, input_file):
    ydl_opts = {"outtmpl": input_file, "format": "mp4", "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return input_file


def get_segments(video_path):
    audio_path = "temp_audio.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",  # -y: overwrites the output file (temp_audio.wav) even if already exists
            "-i",  # -i input, the path that will be passed below as video_path
            video_path,
            "-vn",  # "Video None"—strips out the video track entirely to save processing power
            "-acodec",
            "pcm_s16le",  # Sets the audio codec to uncompressed WAV (Linear PCM), which ensures no quality is lost during extraction
            "-ar",
            "16000",  # Sets the Sampling Rate to 16kHz. This is the specific frequency most speech-to-text models (like Whisper) are trained on.
            "-ac",
            "1",  # Audio Channels —converts the sound to mono. AI doesn't need stereo to understand words.
            audio_path,
        ],
        check=True,  # If FFmpeg fails (the video is corrupted or FFmpeg isn't installed), it will raise an error immediately
    )

    print("Transcribing...")
    result = whisper.transcribe(
        audio_path,
        # the model is optimized for Apple Silicon (M1/M2/M3 chips) using Apple’s MLX framework
        path_or_hf_repo="mlx-community/whisper-small-mlx",
    )

    if os.path.exists(audio_path):
        os.remove(audio_path)
    return result.get("segments", [])


def format_ass_timestamp(seconds):
    hours = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    csecs = int((seconds % 1) * 100)
    return f"{hours}:{mins:02}:{secs:02}.{csecs:02}"


def create_dual_ass_file(segments, ass_path="subs.ass"):
    translator = Translator()

    header = (
        # PlayResX is for treating the screen as a grid 384 units wide
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 384\nPlayResY: 288\nScaledBorderAndShadow: yes\n"
        "CollisionRule: None\n\n"
        "[V4+ Styles]\n"  # defines 2 templates, for spanish and english
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Spanish,Helvetica,10,&H0000FFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,1,0,2,30,30,10,1\n"
        "Style: English,Helvetica,10,&H00FFFF00,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1.5,2,2,30,30,10,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    print("Translating...")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header)
        for seg in tqdm(segments):
            start = format_ass_timestamp(seg["start"])
            end = format_ass_timestamp(seg["end"])
            original_text = seg["text"].strip().replace("\n", " ")

            try:
                translated = translator.translate(
                    original_text, src="es", dest="en"
                ).text
            except:
                translated = "[...]"

            f.write(
                # Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
                f"Dialogue: 1,{start},{end},Spanish,,0,0,0,,{{\\pos(192,235)}}{original_text}\n"
            )
            f.write(
                f"Dialogue: 0,{start},{end},English,,0,0,0,,{{\\pos(192,265)}}{translated}\n"
            )

    return ass_path


def burn_subtitles_fast(video_path, ass_path, output_path):
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output_path if it already exists without asking
        "-i",
        video_path,  # Input: The raw video file we downloaded earlier
        # --- VIDEO FILTERING ---
        "-vf",
        f"subtitles={ass_path}",  # Video Filter: Uses the 'subtitles' engine to
        # draw your .ass file onto every frame of the video.
        # --- VIDEO ENCODING ---
        "-c:v",
        "libx264",  # Codec Video: Use H.264 (the most compatible format in the world)
        "-crf",
        "21",  # Constant Rate Factor: Controls quality. 0 is lossless, 51 is worst.
        "-preset",
        "veryfast",  # Speed/Compression ratio: 'veryfast' tells the CPU to finish
        # quickly at the cost of a slightly larger file size.
        "-pix_fmt",
        "yuv420p",  # Pixel Format: Ensures the video plays on everything
        # (older iPhones, web browsers, and standard TVs).
        # --- AUDIO ENCODING ---
        "-c:a",
        "aac",  # Codec Audio: Use AAC (the standard companion to H.264)
        "-b:a",
        "128k",  # Bitrate Audio: 128kbps is high-quality stereo sound
        # (standard for YouTube/streaming).
        output_path,
    ]
    subprocess.run(cmd, check=True)

@app.get("/")
async def get():
    with open("index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/process")
async def process_video(url: str, request: Request):
    async def event_generator():
        INPUT_FILE = "input_video.mp4"
        ASS_FILE = "subs.ass"
        OUTPUT_FILE = "final_dual_video.mp4"

        try:
            yield {"data": "Starting download..."}
            await asyncio.to_thread(download_video, url, INPUT_FILE)
            
            yield {"data": "Extracting audio and transcribing (MLX)..."}
            segments = await asyncio.to_thread(get_segments, INPUT_FILE)
            
            yield {"data": "Translating and creating subtitles..."}
            ass = await asyncio.to_thread(create_dual_ass_file, segments, ASS_FILE)
            
            yield {"data": "Burning subtitles with FFmpeg..."}
            await asyncio.to_thread(burn_subtitles_fast, INPUT_FILE, ass, OUTPUT_FILE)
            
            yield {"data": "Done! Video saved as final_dual_video.mp4"}
        except Exception as e:
            yield {"data": f"Error: {str(e)}"}
        finally:
            for f in [INPUT_FILE, ASS_FILE]:
                if os.path.exists(f):
                    os.remove(f)
    # This is the wrapper that turns the generator into an HTTP stream
    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
