import logging
import os
import tempfile
import requests
import subprocess
import whisper
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# --- CONFIGURATION ---
TELEGRAM_API_TOKEN = "7728370298:AAFiwKzKcsaMBAzQc1VPc9XYosMXpvxho3s"  # À sécuriser dans des variables d'environnement
GEMINI_API_KEY = "AIzaSyAArErZGDDJx7DJwExgY_pPWmN7Tjai8nk"  # À sécuriser dans des variables d'environnement
WHISPER_MODEL = "tiny"  # ou "base", "small", "medium", "large" selon vos besoins

# --- INITIALISATION ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Charge le modèle Whisper une seule fois au démarrage
try:
    whisper_model = whisper.load_model(WHISPER_MODEL)
    logger.info(f"Modèle Whisper {WHISPER_MODEL} chargé avec succès")
except Exception as e:
    logger.error(f"Erreur lors du chargement du modèle Whisper: {e}")
    raise

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /start"""
    await update.message.reply_text("Bienvenue ! Envoie-moi un message texte ou vocal et je te répondrai.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les messages texte"""
    user_text = update.message.text
    logger.info(f"Message texte reçu: {user_text}")
    await send_to_gemini(update, user_text)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les messages vocaux"""
    logger.info("Message vocal reçu")
    
    try:
        # Télécharge le fichier vocal
        voice_file = await update.message.voice.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as ogg_file:
            ogg_path = ogg_file.name
            await voice_file.download_to_drive(ogg_path)
        
        # Convertit en WAV
        wav_path = ogg_path.replace(".ogg", ".wav")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur FFmpeg: {e.stderr.decode()}")
            await update.message.reply_text("Désolé, je n'ai pas pu traiter le message vocal.")
            return
        
        # Transcription avec Whisper
        try:
            result = whisper_model.transcribe(wav_path)
            text = result["text"]
            logger.info(f"Transcription: {text}")
            
            if not text.strip():
                await update.message.reply_text("Je n'ai pas pu comprendre le message vocal.")
                return
                
            await update.message.reply_text(f"Transcription: {text}")
            await send_to_gemini(update, text)
            
        except Exception as e:
            logger.error(f"Erreur de transcription: {e}")
            await update.message.reply_text("Désolé, une erreur s'est produite lors de la transcription.")
            
    finally:
        # Nettoyage des fichiers temporaires
        if 'ogg_path' in locals() and os.path.exists(ogg_path):
            os.remove(ogg_path)
        if 'wav_path' in locals() and os.path.exists(wav_path):
            os.remove(wav_path)

async def send_to_gemini(update: Update, prompt: str):
    """Envoie le prompt à l'API Gemini et renvoie la réponse"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if "candidates" not in data or not data["candidates"]:
            raise ValueError("Réponse API invalide: pas de candidat")
            
        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        await update.message.reply_text(reply)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur API Gemini: {e}")
        await update.message.reply_text("Désolé, je rencontre des problèmes avec l'API Gemini.")
    except (KeyError, IndexError, ValueError) as e:
        logger.error(f"Erreur de traitement de la réponse Gemini: {e}")
        await update.message.reply_text("Désolé, je n'ai pas pu comprendre la réponse de Gemini.")
    except Exception as e:
        logger.error(f"Erreur inattendue: {e}")
        await update.message.reply_text("Désolé, une erreur inattendue s'est produite.")

# --- MAIN ---
def main():
    """Point d'entrée principal"""
    try:
        app = ApplicationBuilder().token(TELEGRAM_API_TOKEN).build()
        
        # Gestionnaires de commandes
        app.add_handler(CommandHandler("start", start))
        
        # Gestionnaires de messages
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        app.add_handler(MessageHandler(filters.VOICE, handle_voice))
        
        logger.info("Bot lancé et en attente de messages...")
        app.run_polling()
        
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du bot: {e}")

if __name__ == '__main__':
    main()
