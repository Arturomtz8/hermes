import os
import subprocess

import mlx_whisper as whisper
import yt_dlp
from tqdm import tqdm


def download_video(url):
    ydl_opts = {"outtmpl": "input_video.mp4", "format": "mp4", "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return "input_video.mp4"


def get_segments(video_path):
    audio_path = "temp_audio.wav"
    # Isolate audio for Whisper
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            audio_path,
        ],
        check=True,
        capture_output=True,
    )

    print("🧠 Transcribing...")
    result = whisper.transcribe(
        audio_path, path_or_hf_repo="mlx-community/whisper-small-mlx"
    )

    if os.path.exists(audio_path):
        os.remove(audio_path)
    return result.get("segments", [])


def format_ass_timestamp(seconds):
    hours = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int((seconds % 1) * 100)
    return f"{hours}:{mins:02}:{secs:02}.{msecs:02}"


def create_ass_file(segments, ass_path="subs.ass"):
    # Style: Yellow, Bold, Bottom-Center
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 384\nPlayResY: 288\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Helvetica,22,&H0000FFFF,&H000000FF,&H00000000,&H00000000,"
        "1,0,0,0,100,100,0,0,1,2,0,2,10,10,40,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header)
        for seg in segments:
            start = format_ass_timestamp(seg["start"])
            end = format_ass_timestamp(seg["end"])
            text = seg["text"].strip().replace("\n", " ")
            f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")
    return ass_path


def burn_subtitles_fast(video_path, ass_path, output_path):
    # This is the most compatible way to write the filter string
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vf",
        f"subtitles={ass_path}",
        "-c:v",
        "h264_videotoolbox",
        "-b:v",
        "6000k",
        "-c:a",
        "copy",
        output_path,
    ]
    print("🎬 Rendering Final Video...")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    INPUT_FILE = "input_video.mp4"
    ASS_FILE = "subs.ass"
    URL = "https://www.tiktok.com/@ken.digitalera/video/7605320127973723413"

    try:
        vid = download_video(URL)
        segments = get_segments(vid)
        ass = create_ass_file(segments, ASS_FILE)
        burn_subtitles_fast(vid, ass, "final_video.mp4")
        print("\n✨ Done! Check: final_video.mp4")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        for f in [INPUT_FILE, ASS_FILE]:
            if os.path.exists(f):
                os.remove(f)
