import os

import whisper
import yt_dlp

# --- MAC CONFIGURATION ---
# 1. ImageMagick Path
os.environ["IMAGEMAGICK_BINARY"] = "/opt/homebrew/bin/magick"

# 2. FFmpeg Path (Fixes the [Errno 2] error)
ffmpeg_path = (
    "/opt/homebrew/bin/ffmpeg"
    if os.path.exists("/opt/homebrew/bin/ffmpeg")
    else "/usr/local/bin/ffmpeg"
)
os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path

# Now import MoviePy
from moviepy import CompositeVideoClip, TextClip, VideoFileClip


def download_video(url):
    print(f"Downloading: {url}")
    ydl_opts = {"outtmpl": "input_video.mp4", "format": "mp4", "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return "input_video.mp4"


def get_segments(video_path):
    print("Transcribing with Whisper...")
    model = whisper.load_model("base")
    result = model.transcribe(video_path, language="es")
    return result.get("segments", [])


def burn_subtitles(video_path, segments, output_path):
    if not segments:
        print("No speech detected. Creating video without subs.")
        return

    video = VideoFileClip(video_path)
    subtitle_clips = []

    # Define Font (Bulletproof path for Mac)
    font_path = "/Library/Fonts/Arial Bold.ttf"
    if not os.path.exists(font_path):
        font_path = "/System/Library/Fonts/Helvetica.ttc"

    for seg in segments:
        duration = seg["end"] - seg["start"]
        if duration <= 0:
            continue

        # Build each subtitle piece
        txt = (
            TextClip(
                text=seg["text"].strip(),
                font_size=40,
                color="white",
                font=font_path,
                stroke_color="black",
                stroke_width=1.5,
                method="caption",
                size=(int(video.w * 0.8), None),
            )
            .with_start(seg["start"])
            .with_duration(duration)
            .with_position(("center", video.h * 0.8))
        )

        subtitle_clips.append(txt)

    print(f"Compositing {len(subtitle_clips)} subtitle segments...")
    final_video = CompositeVideoClip([video] + subtitle_clips)

    # Write result
    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac")

    video.close()
    final_video.close()


if __name__ == "__main__":
    URL = "https://www.tiktok.com/@mardetodaspartes/video/7604019792965651733"
    try:
        vid = download_video(URL)
        subs = get_segments(vid)
        burn_subtitles(vid, subs, "final_video.mp4")

        if os.path.exists(vid):
            os.remove(vid)
        print("✨ Done! Check final_video.mp4")
    except Exception as e:
        print(f"❌ Error: {e}")
