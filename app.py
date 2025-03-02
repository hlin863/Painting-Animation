from flask import Flask, render_template, request, send_file, redirect, url_for, abort
import os
import subprocess
from werkzeug.utils import secure_filename, safe_join

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
OUTPUT_FOLDER = os.path.join(os.getcwd(), 'outputs')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# SadTalker command runner
def generate_talking_face(image_path, audio_path, output_path):
    command = [
        'python', 'inference.py',
        '--driven_audio', audio_path,
        '--source_image', image_path,
        '--preprocess', 'full',
        '--result_dir', output_path
    ]
    subprocess.run(command, cwd='SadTalker')

import shutil

def convert_video_to_web_format_in_place(video_folder, video_file):
    """Convert video to H.264 + AAC (browser-compatible) and overwrite the original file."""
    input_path = os.path.join(video_folder, video_file)
    temp_path = os.path.join(video_folder, "temp_" + video_file)

    command = [
        'ffmpeg',
        '-i', input_path,
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-strict', 'experimental',
        temp_path
    ]

    subprocess.run(command, check=True)

    # Replace the original file with the converted file
    shutil.move(temp_path, input_path)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        image = request.files['image']
        audio = request.files['audio']

        if image and audio:
            image_filename = secure_filename(image.filename)
            audio_filename = secure_filename(audio.filename)

            image_path = os.path.join(UPLOAD_FOLDER, image_filename)
            audio_path = os.path.join(UPLOAD_FOLDER, audio_filename)

            image.save(image_path)
            audio.save(audio_path)

            # Output directory (for this video)
            video_output_dir = os.path.join(OUTPUT_FOLDER, image_filename.split('.')[0])
            os.makedirs(video_output_dir, exist_ok=True)

            # Run SadTalker
            generate_talking_face(image_path, audio_path, video_output_dir)

            # Find the output video file (SadTalker saves mp4 in result_dir)
            output_video = None
            for file in os.listdir(video_output_dir):
                if file.endswith('.mp4'):
                    output_video = file
                    break

            if output_video:

                convert_video_to_web_format_in_place(video_output_dir, output_video)
                
                return redirect(url_for('result', video_folder=video_output_dir, video_file=output_video))

    return render_template('index.html')


@app.route('/result')
def result():
    video_folder = request.args.get('video_folder')
    video_file = request.args.get('video_file')
    return render_template('result.html', video_folder=video_folder, video_file=video_file)

@app.route('/download/<path:filepath>')
def download_file(filepath):
    return send_file(filepath, as_attachment=True)

@app.route('/outputs/<path:filepath>')
def serve_video(filepath):
    print(f"Serving video file: {filepath}")
    return send_file(filepath, mimetype='video/mp4')

if __name__ == '__main__':
    app.run(debug=True)