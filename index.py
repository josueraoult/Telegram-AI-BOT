import telebot
import requests
import io
import base64
from flask import Flask

# ====== CLÉS API ======
TELEGRAM_TOKEN = "7728370298:AAH2LROduZRfymFowV3m4c9NE9hlx7ZzgKA"
RESEMBLE_API_KEY = "ev6lZTrSDKV5TK2toXibxQtt"
GEMINI_API_KEY = "AIzaSyAHLpehdEmUGOWi8t6aZMFd7KOt9GVVltQ"

VOICE_UUID = "79eb7953"
PROJECT_UUID = "cc1eb39a"

# Initialisation du bot
try:
    bot = telebot.TeleBot(TELEGRAM_TOKEN)
    print("Bot initialisé avec succès!")
except Exception as e:
    print(f"Erreur lors de l'initialisation du bot: {e}")
    raise

user_state = {}

# ====== TEXT-TO-SPEECH ======
def text_to_speech(text):
    url = f"https://app.resemble.ai/api/v2/projects/{PROJECT_UUID}/clips"
    headers = {
        "Authorization": f"Token token={RESEMBLE_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "voice_uuid": VOICE_UUID,
        "data": text,
        "output_format": "wav",
        "sample_rate": 48000,
        "precision": "PCM_16"
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()

        audio_base64 = response.json().get("audio_content")
        if audio_base64:
            audio_bytes = base64.b64decode(audio_base64)
            audio_io = io.BytesIO(audio_bytes)
            files = {'fileToUpload': ('audio.wav', audio_io, 'audio/wav')}
            r = requests.post("https://catbox.moe/user/api.php", 
                            data={"reqtype": "fileupload"}, 
                            files=files)
            return r.text.strip()
    except Exception as e:
        print(f"Erreur TTS: {e}")
    return None

# ====== AUDIO -> TEXTE ======
def audio_to_text(audio_file):
    try:
        with open(audio_file, "rb") as f:
            audio_content = f.read()

        response = requests.post(
            f"https://speech.googleapis.com/v1/speech:recognize?key={GEMINI_API_KEY}",
            json={
                "config": {"encoding": "OGG_OPUS", "languageCode": "fr-FR"},
                "audio": {"content": base64.b64encode(audio_content).decode("utf-8")}
            }
        )
        response.raise_for_status()

        results = response.json().get("results", [])
        if results:
            return results[0]["alternatives"][0]["transcript"]
    except Exception as e:
        print(f"Erreur STT: {e}")
    return None

# ====== GPT AI VIA GEMINI ======
def gemini_response(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    try:
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Erreur Gemini: {e}")
        return "Erreur lors de la génération."

# ====== BOT TELEGRAM ======
@bot.message_handler(commands=['start'])
def start(message):
    user_state[message.chat.id] = "lang_select"
    bot.send_message(message.chat.id, "Choisis ta langue / Choose your language:\nFR / EN")

@bot.message_handler(func=lambda msg: user_state.get(msg.chat.id) == "lang_select")
def set_language(message):
    lang = message.text.strip().upper()
    if lang in ['FR', 'EN']:
        user_state[message.chat.id] = {"lang": lang, "mode": None}
        bot.send_message(message.chat.id, f"Langue définie sur {lang}. Tape /menu pour voir les options.")
    else:
        bot.send_message(message.chat.id, "Langue invalide. Choisis FR ou EN.")

@bot.message_handler(commands=['menu'])
def menu(message):
    state = user_state.get(message.chat.id, {})
    if isinstance(state, dict):
        lang = state.get("lang", "FR")
        if lang == "FR":
            bot.send_message(message.chat.id, "Menu:\n1. GPT AI\n2. Quitter")
        else:
            bot.send_message(message.chat.id, "Menu:\n1. GPT AI\n2. Exit")
        user_state[message.chat.id]["mode"] = "menu"

@bot.message_handler(func=lambda msg: isinstance(user_state.get(msg.chat.id), dict) and user_state[msg.chat.id].get("mode") == "menu")
def handle_menu_choice(message):
    choice = message.text.strip()
    lang = user_state[message.chat.id]["lang"]

    if choice == "1":
        user_state[message.chat.id]["mode"] = "gpt"
        if lang == "FR":
            bot.send_message(message.chat.id, "Tu es maintenant dans le mode GPT AI. Envoie un texte ou un audio.")
        else:
            bot.send_message(message.chat.id, "You're now in GPT AI mode. Send text or audio.")
    else:
        user_state[message.chat.id]["mode"] = None
        bot.send_message(message.chat.id, "Bye!")

@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    state = user_state.get(message.chat.id, {})
    if isinstance(state, dict) and state.get("mode") == "gpt":
        try:
            file_info = bot.get_file(message.voice.file_id)
            file = requests.get(f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}")
            
            with open("audio.ogg", "wb") as f:
                f.write(file.content)

            text = audio_to_text("audio.ogg")
            if text:
                response = gemini_response(text)
                audio_url = text_to_speech(response)
                bot.send_message(message.chat.id, response)
                if audio_url:
                    bot.send_voice(message.chat.id, audio=requests.get(audio_url).content)
            else:
                bot.send_message(message.chat.id, "Impossible de comprendre l'audio.")
        except Exception as e:
            print(f"Erreur voice: {e}")
            bot.send_message(message.chat.id, "Une erreur est survenue lors du traitement de l'audio.")

@bot.message_handler(func=lambda msg: isinstance(user_state.get(msg.chat.id), dict) and user_state[msg.chat.id].get("mode") == "gpt")
def handle_text(message):
    try:
        response = gemini_response(message.text)
        audio_url = text_to_speech(response)
        bot.send_message(message.chat.id, response)
        if audio_url:
            bot.send_voice(message.chat.id, audio=requests.get(audio_url).content)
    except Exception as e:
        print(f"Erreur texte: {e}")
        bot.send_message(message.chat.id, "Une erreur est survenue lors du traitement de votre message.")

# ====== SERVEUR WEB POUR RENDER ======
app = Flask(__name__)

@app.route('/')
def home():
    return "Le bot Telegram fonctionne parfaitement sur Render (port 8080)!"

if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: bot.infinity_polling()).start()
    app.run(host="0.0.0.0", port=8080)
