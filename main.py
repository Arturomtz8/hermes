import os

import mlx_whisper as whisper  # Optimized for Mac
import yt_dlp
from moviepy import CompositeVideoClip, TextClip, VideoFileClip


def download_video(url):
    ydl_opts = {"outtmpl": "input_video.mp4", "format": "mp4", "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return "input_video.mp4"


def get_segments(video_path):
    print("Transcribing with MLX (High Speed Mac Optimization)...")

    # Using the most reliable public repo for MLX Whisper Small
    # 'mlx-community/whisper-small-mlx' is the standard naming convention
    try:
        result = whisper.transcribe(
            video_path, path_or_hf_repo="mlx-community/whisper-small-mlx"
        )
    except Exception as e:
        print(f"Small model failed, trying base model... Error: {e}")
        result = whisper.transcribe(
            video_path, path_or_hf_repo="mlx-community/whisper-base-mlx"
        )

    return result.get("segments", [])


def burn_subtitles(video_path, segments, output_path):
    video = VideoFileClip(video_path)
    subtitle_clips = []

    # Use a faster font resolution
    font_path = "/System/Library/Fonts/Helvetica.ttc"

    print(f"Preparing {len(segments)} subtitle segments...")

    for seg in segments:
        duration = seg["end"] - seg["start"]
        if duration <= 0:
            continue

        # OPTIMIZATION: method='caption' is slow because it calculates wrapping.
        # If your lines are short, 'label' is faster. But for TikTok, we keep caption
        # and just ensure we aren't over-processing.
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
            .with_position(("center", int(video.h * 0.8)))
        )
        subtitle_clips.append(txt)

    print("Compositing layers...")
    final_video = CompositeVideoClip([video] + subtitle_clips)

    print("Encoding with Hardware Acceleration + Multithreading...")
    final_video.write_videofile(
        output_path,
        codec="h264_videotoolbox",
        # Use more threads for the composite calculation
        threads=8,
        # Increase logger to 'None' or 'bar' to save console overhead
        logger="bar",
        ffmpeg_params=["-b:v", "5000k", "-realtime", "1"],
        audio_codec="aac",
        # Lowering fps of the text overlays can save time if original is 60fps
        fps=video.fps,
    )

    video.close()
    final_video.close()


if __name__ == "__main__":
    URL = "https://www.tiktok.com/@ken.digitalera/video/7605320127973723413"
    try:
        vid = download_video(URL)
        subs = get_segments(vid)
        burn_subtitles(vid, subs, "final_video.mp4")
        print("✨ Done!")
    except Exception as e:
        print(f"❌ Error: {e}")

    # URL = "https://www.tiktok.com/@mardetodaspartes/video/7604019792965651733"
