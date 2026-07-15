import os
import time
import shutil
import tempfile
import uuid
from flask import Flask, render_template, request, send_file, jsonify, abort
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)


def cleanup_old_folders():
    """Supprime les dossiers temporaires de plus d'une heure."""
    base = tempfile.gettempdir()
    for name in os.listdir(base):
        if name.startswith('tiktok_dl_'):
            path = os.path.join(base, name)
            if os.path.isdir(path) and time.time() - os.path.getctime(path) > 3600:
                shutil.rmtree(path, ignore_errors=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/download', methods=['POST'])
def download():
    cleanup_old_folders()

    data = request.get_json(silent=True) or {}
    urls_raw = (data.get('urls') or '').strip()
    urls = [u.strip() for u in urls_raw.splitlines() if u.strip()]

    if not urls:
        return jsonify({'error': 'NO_URLS'}), 400

    req_id = str(uuid.uuid4())
    temp_dir = os.path.join(tempfile.gettempdir(), f'tiktok_dl_{req_id}')
    os.makedirs(temp_dir, exist_ok=True)

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best',
        'format_sort': ['res:2160', 'vcodec:h264', 'ext:mp4:m4a'],
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Referer': 'https://www.tiktok.com/',
        },
    }

    results = []
    failed = []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for i, url in enumerate(urls):

            try:
                info = ydl.extract_info(url, download=True)
                vid_id = info.get('id', '')
                video_file = None
                for f in os.listdir(temp_dir):
                    if f.startswith(vid_id):
                        video_file = f
                        break

                if not video_file:
                    failed.append({'url': url, 'reason': 'FILE_NOT_FOUND'})
                    continue

                file_size = os.path.getsize(os.path.join(temp_dir, video_file))
                height = info.get('height', 0) or 0

                if height >= 2160:
                    quality = '4K'
                elif height >= 1080:
                    quality = '1080p'
                elif height >= 720:
                    quality = '720p'
                else:
                    quality = f'{height}p' if height else 'HD'

                results.append({
                    'download_url': f'/file/{req_id}/{video_file}',
                    'filename': video_file,
                    'title': info.get('title', 'Video') or 'Video',
                    'author': info.get('uploader', info.get('creator', '')) or '',
                    'thumbnail': info.get('thumbnail', '') or '',
                    'quality': quality,
                    'size': f'{file_size / (1024*1024):.1f} MB' if file_size > 1024*1024
                            else f'{file_size / 1024:.0f} KB',
                })

            except Exception as e:
                print(f"[ERROR] {url}: {e}")
                failed.append({'url': url, 'reason': 'DOWNLOAD_FAILED'})

            if i < len(urls) - 1:
                time.sleep(1.5)

    if not results:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({'error': 'NO_VIDEOS', 'failed': failed}), 400

    return jsonify({
        'success': True,
        'videos': results,
        'failed': failed,
        'total': len(urls),
    })


@app.route('/file/<req_id>/<filename>')
def serve_file(req_id, filename):
    if '..' in req_id or '..' in filename or '/' in filename:
        abort(400)

    filepath = os.path.join(tempfile.gettempdir(), f'tiktok_dl_{req_id}', filename)
    if not os.path.exists(filepath):
        abort(404)

    return send_file(
        filepath,
        mimetype='video/mp4',
        as_attachment=True,
        download_name=filename,
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7860))
    app.run(debug=os.environ.get('FLASK_DEBUG', 'true').lower() == 'true',
            host='0.0.0.0', port=port)
