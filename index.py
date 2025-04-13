import logging
import os
import tempfile
import requests
import whisper
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# --- CONFIGURATION ---
TELEGRAM_API_TOKEN = "7728370298:AAFiwKzKcsaMBAzQc1VPc9XYosMXpvxho3s"
GEMINI_API_KEY = "AIzaSyAArErZGDDJx7DJwExgY_pPWmN7Tjai8nk"
WHISPER_MODEL = "tiny"

# --- INITIALISATION ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
whisper_model = whisper.load_model(WHISPER_MODEL)

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salut ! Envoie-moi un message texte ou vocal, et je te réponds avec Gemini.")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    await send_to_gemini(update, prompt)

async def audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = await update.message.voice.get_file()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tf:
        await voice.download_to_drive(tf.name)
        ogg_path = tf.name

    wav_path = ogg_path.replace(".ogg", ".wav")
    os.system(f"ffmpeg -i {ogg_path} -ar 16000 -ac 1 -c:a pcm_s16le {wav_path}")

    result = whisper_model.transcribe(wav_path)
    text = result["text"]

    await update.message.reply_text(f"[Transcription]: {text}")
    await send_to_gemini(update, text)

    os.remove(ogg_path)
    os.remove(wav_path)

async def send_to_gemini(update: Update, prompt: str):
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
    else:
        reply = "Erreur avec Gemini API."

    await update.message.reply_text(reply)

# --- MAIN ---
def main():
    app = ApplicationBuilder().token(TELEGRAM_API_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.VOICE, audio_handler))

    print("Bot prêt.")
    app.run_polling()

if __name__ == '__main__':
    main()
