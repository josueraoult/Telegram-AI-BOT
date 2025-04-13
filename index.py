import os
import logging
import tempfile
import requests
from flask import Flask
import telebot
from telebot.types import Message
import whisper
import subprocess
from threading import Thread
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()
TELEGRAM_API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Vérification du token
if not TELEGRAM_API_TOKEN:
    raise ValueError("TELEGRAM_API_TOKEN manquant !")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY manquant !")

# Initialisation du bot
bot = telebot.TeleBot(TELEGRAM_API_TOKEN)

# Vérification que le token fonctionne
try:
    me = bot.get_me()
    logger.info(f"Bot connecté : @{me.username}")
except Exception as e:
    logger.error(f"Échec de connexion à Telegram : {e}")
    exit()

# Chargement du modèle Whisper (correct pour CPU)
whisper_model = whisper.load_model("tiny", device="cpu", fp16=False)

# Serveur web (utile pour Render)
app = Flask(__name__)
@app.route("/")
def index():
    return "Le bot fonctionne."

# Commande /start
@bot.message_handler(commands=["start"])
def handle_start(message: Message):
    bot.reply_to(message, "Bienvenue ! Envoie-moi un texte ou un message vocal, et je te répondrai.")

# Texte
@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message: Message):
    send_to_gemini(message, message.text)

# Vocal
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

# Envoi à Gemini (modèle flash)
def send_to_gemini(message: Message, prompt: str):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        response_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "Aucune réponse.")
        bot.reply_to(message, f"[Gemini]: {response_text}")
    except requests.exceptions.HTTPError as err:
        logger.error(f"Erreur Gemini : {err}")
        bot.reply_to(message, "Erreur avec l'API Gemini.")
    except Exception as e:
        logger.error(f"Erreur générique : {e}")
        bot.reply_to(message, "Une erreur est survenue.")

# Lancer serveur + bot
if __name__ == "__main__":
    def run_web():
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

    Thread(target=run_web).start()
    logger.info("Bot lancé avec polling.")
    bot.infinity_polling()
