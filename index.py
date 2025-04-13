import logging
import os
import tempfile
import requests
import asyncio
import subprocess
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
    await update.message.reply_text("Bienvenue ! Envoie-moi un message texte ou vocal.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await send_to_gemini(update, user_text)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice_file = await update.message.voice.get_file()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as ogg_file:
        await voice_file.download_to_drive(ogg_file.name)
        ogg_path = ogg_file.name

    wav_path = ogg_path.replace(".ogg", ".wav")
    subprocess.run(["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path])
    result = whisper_model.transcribe(wav_path)
    text = result["text"]

    await update.message.reply_text(f"[Transcrit]: {text}")
    await send_to_gemini(update, text)

    os.remove(ogg_path)
    os.remove(wav_path)

async def send_to_gemini(update: Update, prompt: str):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        try:
            reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except:
            reply = "Erreur : réponse Gemini invalide."
    else:
        reply = "Erreur avec l’API Gemini."

    await update.message.reply_text(reply)

# --- MAIN ---
def main():
    app = ApplicationBuilder().token(TELEGRAM_API_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    print("Bot lancé.")
    app.run_polling()

if __name__ == '__main__':
    main()
