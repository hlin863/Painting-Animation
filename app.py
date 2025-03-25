from flask import Flask, render_template, request, send_file, redirect, url_for, abort
import os
import subprocess
from werkzeug.utils import secure_filename, safe_join
from pydub import AudioSegment
import asyncio
import edge_tts
import sys

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
OUTPUT_FOLDER = os.path.join(os.getcwd(), 'outputs')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Absolute path to SadTalker root folder
SADTALKER_PATH = os.path.abspath(os.path.join(os.getcwd(), 'SadTalker'))

# Add SadTalker root to the Python path
if SADTALKER_PATH not in sys.path:
    sys.path.insert(0, SADTALKER_PATH)

# SadTalker command runner
def generate_talking_face(image_path, audio_path, output_path):
    command = [
        'python', 'inference.py',
        '--driven_audio', audio_path,
        '--source_image', image_path,
        '--preprocess', 'full',
        '--result_dir', output_path,
        '--still',
        '--enhancer', 'gfpgan',
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

@app.route('/gallery')
def gallery():
    video_data = []
    gallery_path = r"C:\Users\haoch\Desktop\Painting-Animation\outputs"
    for root, _, files in os.walk(gallery_path):
        for file in files:
            if file.endswith('.mp4'):
                
                rel_folder = os.path.relpath(root, gallery_path).replace('\\', '/')
        
                full_path = os.path.join(root, file)
                video_data.append({
                    'folder': rel_folder,
                    'file': file,
                    'full_path': full_path  # Optional, for internal logs
                })
    return render_template('gallery.html', videos=video_data)

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
            print("Trying to save audio to:", audio_path)
            print("File exists already?", os.path.exists(audio_path))
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


async def generate_tts(text, output_path, voice="zh-CN-YunyangNeural"):
    """
    Generate text-to-speech using EdgeTTS with a selected voice.
    Saves the output audio file.
    """
    communicate = edge_tts.Communicate(text, voice, rate='-25%')
    await communicate.save(output_path)

def generate_talking_face_from_text(image_path, text, output_path):
    """
    Generate talking face video from an image and input text.
    - Uses gTTS for text-to-speech.
    - Uses SadTalker for face animation.
    """
    # Step 1 - Convert text to speech
    tts_audio_path = os.path.join(output_path, "generated_speech.wav")

    # Use EdgeTTS to generate male voice
    asyncio.run(generate_tts(text, tts_audio_path))

    # Use SadTalker to generate video
    generate_talking_face(image_path, tts_audio_path, output_path)

@app.route('/text_talking_face', methods=['POST'])
def text_talking_face():
    if request.method == 'POST':
        image = request.files['image']
        text = request.form.get('text', '')

        if not text:
            return "Text input is required.", 400

        if image:
            image_filename = secure_filename(image.filename)
            image_path = os.path.join(UPLOAD_FOLDER, image_filename)
            image.save(image_path)

            video_output_dir = os.path.join(OUTPUT_FOLDER, 'text_talking_faces', image_filename.split('.')[0])
            os.makedirs(video_output_dir, exist_ok=True)

            # Generate talking face from image + text
            generate_talking_face_from_text(image_path, text, video_output_dir)

            # Locate the resulting video
            output_video = None
            for file in os.listdir(video_output_dir):
                if file.endswith('.mp4'):
                    output_video = file
                    break

            if output_video:
                # Convert video if needed
                convert_video_to_web_format_in_place(video_output_dir, output_video)

                return send_file(os.path.join(video_output_dir, output_video), as_attachment=True)

    return redirect(url_for('index'))

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

@app.route('/crop_audio', methods=['GET', 'POST'])
def crop_audio():
    if request.method == 'POST':
        audio = request.files['audio']
        start_time = float(request.form['start_time'])
        end_time = float(request.form['end_time'])

        if audio:
            audio_filename = secure_filename(audio.filename)
            audio_path = os.path.join(UPLOAD_FOLDER, audio_filename)
            cropped_path = os.path.join(UPLOAD_FOLDER, f"cropped_{audio_filename}")

            audio.save(audio_path)

            # Crop the audio using pydub
            sound = AudioSegment.from_file(audio_path)
            cropped_sound = sound[start_time * 1000:end_time * 1000]  # pydub works in milliseconds
            cropped_sound.export(cropped_path, format="wav")

            return send_file(cropped_path, as_attachment=True)

    return render_template('crop_audio.html')

@app.route('/reanimate', methods=['GET', 'POST'])
def reanimate():
    if request.method == 'POST':
        image = request.files.get('image')
        audio = request.files.get('audio')
        text = request.form.get('text', '').strip()
        voice = request.form.get('voice', "zh-CN-YunyangNeural")

        if not image:
            return "Image is required.", 400

        # Save the uploaded image
        image_filename = secure_filename(image.filename)
        image_path = os.path.join(UPLOAD_FOLDER, image_filename)
        image.save(image_path)

        # Create output folder for the new video
        video_output_dir = os.path.join(OUTPUT_FOLDER, image_filename.split('.')[0])
        os.makedirs(video_output_dir, exist_ok=True)

        if audio:
            # Save uploaded audio
            audio_path = os.path.join(UPLOAD_FOLDER, secure_filename(audio.filename))
            audio.save(audio_path)

        elif text:
            # Generate talking face with TTS audio
            # Generate TTS audio from text using the selected voice
            tts_audio_path = os.path.join(video_output_dir, "generated_speech.wav")
            asyncio.run(generate_tts(text, tts_audio_path, voice))
            audio_path = tts_audio_path
            print(f"Generated TTS audio at: {tts_audio_path}")
        else:
            return "Error: Either an audio file or text input is required.", 400
        
        generate_talking_face(image_path, audio_path, video_output_dir)

        # Find the new video
        output_video = None
        for file in os.listdir(video_output_dir):
            if file.endswith('.mp4'):
                output_video = file
                break

        if output_video:
            convert_video_to_web_format_in_place(video_output_dir, output_video)
            return redirect(url_for('result', video_folder=video_output_dir, video_file=output_video))

        return "Failed to generate talking face.", 500

    return render_template('reanimate.html')

if __name__ == '__main__':
    app.run(debug=True)