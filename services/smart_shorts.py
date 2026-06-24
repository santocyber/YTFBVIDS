import os, subprocess, json, math, re
from pathlib import Path


def get_video_duration(video_path):
    r = subprocess.run([
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'csv=p=0', str(video_path)
    ], capture_output=True, text=True, timeout=30)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0


def get_video_dimensions(video_path):
    r = subprocess.run([
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'json', str(video_path)
    ], capture_output=True, text=True, timeout=30)
    data = json.loads(r.stdout)
    streams = data.get('streams', [])
    if not streams:
        return 1920, 1080
    return int(streams[0].get('width', 1920)), int(streams[0].get('height', 1080))


def fmt_tc(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def detect_scenes(video_path, threshold=0.3, min_duration=3, max_segment=120):
    """
    Detect scenes using ffmpeg scene filter.
    Falls back to uniform segments if no scene changes found.
    """
    scenes = []
    total = get_video_duration(video_path)

    if total > max_segment:
        return [{
            'index': 0,
            'start': 0.0,
            'end': round(total, 2),
            'duration': round(total, 2),
            'start_tc': fmt_tc(0),
            'end_tc': fmt_tc(total),
        }]

    # Try ffmpeg scene detection
    cmd = [
        'ffmpeg', '-i', str(video_path),
        '-filter:v', f"select='gt(scene,{threshold})',showinfo",
        '-f', 'null', '-'
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        cut_times = []
        for line in r.stderr.split('\n'):
            m = re.search(r'pts_time:([\d.]+)', line)
            if m:
                t = float(m.group(1))
                if 0 < t < total:
                    cut_times.append(t)
        cut_times.sort()
    except Exception:
        cut_times = []

    # Build scenes from cut points
    prev = 0.0
    for i, t in enumerate(cut_times):
        dur = t - prev
        if dur >= min_duration:
            scenes.append({
                'index': i,
                'start': round(prev, 2),
                'end': round(t, 2),
                'duration': round(dur, 2),
                'start_tc': fmt_tc(prev),
                'end_tc': fmt_tc(t),
            })
        prev = t

    # Last segment
    last_dur = total - prev
    if last_dur >= min_duration:
        scenes.append({
            'index': len(scenes),
            'start': round(prev, 2),
            'end': round(total, 2),
            'duration': round(last_dur, 2),
            'start_tc': fmt_tc(prev),
            'end_tc': fmt_tc(total),
        })

    # Fallback: split into equal segments if no scenes detected
    if not scenes and total > 0:
        n = max(1, int(total / max_segment))
        seg_dur = total / n
        for i in range(n):
            start = i * seg_dur
            end = min((i + 1) * seg_dur, total)
            scenes.append({
                'index': i,
                'start': round(start, 2),
                'end': round(end, 2),
                'duration': round(end - start, 2),
                'start_tc': fmt_tc(start),
                'end_tc': fmt_tc(end),
            })

    return scenes


def split_long_scenes(scenes, max_duration=30, min_duration=5):
    """Split long scenes into short-friendly chunks."""
    chunks = []
    for scene in scenes:
        start = float(scene['start'])
        end = float(scene['end'])
        original_index = scene.get('index', len(chunks))
        part = 1

        while start < end:
            chunk_end = min(start + max_duration, end)
            duration = chunk_end - start

            if duration < min_duration:
                if chunks and chunks[-1].get('original_index') == original_index:
                    chunks[-1]['end'] = round(end, 2)
                    chunks[-1]['duration'] = round(chunks[-1]['end'] - chunks[-1]['start'], 2)
                    chunks[-1]['end_tc'] = fmt_tc(end)
                break

            chunks.append({
                'index': len(chunks),
                'original_index': original_index,
                'part': part,
                'start': round(start, 2),
                'end': round(chunk_end, 2),
                'duration': round(duration, 2),
                'start_tc': fmt_tc(start),
                'end_tc': fmt_tc(chunk_end),
            })
            start = chunk_end
            part += 1

    return chunks


def detect_face_center_x(video_path, timestamp):
    """Detect face in frame at timestamp, return center X coordinate or None."""
    try:
        import cv2
    except ImportError:
        return None
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        cap.release()
        return None
    target = max(0, int(timestamp * fps) - 1)
    cap.set(cv2.CAP_PROP_POS_FRAMES, target)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, 1.1, 4, minSize=(60, 60))
    if len(faces) > 0:
        largest = max(faces, key=lambda f: f[2] * f[3])
        return largest[0] + largest[2] // 2
    return None


def build_crop_filter(video_path, timestamp, vw, vh):
    crop_w = int(vh * 9 / 16)
    if crop_w > vw:
        crop_w = vw
    crop_x = (vw - crop_w) // 2
    face_cx = detect_face_center_x(video_path, timestamp)
    if face_cx is not None:
        crop_x = max(0, min(face_cx - crop_w // 2, vw - crop_w))
    return f'crop={crop_w}:{vh}:{crop_x}:0,scale=1080:1920'


def parse_ffmpeg_time(value):
    try:
        h, m, s = value.split(':')
        return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        return 0


def generate_short(video_path, start, end, output_path, smart_crop=True, progress_callback=None):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = end - start
    vw, vh = get_video_dimensions(video_path)
    if smart_crop:
        vf = build_crop_filter(video_path, start + 0.5, vw, vh)
    else:
        crop_w = min(int(vh * 9 / 16), vw)
        crop_x = (vw - crop_w) // 2
        vf = f'crop={crop_w}:{vh}:{crop_x}:0,scale=1080:1920'
    cmd = [
        'ffmpeg', '-v', 'error', '-i', str(video_path),
        '-ss', str(start), '-t', str(duration),
        '-vf', vf, '-c:a', 'aac',
        '-progress', 'pipe:1', '-nostats',
        '-y', str(output_path)
    ]
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        if process.stdout:
            for line in process.stdout:
                line = line.strip()
                if not line or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                current = 0
                if key in ('out_time_ms', 'out_time_us'):
                    try:
                        current = float(value) / 1_000_000
                    except ValueError:
                        current = 0
                elif key == 'out_time':
                    current = parse_ffmpeg_time(value)

                if current and progress_callback and duration > 0:
                    progress_callback(min(100, (current / duration) * 100))

        return process.wait(timeout=30) == 0
    except Exception:
        return False


def generate_scene_thumbnail(video_path, timestamp, output_path, size=320):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run([
            'ffmpeg', '-i', str(video_path),
            '-ss', str(max(0, timestamp)),
            '-vframes', '1', '-vf', f'scale={size}:-1',
            '-y', str(output_path)
        ], capture_output=True, timeout=30)
        return output_path.exists()
    except Exception:
        return False


def generate_all_shorts(video_path, output_dir, scenes, smart_crop=True):
    results = []
    video_stem = Path(video_path).stem
    for scene in scenes:
        out_name = f"short_{video_stem}_cena{scene['index']+1}.mp4"
        out_path = Path(output_dir) / out_name
        ok = generate_short(video_path, scene['start'], scene['end'], out_path, smart_crop)
        results.append({**scene, 'file': out_name, 'success': ok})
    return results
