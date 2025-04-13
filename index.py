import os
import logging
import tempfile
import requests
from flask import Flask
import telebot
from telebot.types import Message
import whisper
import subprocess

# Configuration
TELEGRAM_API_TOKEN = "7728370298:AAFiwKzKcsaMBAzQc1VPc9XYosMXpvxho3s"
GEMINI_API_KEY = ":AIzaSyAArErZGDDJx7DJwExgY_pPWmN7Tjai8nk"
WHISPER_MODEL = "tiny"

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialisation du bot
bot = telebot.TeleBot(TELEGRAM_API_TOKEN)

# Chargement du modèle Whisper
whisper_model = whisper.load_model(WHISPER_MODEL)

# Serveur web simple (Flask)
app = Flask(__name__)

@app.route("/")
def index():
    return "Le bot fonctionne."

# Commande /start
@bot.message_handler(commands=["start"])
def handle_start(message: Message):
    bot.reply_to(message, "Bienvenue ! Envoie-moi un texte ou un message vocal, et je te répondrai.")

# Gestion des messages texte
@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message: Message):
    send_to_gemini(message, message.text)

# Gestion des messages vocaux
@bot.message_handler(content_types=["voice"])
def handle_voice(message: Message):
    try:
        file_info = bot.get_file(message.voice.file_id)
        file = bot.download_file(file_info.file_path)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as f:
            f.write(file)
            ogg_path = f.name

        wav_path = ogg_path.replace(".ogg", ".wav")
        subprocess.run([
            "ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path
        ], check=True)

        result = whisper_model.transcribe(wav_path)
        text = result["text"]
        bot.reply_to(message, f"[Transcription]: {text}")
        send_to_gemini(message, text)

        os.remove(ogg_path)
        os.remove(wav_path)

    except Exception as e:
        logger.error(f"Erreur audio : {e}")
        bot.reply_to(message, "Erreur lors du traitement du message vocal.")

# Envoi à Gemini API
def send_to_gemini(message: Message, prompt: str):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        r = requests.post(url, headers=headers, json=payload)
        r.raise_for_status()
        response_text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        bot.reply_to(message, response_text)
    except Exception as e:
        logger.error(f"Erreur Gemini : {e}")
        bot.reply_to(message, "Erreur avec l'API Gemini.")

# Lancement du bot et du serveur web
if __name__ == "__main__":
    from threading import Thread

    # Démarrer le serveur web
    def run_web():
        app.run(host="0.0.0.0", port=8080)

    Thread(target=run_web).start()

    # Lancer le bot
    logger.info("Bot lancé avec telebot.")
    bot.infinity_polling()
