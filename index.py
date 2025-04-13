import logging
import os
import tempfile
import requests
import whisper
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# --- CONFIGURATION ---
# Clés API et paramètres intégrés directement ici
TELEGRAM_API_TOKEN = "7728370298:AAFiwKzKcsaMBAzQc1VPc9XYosMXpvxho3s"
GEMINI_API_KEY = "AIzaSyAArErZGDDJx7DJwExgY_pPWmN7Tjai8nk"
WHISPER_MODEL = "tiny"

# --- INITIALISATION ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Charger le modèle Whisper (STT)
whisper_model = whisper.load_model(WHISPER_MODEL)

# --- COMMANDES & HANDLERS ---

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Salut ! Envoie-moi un message texte ou vocal, et je te réponds avec Gemini.")

def text_handler(update: Update, context: CallbackContext) -> None:
    prompt = update.message.text
    send_to_gemini(update, prompt)

def audio_handler(update: Update, context: CallbackContext) -> None:
    voice = update.message.voice.get_file()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tf:
        voice.download(out=tf)
        ogg_path = tf.name

    wav_path = ogg_path.replace(".ogg", ".wav")
    os.system(f"ffmpeg -i {ogg_path} -ar 16000 -ac 1 -c:a pcm_s16le {wav_path}")

    result = whisper_model.transcribe(wav_path)
    text = result["text"]

    update.message.reply_text(f"[Transcription]: {text}")
    send_to_gemini(update, text)

    os.remove(ogg_path)
    os.remove(wav_path)

def send_to_gemini(update: Update, prompt: str) -> None:
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    full_url = f"{url}?key={GEMINI_API_KEY}"
    r = requests.post(full_url, headers=headers, json=payload)

    if r.status_code == 200:
        try:
            reply = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            reply = "Réponse invalide de Gemini."
        update.message.reply_text(reply)
    else:
        update.message.reply_text("Erreur avec Gemini API.")

def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(f"Erreur : {context.error}")

# --- LANCEMENT BOT ---
def main():
    updater = Updater(TELEGRAM_API_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_handler))
    dp.add_handler(MessageHandler(Filters.voice, audio_handler))
    dp.add_error_handler(error_handler)

    print("Bot prêt.")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
