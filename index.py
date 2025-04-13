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
WHISPER_MODEL = "tiny"

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Vérification des tokens
if not TELEGRAM_API_TOKEN:
    raise ValueError("TELEGRAM_API_TOKEN manquant !")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY manquant !")

# Initialisation du bot
bot = telebot.TeleBot(TELEGRAM_API_TOKEN)

# Vérification du token
try:
    me = bot.get_me()
    logger.info(f"Bot connecté : @{me.username}")
except Exception as e:
    logger.error(f"Échec de connexion à Telegram : {e}")
    exit()

# Chargement du modèle Whisper
logger.info("Chargement du modèle Whisper...")
whisper_model = whisper.load_model(WHISPER_MODEL)
logger.info("Modèle Whisper chargé.")

# Serveur Flask pour Render
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
    logger.info(f"Texte reçu : {message.text}")
    send_to_gemini(message, message.text)

# Vocal
@bot.message_handler(content_types=["voice"])
def handle_voice(message: Message):
    logger.info("Message vocal reçu.")
    bot.reply_to(message, "Message vocal reçu, traitement en cours...")
    
    try:
        file_info = bot.get_file(message.voice.file_id)
        logger.info(f"Fichier audio : {file_info.file_path}")
        file = bot.download_file(file_info.file_path)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as f:
            f.write(file)
            ogg_path = f.name
        logger.info(f"Audio téléchargé : {ogg_path}")

        wav_path = ogg_path.replace(".ogg", ".wav")
        ffmpeg_command = [
            "ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path
        ]
        logger.info(f"Conversion avec ffmpeg : {' '.join(ffmpeg_command)}")
        subprocess.run(ffmpeg_command, check=True)

        logger.info("Transcription en cours...")
        result = whisper_model.transcribe(wav_path)
        text = result["text"]
        logger.info(f"Transcription : {text}")
        bot.reply_to(message, f"[Transcription]: {text}")
        send_to_gemini(message, text)

    except Exception as e:
        logger.error(f"Erreur audio : {e}")
        bot.reply_to(message, f"Erreur audio : {e}")
    finally:
        try:
            if os.path.exists(ogg_path): os.remove(ogg_path)
            if os.path.exists(wav_path): os.remove(wav_path)
        except Exception as e:
            logger.warning(f"Erreur suppression fichier : {e}")

# Envoi à Gemini
def send_to_gemini(message: Message, prompt: str):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        logger.info(f"Envoi à Gemini : {prompt}")
        r = requests.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        logger.info(f"Réponse Gemini brute : {data}")
        response_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "Aucune réponse.")
        bot.reply_to(message, f"[Gemini]: {response_text}")
    except Exception as e:
        logger.error(f"Erreur Gemini : {e}")
        bot.reply_to(message, "Erreur avec l'API Gemini.")

# Lancer serveur + bot
if __name__ == "__main__":
    def run_web():
        port = int(os.environ.get("PORT", 8080))
        logger.info(f"Lancement du serveur Flask sur le port {port}")
        app.run(host="0.0.0.0", port=port)

    Thread(target=run_web).start()
    logger.info("Bot lancé avec polling.")
    bot.infinity_polling()
