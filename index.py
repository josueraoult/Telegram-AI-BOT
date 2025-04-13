import logging
import os
import tempfile

import requests
import whisper
from TTS.api import TTS
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

from config import TELEGRAM_API_TOKEN, GEMINI_API_KEY, WHISPER_MODEL, COQUI_MODEL

# Initialisation
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Charger Whisper (transcription)
whisper_model = whisper.load_model(WHISPER_MODEL)

# Charger Coqui TTS (synthèse vocale)
tts = TTS(model_name=COQUI_MODEL, progress_bar=False, gpu=False)

# Start
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Salut ! Envoie-moi un message texte ou vocal et je te répondrai avec l'IA Gemini.")

# Traitement audio
def audio_handler(update: Update, context: CallbackContext) -> None:
    voice = update.message.voice.get_file()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tf:
        voice.download(out=tf)
        ogg_path = tf.name

    wav_path = ogg_path.replace(".ogg", ".wav")
    os.system(f"ffmpeg -i {ogg_path} -ar 16000 -ac 1 -c:a pcm_s16le {wav_path}")

    result = whisper_model.transcribe(wav_path)
    text = result["text"]
    update.message.reply_text(f"Transcription : {text}")
    process_text(update, text)

    os.remove(ogg_path)
    os.remove(wav_path)

# Traitement texte
def text_handler(update: Update, context: CallbackContext) -> None:
    text = update.message.text
    process_text(update, text)

# Requête Gemini
def process_text(update: Update, prompt: str) -> None:
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    full_url = f"{url}?key={GEMINI_API_KEY}"
    response = requests.post(full_url, headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json()
        try:
            text_response = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            text_response = "Erreur de traitement dans la réponse de Gemini."

        update.message.reply_text(text_response)

        # Synthèse vocale avec Coqui TTS
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf_audio:
            audio_path = tf_audio.name
            tts.tts_to_file(text=text_response, file_path=audio_path)
            update.message.reply_voice(voice=open(audio_path, "rb"))
            os.remove(audio_path)
    else:
        update.message.reply_text("Erreur lors de la requête à Gemini.")

# Gestion des erreurs
def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(f"Erreur : {context.error}")

# Lancement du bot
def main():
    updater = Updater(TELEGRAM_API_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.voice, audio_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_handler))
    dp.add_error_handler(error_handler)

    print("Bot démarré.")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()