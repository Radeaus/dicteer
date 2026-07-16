"""
Dicteer - lokale spraak-naar-tekst voor Windows.

Zoals Wispr Flow, maar gratis en 100% lokaal (faster-whisper op je eigen GPU/CPU).
Druk de sneltoets in, praat, en de tekst wordt geplakt in het venster waar je cursor staat.

Twee modi (instelbaar via tray-icoon of config.json):
  - toggle: één keer drukken = start, nog een keer = stop (standaard)
  - hold:   sneltoets ingedrukt houden terwijl je praat (walkietalkie)
"""

import faulthandler
import glob
import json
import logging
import math
import os
import site
import sys
import threading
import time

VERSION = "v24"

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
LOG_PATH = os.path.join(APP_DIR, "dicteer.log")
HISTORY_PATH = os.path.join(APP_DIR, "history.json")
DISCORD_TOKEN_PATH = os.path.join(APP_DIR, "discord_token.json")
STATS_PATH = os.path.join(APP_DIR, "stats.json")

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("dicteer")

# Vangnet 1: harde (native) crashes naar dicteer_crash.log
CRASH_LOG_PATH = os.path.join(APP_DIR, "dicteer_crash.log")
try:
    _crash_file = open(CRASH_LOG_PATH, "a", encoding="utf-8")
    faulthandler.enable(_crash_file)
except Exception:
    pass


# Vangnet 2: onafgevangen Python-fouten (hoofdthread en threads) naar de log
def _log_unhandled(exc_type, exc, tb):
    log.critical("Onafgevangen fout", exc_info=(exc_type, exc, tb))


sys.excepthook = _log_unhandled


def _log_thread_exc(args):
    name = args.thread.name if args.thread else "?"
    log.critical("Onafgevangen fout in thread %s", name,
                 exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


threading.excepthook = _log_thread_exc

DEFAULT_CONFIG = {
    "hotkey": "ctrl+shift+s",
    "mode": "toggle",            # "toggle" (druk=start, druk=stop) of "hold" (vasthouden)
    "suppress_hotkey": True,     # onderschep de toets zodat andere programma's hem niet zien
    "model": "large-v3-turbo",   # snel en zeer goed Nederlands; alternatief: "medium", "large-v3"
    "language": "auto",          # "auto" (NL+EN door elkaar), "nl" of "en"
    "device": "auto",            # "auto", "cuda" of "cpu"
    "beam_size": 2,
    "beep": True,
    "beep_volume": 0.15,      # 0.0 (stil) t/m 1.0 (hard)
    "overlay": True,             # zwevend venstertje onderin beeld tijdens opname
    "live_preview": True,        # live meelezen in de overlay tijdens de opname
    "input_device": "auto",      # microfoon: "auto" of exacte apparaatnaam
    "history": True,             # laatste 10 dictaten in het traymenu
    "discord_mute": False,       # Discord-mic dempen tijdens opname (via officiele Discord-API)
    "discord_deafen": False,     # Discord deafen tijdens opname (je hoort dan zelf ook niets)
    "discord_client_id": "",     # zie README: eigen Discord-app aanmaken
    "discord_client_secret": "",
    "pause_media": False,        # media (Spotify/YouTube) pauzeren tijdens opname
    "ui_language": "en",         # taal van de interface: en/nl/de/es/fr
    "show_settings_on_start": True,
    "restore_clipboard": True,
    "min_seconds": 0.4,
}

SAMPLE_RATE = 16000

# Whisper ondersteunt ~100 talen; dit zijn de keuzes in het menu.
# "auto" detecteert de gesproken taal vanzelf (ook per opname wisselend).
LANGUAGES = [
    ("auto", None),  # weergavenaam komt uit de vertaling (lang_auto)
    ("nl", "Nederlands"),
    ("en", "English"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("pt", "Português"),
    ("pl", "Polski"),
    ("tr", "Türkçe"),
]

UI_LANGUAGES = [
    ("en", "English"),
    ("nl", "Nederlands"),
    ("de", "Deutsch"),
    ("es", "Español"),
    ("fr", "Français"),
]

UI_LANG = "en"

TR = {
"en": {
 "mic": "Microphone", "live_preview": "Live preview while recording",
 "tab_stats": "Statistics", "st_dictations": "Dictations",
 "st_words": "Words dictated", "st_audio": "Total recording time",
 "st_saved": "Estimated time saved",
 "ui_lang_note": "After clicking Apply or Save, restart Dicteer to apply the new interface language.",
 "apply": "Apply", "tab_recording": "Recording",
 "settings_title": "Settings", "tab_general": "General", "tab_audio": "Audio & feedback",
 "tab_discord": "Discord", "tab_system": "System",
 "hotkey": "Hotkey (e.g. ctrl+shift+s or f9)", "mode": "Mode",
 "mode_toggle": "toggle - press to start/stop", "mode_hold": "hold - hold while speaking",
 "spoken_lang": "Dictation language", "lang_auto": "Auto detect",
 "model": "Model (reloaded after saving)", "device": "Device", "ui_lang": "Interface language",
 "beep": "Beeps on start/stop", "beep_vol": "Beep volume (0 = silent, 1 = loud)",
 "overlay": "Show overlay at the bottom of the screen",
 "pause_media": "Pause playing media while recording (resumes afterwards)",
 "dc_mute": "Mute Discord microphone while recording",
 "dc_deafen": "Deafen Discord while recording (you hear nothing)",
 "dc_id": "Discord client ID", "dc_secret": "Discord client secret",
 "dc_link": "Link / test Discord", "dc_note": "One-time setup required - see README.",
 "autostart": "Start with Windows", "history": "Keep history (last 10 dictations)",
 "restore_clip": "Restore clipboard after pasting", "show_start": "Show this window at startup",
 "shortcut": "Create desktop shortcut", "save": "Save", "cancel": "Cancel",
 "saved": "Settings saved.", "recording": "Recording", "transcribing": "Transcribing",
 "state_load": "loading model...", "state_ready": "ready ({hotkey})", "state_rec": "recording",
 "state_proc": "transcribing...", "state_err": "error - see dicteer.log",
 "menu_hotkey": "Hotkey", "menu_settings": "Settings...", "menu_mode": "Mode",
 "menu_mode_hold": "Hold to talk", "menu_mode_toggle": "Press to start/stop",
 "menu_lang": "Language", "menu_history": "History", "hist_empty": "(empty)",
 "menu_dc_mute": "Mute Discord while recording", "menu_dc_deafen": "Deafen Discord while recording",
 "menu_media": "Pause media while recording", "menu_dc_link": "Link / test Discord",
 "menu_autostart": "Start with Windows", "menu_config": "Open config file",
 "menu_reload": "Reload config", "menu_log": "Open log", "menu_quit": "Exit",
 "n_linked": "Linked! Discord was muted for 2 seconds as a test. Ready to go.",
 "n_not_linked": "Discord is not linked yet: tray menu -> 'Link / test Discord'.",
 "n_link_watch": "Watch Discord: an authorization popup may appear...",
 "n_link_fail": "Discord linking failed: ",
 "n_fill": "Enter the Discord client ID and secret first (see README).",
 "n_shortcut_ok": "Shortcut 'Dicteer' added to your desktop.",
 "n_shortcut_fail": "Creating the shortcut failed - see dicteer.log.",
 "n_mic_restored": "Your microphone was muted (by an older version); this has been fixed.",
 "n_rec_fail": "Recording failed to start: ",
},
"nl": {
 "mic": "Microfoon", "live_preview": "Live meelezen tijdens opname",
 "tab_stats": "Statistieken", "st_dictations": "Dictaten",
 "st_words": "Gedicteerde woorden", "st_audio": "Totale opnametijd",
 "st_saved": "Geschatte bespaarde tijd",
 "ui_lang_note": "Na Apply of Save moet je Dicteer opnieuw opstarten om de nieuwe taal te zien.",
 "apply": "Toepassen", "tab_recording": "Opname",
 "settings_title": "Instellingen", "tab_general": "Algemeen", "tab_audio": "Audio & feedback",
 "tab_discord": "Discord", "tab_system": "Systeem",
 "hotkey": "Sneltoets (bijv. ctrl+shift+s of f9)", "mode": "Modus",
 "mode_toggle": "toggle - drukken voor start/stop", "mode_hold": "hold - vasthouden tijdens praten",
 "spoken_lang": "Dicteertaal", "lang_auto": "Automatisch detecteren",
 "model": "Model (wordt na opslaan opnieuw geladen)", "device": "Apparaat", "ui_lang": "Taal van de interface",
 "beep": "Piepjes bij start/stop", "beep_vol": "Piep-volume (0 = stil, 1 = hard)",
 "overlay": "Overlay onderin beeld tonen",
 "pause_media": "Spelende media pauzeren tijdens opname (hervat daarna)",
 "dc_mute": "Discord-microfoon dempen tijdens opname",
 "dc_deafen": "Discord deafenen tijdens opname (je hoort niets)",
 "dc_id": "Discord client-ID", "dc_secret": "Discord client-secret",
 "dc_link": "Discord koppelen / testen", "dc_note": "Eenmalige setup nodig - zie README.",
 "autostart": "Starten met Windows", "history": "Geschiedenis bijhouden (laatste 10 dictaten)",
 "restore_clip": "Klembord herstellen na plakken", "show_start": "Dit venster tonen bij het opstarten",
 "shortcut": "Snelkoppeling op bureaublad maken", "save": "Opslaan", "cancel": "Annuleren",
 "saved": "Instellingen opgeslagen.", "recording": "Opname", "transcribing": "Bezig met omzetten",
 "state_load": "model laden...", "state_ready": "klaar ({hotkey})", "state_rec": "opname loopt",
 "state_proc": "bezig met omzetten...", "state_err": "fout - zie dicteer.log",
 "menu_hotkey": "Sneltoets", "menu_settings": "Instellingen...", "menu_mode": "Modus",
 "menu_mode_hold": "Ingedrukt houden", "menu_mode_toggle": "Drukken voor start/stop",
 "menu_lang": "Taal", "menu_history": "Geschiedenis", "hist_empty": "(nog leeg)",
 "menu_dc_mute": "Discord dempen tijdens opname", "menu_dc_deafen": "Discord deafenen tijdens opname",
 "menu_media": "Media pauzeren tijdens opname", "menu_dc_link": "Discord koppelen / testen",
 "menu_autostart": "Automatisch starten met Windows", "menu_config": "Config openen",
 "menu_reload": "Config herladen", "menu_log": "Logboek openen", "menu_quit": "Afsluiten",
 "n_linked": "Gekoppeld! Discord was ter test 2 seconden gedempt. Klaar voor gebruik.",
 "n_not_linked": "Discord is nog niet gekoppeld: traymenu -> 'Discord koppelen / testen'.",
 "n_link_watch": "Let op Discord: er kan een goedkeuringsvenster verschijnen...",
 "n_link_fail": "Discord koppelen mislukt: ",
 "n_fill": "Vul eerst de Discord client-ID en secret in (zie README).",
 "n_shortcut_ok": "Snelkoppeling 'Dicteer' staat op je bureaublad.",
 "n_shortcut_fail": "Snelkoppeling maken mislukt - zie dicteer.log.",
 "n_mic_restored": "Je microfoon stond op mute (door een oudere versie); dat is hersteld.",
 "n_rec_fail": "Opname starten mislukt: ",
},
"de": {
 "mic": "Mikrofon", "live_preview": "Live-Vorschau während der Aufnahme",
 "tab_stats": "Statistiken", "st_dictations": "Diktate",
 "st_words": "Diktierte Wörter", "st_audio": "Gesamte Aufnahmezeit",
 "st_saved": "Geschätzte gesparte Zeit",
 "ui_lang_note": "Nach Übernehmen oder Speichern muss Dicteer neu gestartet werden, um die neue Sprache anzuzeigen.",
 "apply": "Übernehmen", "tab_recording": "Aufnahme",
 "settings_title": "Einstellungen", "tab_general": "Allgemein", "tab_audio": "Audio & Feedback",
 "tab_discord": "Discord", "tab_system": "System",
 "hotkey": "Tastenkürzel (z. B. ctrl+shift+s oder f9)", "mode": "Modus",
 "mode_toggle": "toggle - drücken für Start/Stopp", "mode_hold": "hold - beim Sprechen gedrückt halten",
 "spoken_lang": "Diktiersprache", "lang_auto": "Automatisch erkennen",
 "model": "Modell (wird nach dem Speichern neu geladen)", "device": "Gerät", "ui_lang": "Sprache der Oberfläche",
 "beep": "Signaltöne bei Start/Stopp", "beep_vol": "Lautstärke (0 = stumm, 1 = laut)",
 "overlay": "Overlay am unteren Bildschirmrand anzeigen",
 "pause_media": "Laufende Medien während der Aufnahme pausieren (danach fortsetzen)",
 "dc_mute": "Discord-Mikrofon während der Aufnahme stummschalten",
 "dc_deafen": "Discord während der Aufnahme deafen (du hörst nichts)",
 "dc_id": "Discord Client-ID", "dc_secret": "Discord Client-Secret",
 "dc_link": "Discord verknüpfen / testen", "dc_note": "Einmalige Einrichtung nötig - siehe README.",
 "autostart": "Mit Windows starten", "history": "Verlauf behalten (letzte 10 Diktate)",
 "restore_clip": "Zwischenablage nach dem Einfügen wiederherstellen", "show_start": "Dieses Fenster beim Start anzeigen",
 "shortcut": "Desktop-Verknüpfung erstellen", "save": "Speichern", "cancel": "Abbrechen",
 "saved": "Einstellungen gespeichert.", "recording": "Aufnahme", "transcribing": "Wird umgewandelt",
 "state_load": "Modell wird geladen...", "state_ready": "bereit ({hotkey})", "state_rec": "Aufnahme läuft",
 "state_proc": "wird umgewandelt...", "state_err": "Fehler - siehe dicteer.log",
 "menu_hotkey": "Tastenkürzel", "menu_settings": "Einstellungen...", "menu_mode": "Modus",
 "menu_mode_hold": "Gedrückt halten", "menu_mode_toggle": "Drücken für Start/Stopp",
 "menu_lang": "Sprache", "menu_history": "Verlauf", "hist_empty": "(leer)",
 "menu_dc_mute": "Discord bei Aufnahme stummschalten", "menu_dc_deafen": "Discord bei Aufnahme deafen",
 "menu_media": "Medien bei Aufnahme pausieren", "menu_dc_link": "Discord verknüpfen / testen",
 "menu_autostart": "Mit Windows starten", "menu_config": "Konfiguration öffnen",
 "menu_reload": "Konfiguration neu laden", "menu_log": "Protokoll öffnen", "menu_quit": "Beenden",
 "n_linked": "Verknüpft! Discord war zum Test 2 Sekunden stummgeschaltet. Bereit.",
 "n_not_linked": "Discord ist noch nicht verknüpft: Tray-Menü -> 'Discord verknüpfen / testen'.",
 "n_link_watch": "Achte auf Discord: möglicherweise erscheint ein Freigabefenster...",
 "n_link_fail": "Discord-Verknüpfung fehlgeschlagen: ",
 "n_fill": "Bitte zuerst Discord Client-ID und Secret eintragen (siehe README).",
 "n_shortcut_ok": "Verknüpfung 'Dicteer' liegt auf dem Desktop.",
 "n_shortcut_fail": "Verknüpfung fehlgeschlagen - siehe dicteer.log.",
 "n_mic_restored": "Dein Mikrofon war stummgeschaltet (durch eine ältere Version); behoben.",
 "n_rec_fail": "Aufnahme konnte nicht starten: ",
},
"es": {
 "mic": "Micrófono", "live_preview": "Vista previa en vivo durante la grabación",
 "tab_stats": "Estadísticas", "st_dictations": "Dictados",
 "st_words": "Palabras dictadas", "st_audio": "Tiempo total de grabación",
 "st_saved": "Tiempo ahorrado estimado",
 "ui_lang_note": "Tras Aplicar o Guardar, reinicia Dicteer para ver el nuevo idioma.",
 "apply": "Aplicar", "tab_recording": "Grabación",
 "settings_title": "Ajustes", "tab_general": "General", "tab_audio": "Audio y avisos",
 "tab_discord": "Discord", "tab_system": "Sistema",
 "hotkey": "Atajo de teclado (p. ej. ctrl+shift+s o f9)", "mode": "Modo",
 "mode_toggle": "toggle - pulsar para iniciar/parar", "mode_hold": "hold - mantener pulsado al hablar",
 "spoken_lang": "Idioma del dictado", "lang_auto": "Detección automática",
 "model": "Modelo (se recarga al guardar)", "device": "Dispositivo", "ui_lang": "Idioma de la interfaz",
 "beep": "Pitidos al iniciar/parar", "beep_vol": "Volumen del pitido (0 = silencio, 1 = alto)",
 "overlay": "Mostrar overlay en la parte inferior",
 "pause_media": "Pausar el contenido en reproducción durante la grabación (se reanuda después)",
 "dc_mute": "Silenciar el micrófono de Discord durante la grabación",
 "dc_deafen": "Ensordecer Discord durante la grabación (no oyes nada)",
 "dc_id": "ID de cliente de Discord", "dc_secret": "Secreto de cliente de Discord",
 "dc_link": "Vincular / probar Discord", "dc_note": "Requiere configuración única - ver README.",
 "autostart": "Iniciar con Windows", "history": "Guardar historial (últimos 10 dictados)",
 "restore_clip": "Restaurar el portapapeles tras pegar", "show_start": "Mostrar esta ventana al iniciar",
 "shortcut": "Crear acceso directo en el escritorio", "save": "Guardar", "cancel": "Cancelar",
 "saved": "Ajustes guardados.", "recording": "Grabando", "transcribing": "Transcribiendo",
 "state_load": "cargando modelo...", "state_ready": "listo ({hotkey})", "state_rec": "grabando",
 "state_proc": "transcribiendo...", "state_err": "error - ver dicteer.log",
 "menu_hotkey": "Atajo", "menu_settings": "Ajustes...", "menu_mode": "Modo",
 "menu_mode_hold": "Mantener pulsado", "menu_mode_toggle": "Pulsar para iniciar/parar",
 "menu_lang": "Idioma", "menu_history": "Historial", "hist_empty": "(vacío)",
 "menu_dc_mute": "Silenciar Discord al grabar", "menu_dc_deafen": "Ensordecer Discord al grabar",
 "menu_media": "Pausar multimedia al grabar", "menu_dc_link": "Vincular / probar Discord",
 "menu_autostart": "Iniciar con Windows", "menu_config": "Abrir configuración",
 "menu_reload": "Recargar configuración", "menu_log": "Abrir registro", "menu_quit": "Salir",
 "n_linked": "¡Vinculado! Discord estuvo silenciado 2 segundos como prueba. Listo.",
 "n_not_linked": "Discord aún no está vinculado: menú de bandeja -> 'Vincular / probar Discord'.",
 "n_link_watch": "Atento a Discord: puede aparecer una ventana de autorización...",
 "n_link_fail": "Error al vincular Discord: ",
 "n_fill": "Introduce primero el ID y el secreto de cliente de Discord (ver README).",
 "n_shortcut_ok": "Acceso directo 'Dicteer' añadido al escritorio.",
 "n_shortcut_fail": "No se pudo crear el acceso directo - ver dicteer.log.",
 "n_mic_restored": "Tu micrófono estaba silenciado (por una versión anterior); corregido.",
 "n_rec_fail": "No se pudo iniciar la grabación: ",
},
"fr": {
 "mic": "Microphone", "live_preview": "Aperçu en direct pendant l'enregistrement",
 "tab_stats": "Statistiques", "st_dictations": "Dictées",
 "st_words": "Mots dictés", "st_audio": "Durée totale d'enregistrement",
 "st_saved": "Temps gagné estimé",
 "ui_lang_note": "Après Appliquer ou Enregistrer, redémarrez Dicteer pour voir la nouvelle langue.",
 "apply": "Appliquer", "tab_recording": "Enregistrement",
 "settings_title": "Paramètres", "tab_general": "Général", "tab_audio": "Audio et retours",
 "tab_discord": "Discord", "tab_system": "Système",
 "hotkey": "Raccourci (p. ex. ctrl+shift+s ou f9)", "mode": "Mode",
 "mode_toggle": "toggle - appuyer pour démarrer/arrêter", "mode_hold": "hold - maintenir en parlant",
 "spoken_lang": "Langue de dictée", "lang_auto": "Détection automatique",
 "model": "Modèle (rechargé après enregistrement)", "device": "Périphérique", "ui_lang": "Langue de l'interface",
 "beep": "Bips au démarrage/arrêt", "beep_vol": "Volume du bip (0 = muet, 1 = fort)",
 "overlay": "Afficher l'overlay en bas de l'écran",
 "pause_media": "Mettre en pause les médias en cours pendant l'enregistrement (reprise ensuite)",
 "dc_mute": "Couper le micro Discord pendant l'enregistrement",
 "dc_deafen": "Mettre Discord en sourdine pendant l'enregistrement (vous n'entendez rien)",
 "dc_id": "ID client Discord", "dc_secret": "Secret client Discord",
 "dc_link": "Lier / tester Discord", "dc_note": "Configuration unique requise - voir README.",
 "autostart": "Démarrer avec Windows", "history": "Conserver l'historique (10 dernières dictées)",
 "restore_clip": "Restaurer le presse-papiers après collage", "show_start": "Afficher cette fenêtre au démarrage",
 "shortcut": "Créer un raccourci sur le bureau", "save": "Enregistrer", "cancel": "Annuler",
 "saved": "Paramètres enregistrés.", "recording": "Enregistrement", "transcribing": "Transcription",
 "state_load": "chargement du modèle...", "state_ready": "prêt ({hotkey})", "state_rec": "enregistrement",
 "state_proc": "transcription...", "state_err": "erreur - voir dicteer.log",
 "menu_hotkey": "Raccourci", "menu_settings": "Paramètres...", "menu_mode": "Mode",
 "menu_mode_hold": "Maintenir enfoncé", "menu_mode_toggle": "Appuyer pour démarrer/arrêter",
 "menu_lang": "Langue", "menu_history": "Historique", "hist_empty": "(vide)",
 "menu_dc_mute": "Couper Discord pendant l'enregistrement", "menu_dc_deafen": "Sourdine Discord pendant l'enregistrement",
 "menu_media": "Pause médias pendant l'enregistrement", "menu_dc_link": "Lier / tester Discord",
 "menu_autostart": "Démarrer avec Windows", "menu_config": "Ouvrir la configuration",
 "menu_reload": "Recharger la configuration", "menu_log": "Ouvrir le journal", "menu_quit": "Quitter",
 "n_linked": "Lié ! Discord a été coupé 2 secondes en test. Prêt.",
 "n_not_linked": "Discord n'est pas encore lié : menu -> 'Lier / tester Discord'.",
 "n_link_watch": "Surveillez Discord : une fenêtre d'autorisation peut apparaître...",
 "n_link_fail": "Échec de la liaison Discord : ",
 "n_fill": "Renseignez d'abord l'ID et le secret client Discord (voir README).",
 "n_shortcut_ok": "Raccourci 'Dicteer' ajouté au bureau.",
 "n_shortcut_fail": "Échec de la création du raccourci - voir dicteer.log.",
 "n_mic_restored": "Votre micro était coupé (par une ancienne version) ; corrigé.",
 "n_rec_fail": "Impossible de démarrer l'enregistrement : ",
},
}


def tr(key):
    d = TR.get(UI_LANG) or TR["en"]
    return d.get(key) or TR["en"].get(key, key)


# ---------------------------------------------------------------- config

def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        save_config(cfg)
    except Exception as e:
        log.warning("config.json onleesbaar, standaardwaarden gebruikt: %s", e)
    global UI_LANG
    UI_LANG = cfg.get("ui_language", "en")
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.warning("config.json niet opgeslagen: %s", e)


# ---------------------------------------------------------------- geschiedenis

def load_history():
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return list(json.load(f))[:10]
    except Exception:
        return []


def save_history(hist):
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ---------------------------------------------------------------- statistieken

def load_stats():
    d = {"dictations": 0, "words": 0, "seconds": 0.0}
    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            d.update(json.load(f))
    except Exception:
        pass
    return d


def save_stats(stats):
    try:
        with open(STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------- autostart

AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_enabled():
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as k:
            winreg.QueryValueEx(k, "Dicteer")
        return True
    except Exception:
        return False


def set_autostart(enabled):
    if os.name != "nt":
        return
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY,
                            0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                exe = sys.executable
                pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
                if os.path.exists(pyw):
                    exe = pyw  # zonder consolevenster
                cmd = f'"{exe}" "{os.path.abspath(__file__)}"'
                winreg.SetValueEx(k, "Dicteer", 0, winreg.REG_SZ, cmd)
                log.info("Autostart aangezet: %s", cmd)
            else:
                try:
                    winreg.DeleteValue(k, "Dicteer")
                except FileNotFoundError:
                    pass
                log.info("Autostart uitgezet.")
    except Exception:
        log.exception("Autostart instellen mislukt")


# ------------------------------------------------------------ app-identiteit

APP_AUMID = "Dicteer.Dicteer"


def setup_app_identity():
    """Registreer Dicteer als eigen app bij Windows, zodat meldingen
    'Dicteer' met het eigen icoontje tonen in plaats van 'Python'."""
    if os.name != "nt":
        return
    try:
        import ctypes
        import winreg
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_AUMID)
        with winreg.CreateKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Classes\AppUserModelId" + "\\" + APP_AUMID) as k:
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, "Dicteer")
            ico = os.path.join(APP_DIR, "dicteer.ico")
            if os.path.exists(ico):
                winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, ico)
    except Exception:
        log.exception("App-identiteit instellen mislukt")


# ---------------------------------------------------------------- snelkoppeling

def make_desktop_shortcut():
    """Maak/ververs de snelkoppeling 'Dicteer' op het bureaublad."""
    if os.name != "nt":
        return None
    import ctypes
    import gc
    import comtypes
    import comtypes.client
    buf = ctypes.create_unicode_buffer(260)
    # CSIDL_DESKTOPDIRECTORY (0x10): echte bureaublad-map, ook bij OneDrive
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf)
    desktop = buf.value or os.path.join(os.path.expanduser("~"), "Desktop")
    pad = os.path.join(desktop, "Dicteer.lnk")
    comtypes.CoInitialize()
    ws = lnk = None
    try:
        ws = comtypes.client.CreateObject("WScript.Shell", dynamic=True)
        lnk = ws.CreateShortcut(pad)
        pyw = os.path.join(APP_DIR, "venv", "Scripts", "pythonw.exe")
        if not os.path.exists(pyw):
            pyw = sys.executable
        lnk.TargetPath = pyw
        lnk.Arguments = f'"{os.path.join(APP_DIR, "dicteer.py")}"'
        lnk.WorkingDirectory = APP_DIR
        ico = os.path.join(APP_DIR, "dicteer.ico")
        if os.path.exists(ico):
            lnk.IconLocation = ico
        lnk.Save()
        log.info("Bureaublad-snelkoppeling gemaakt: %s", pad)
        return pad
    finally:
        lnk = ws = None
        gc.collect()  # COM-objecten op deze thread opruimen (zie repair_microphone)
        try:
            comtypes.CoUninitialize()
        except Exception:
            pass


# ---------------------------------------------------------------- discord

def pycaw_available():
    try:
        import comtypes  # noqa: F401
        import pycaw.pycaw  # noqa: F401
        return True
    except Exception:
        return False


def _iter_capture_sessions():
    """(procesnaam, ISimpleAudioVolume) voor elke opnamesessie op alle actieve microfoons."""
    import comtypes
    from pycaw.pycaw import (IAudioSessionManager2, IAudioSessionControl2,
                             ISimpleAudioVolume, IMMDeviceEnumerator)
    try:
        from pycaw.constants import CLSID_MMDeviceEnumerator
    except ImportError:
        from pycaw.pycaw import CLSID_MMDeviceEnumerator

    enumerator = comtypes.CoCreateInstance(
        CLSID_MMDeviceEnumerator, IMMDeviceEnumerator,
        comtypes.CLSCTX_INPROC_SERVER)
    collection = enumerator.EnumAudioEndpoints(1, 1)  # eCapture, DEVICE_STATE_ACTIVE
    for i in range(collection.GetCount()):
        try:
            dev = collection.Item(i)
            mgr = dev.Activate(IAudioSessionManager2._iid_, comtypes.CLSCTX_ALL, None)
            mgr = mgr.QueryInterface(IAudioSessionManager2)
            sessions = mgr.GetSessionEnumerator()
        except Exception:
            log.exception("Opnameapparaat %d niet leesbaar", i)
            continue
        for j in range(sessions.GetCount()):
            try:
                ctl2 = sessions.GetSession(j).QueryInterface(IAudioSessionControl2)
                pid = ctl2.GetProcessId()
                try:
                    import psutil
                    name = psutil.Process(pid).name()
                except Exception:
                    name = f"pid={pid}"
                yield name, ctl2.QueryInterface(ISimpleAudioVolume)
            except Exception:
                continue


def repair_microphone():
    """Herstel dempingen die door een eerdere Dicteer-versie zijn blijven hangen.
    BELANGRIJK: alle COM-objecten worden op deze thread expliciet opgeruimd
    (gc.collect) voordat COM sluit - anders ruimt de garbage collector ze
    later op een willekeurige andere thread op en crasht het hele programma
    met een access violation (dit was de oorzaak van de random crashes)."""
    if not pycaw_available():
        return 0
    import gc
    import comtypes
    from ctypes import POINTER, cast
    from pycaw.pycaw import IAudioEndpointVolume, IMMDeviceEnumerator
    try:
        from pycaw.constants import CLSID_MMDeviceEnumerator
    except ImportError:
        from pycaw.pycaw import CLSID_MMDeviceEnumerator
    fixed = 0
    comtypes.CoInitialize()
    try:
        enumerator = collection = None
        try:
            enumerator = comtypes.CoCreateInstance(
                CLSID_MMDeviceEnumerator, IMMDeviceEnumerator,
                comtypes.CLSCTX_INPROC_SERVER)
            collection = enumerator.EnumAudioEndpoints(1, 1)  # eCapture, ACTIVE
            for i in range(collection.GetCount()):
                dev = itf = vol = None
                try:
                    dev = collection.Item(i)
                    itf = dev.Activate(IAudioEndpointVolume._iid_,
                                       comtypes.CLSCTX_ALL, None)
                    vol = cast(itf, POINTER(IAudioEndpointVolume))
                    if vol.GetMute():
                        vol.SetMute(0, None)
                        fixed += 1
                        log.info("Opnameapparaat %d stond op mute; hersteld.", i)
                except Exception:
                    pass
                finally:
                    dev = itf = vol = None
            name = svol = None
            for name, svol in _iter_capture_sessions():
                try:
                    if "discord" in name.lower() and svol.GetMute():
                        svol.SetMute(0, None)
                        fixed += 1
                        log.info("Audiosessie van %s stond op mute; hersteld.", name)
                except Exception:
                    pass
                finally:
                    svol = None
        except Exception:
            log.exception("Microfoon-herstel mislukt")
        finally:
            enumerator = collection = None
            gc.collect()  # ruim ALLE COM-objecten nu op, op deze thread
    finally:
        try:
            comtypes.CoUninitialize()
        except Exception:
            pass
    return fixed


# --------------------------------------------------- discord rpc (officiele API)

class DiscordNotLinked(RuntimeError):
    """Nog geen koppeling met Discord gemaakt (traymenu -> Discord koppelen)."""


class _DiscordRPC:
    """Minimale synchrone Discord RPC-client via de lokale IPC-pipe."""

    def __init__(self, client_id):
        self.client_id = str(client_id)
        self._f = None

    def connect(self):
        for i in range(10):
            try:
                self._f = open(rf"\\.\pipe\discord-ipc-{i}", "r+b", buffering=0)
            except OSError:
                continue
            self._send(0, {"v": 1, "client_id": self.client_id})  # handshake
            op, data = self._recv()
            if data.get("evt") == "READY" or data.get("cmd") == "DISPATCH":
                return
            self.close()
        raise RuntimeError("Discord niet gevonden - draait de Discord-app?")

    def _send(self, op, payload):
        import struct
        raw = json.dumps(payload).encode("utf-8")
        self._f.write(struct.pack("<II", op, len(raw)) + raw)

    def _read_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self._f.read(n - len(buf))
            if not chunk:
                raise RuntimeError("Discord: verbinding verbroken")
            buf += chunk
        return buf

    def _recv(self):
        import struct
        op, length = struct.unpack("<II", self._read_exact(8))
        return op, json.loads(self._read_exact(length).decode("utf-8"))

    def cmd(self, name, args, max_frames=50):
        import uuid
        nonce = str(uuid.uuid4())
        self._send(1, {"cmd": name, "args": args, "nonce": nonce})
        for _ in range(max_frames):
            op, data = self._recv()
            if data.get("nonce") == nonce:
                if data.get("evt") == "ERROR":
                    msg = (data.get("data") or {}).get("message", "onbekende fout")
                    raise RuntimeError(f"Discord: {msg}")
                return data.get("data") or {}
        raise RuntimeError(f"Discord: geen antwoord op {name}")

    def close(self):
        try:
            if self._f:
                self._f.close()
        except Exception:
            pass
        self._f = None


def _discord_load_token():
    try:
        with open(DISCORD_TOKEN_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _discord_save_token(tok):
    try:
        with open(DISCORD_TOKEN_PATH, "w", encoding="utf-8") as f:
            json.dump(tok, f, indent=2)
    except Exception:
        log.exception("Discord-token niet opgeslagen")


def _discord_token_request(fields):
    """OAuth2-tokenaanvraag bij Discord (authorization_code of refresh_token)."""
    import urllib.parse
    import urllib.request
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        "https://discord.com/api/oauth2/token", data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Dicteer/1.0",
        })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        detail = ""
        try:
            detail = e.read().decode()[:200]  # HTTPError heeft een body
        except Exception:
            pass
        raise RuntimeError(f"tokenaanvraag mislukt: {e} {detail}")


_discord_was_muted = False  # stond de gebruiker zelf al op mute?


def _discord_authenticate(rpc, cfg, interactive=False):
    """Log in op een open RPC-verbinding met het bewaarde token
    (zo nodig verversen; alleen bij interactive=True de goedkeurings-popup)."""
    cid = str(cfg["discord_client_id"])
    secret = cfg["discord_client_secret"]
    tok = _discord_load_token()
    if tok.get("access_token"):
        try:
            rpc.cmd("AUTHENTICATE", {"access_token": tok["access_token"]})
            return
        except Exception:
            pass
    if tok.get("refresh_token"):
        try:
            tok = _discord_token_request({
                "client_id": cid, "client_secret": secret,
                "grant_type": "refresh_token",
                "refresh_token": tok["refresh_token"]})
            _discord_save_token(tok)
            rpc.cmd("AUTHENTICATE", {"access_token": tok["access_token"]})
            return
        except Exception:
            pass
    if not interactive:
        raise DiscordNotLinked("nog niet gekoppeld")
    data = rpc.cmd("AUTHORIZE", {
        "client_id": cid,
        "scopes": ["rpc", "rpc.voice.read", "rpc.voice.write"]})
    fields = {
        "client_id": cid, "client_secret": secret,
        "grant_type": "authorization_code", "code": data["code"]}
    try:
        tok = _discord_token_request(
            {**fields, "redirect_uri": "http://127.0.0.1"})
    except RuntimeError as e1:
        log.info("Tokenruil met redirect_uri mislukt (%s); "
                 "opnieuw zonder redirect_uri...", e1)
        tok = _discord_token_request(fields)
    _discord_save_token(tok)
    rpc.cmd("AUTHENTICATE", {"access_token": tok["access_token"]})


_discord_was_deafened = False


def _rpc_apply_state(rpc, active, do_mute, do_deaf):
    """Zet mute/deafen aan bij opnamestart en herstel de oorspronkelijke
    stand daarna (wie zelf al gemute/gedeafend stond, blijft dat)."""
    global _discord_was_muted, _discord_was_deafened
    if active:
        prev = {}
        try:
            prev = rpc.cmd("GET_VOICE_SETTINGS", {})
        except Exception:
            pass
        _discord_was_muted = bool(prev.get("mute"))
        _discord_was_deafened = bool(prev.get("deaf"))
        args = {}
        if do_mute:
            args["mute"] = True
        if do_deaf:
            args["deaf"] = True
        if args:
            rpc.cmd("SET_VOICE_SETTINGS", args)
    else:
        args = {}
        if do_deaf and not _discord_was_deafened:
            args["deaf"] = False
        if do_mute and not _discord_was_muted:
            args["mute"] = False
        if args:
            rpc.cmd("SET_VOICE_SETTINGS", args)


def discord_rpc_set_mute(cfg, mute, interactive=False):
    """Eenmalige verbinding (voor koppelen/testen via het traymenu)."""
    rpc = _DiscordRPC(cfg["discord_client_id"])
    try:
        rpc.connect()
        _discord_authenticate(rpc, cfg, interactive=interactive)
        _rpc_apply_state(rpc, mute, True, False)
    finally:
        rpc.close()


class DiscordMuteWorker:
    """Eén permanente RPC-verbinding + wachtrij. Voert altijd alleen de
    laatst gevraagde stand uit, zodat mute/unmute elkaar nooit inhalen,
    en dempt in milliseconden i.p.v. per keer opnieuw te verbinden."""

    def __init__(self, app):
        self.app = app
        self._desired = None
        self._cv = threading.Condition()
        self._rpc = None
        threading.Thread(target=self._run, daemon=True,
                         name="discord-mute").start()

    def request(self, mute):
        with self._cv:
            self._desired = bool(mute)
            self._cv.notify()

    def _close(self):
        if self._rpc is not None:
            try:
                self._rpc.close()
            except Exception:
                pass
            self._rpc = None

    def _ensure_connected(self):
        if self._rpc is not None:
            return
        rpc = _DiscordRPC(self.app.cfg["discord_client_id"])
        rpc.connect()
        _discord_authenticate(rpc, self.app.cfg, interactive=False)
        self._rpc = rpc
        log.info("Discord RPC-verbinding opgezet.")

    def _run(self):
        while True:
            with self._cv:
                while self._desired is None:
                    if not self._cv.wait(timeout=120):
                        self._close()  # even niets gedaan: verbinding netjes dicht
                mute = self._desired
                self._desired = None
            t0 = time.time()
            do_mute = bool(self.app.cfg.get("discord_mute", False))
            do_deaf = bool(self.app.cfg.get("discord_deafen", False))
            try:
                try:
                    self._ensure_connected()
                    _rpc_apply_state(self._rpc, mute, do_mute, do_deaf)
                except DiscordNotLinked:
                    raise
                except Exception:
                    # verbinding kwijt (Discord herstart?): een keer opnieuw
                    self._close()
                    self._ensure_connected()
                    _rpc_apply_state(self._rpc, mute, do_mute, do_deaf)
                log.info("Discord-mic %s (%.2f s).",
                         "gedempt" if mute else "hersteld", time.time() - t0)
            except DiscordNotLinked:
                self._close()
                self.app._notify(tr("n_not_linked"))
            except Exception:
                log.exception("Discord dempen mislukt")
                self._close()


# ---------------------------------------------------------------- CUDA DLL's

def setup_cuda_dlls():
    """Maak de cuBLAS/cuDNN DLL's uit de pip-packages vindbaar (Windows)."""
    if os.name != "nt":
        return
    paths = []
    try:
        site_dirs = list(site.getsitepackages())
    except Exception:
        site_dirs = []
    try:
        site_dirs.append(site.getusersitepackages())
    except Exception:
        pass
    for sp in site_dirs:
        paths.extend(glob.glob(os.path.join(sp, "nvidia", "*", "bin")))
    for p in paths:
        try:
            os.add_dll_directory(p)
        except Exception:
            pass
        os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")
    if paths:
        log.info("CUDA DLL-paden toegevoegd: %s", paths)


# ---------------------------------------------------------------- media

class MediaController:
    """Pauzeert bij opnamestart alleen media die daadwerkelijk SPEELT en
    hervat daarna uitsluitend wat wij zelf gepauzeerd hebben. Gebruikt de
    officiele Windows-media-API (SMTC) - geen blinde play/pauze-toggle."""

    PLAYING, PAUSED = 4, 5

    def __init__(self, app):
        self.app = app
        self._paused = []
        self._warned = False

    def pause_playing(self):
        try:
            import asyncio
            from winrt.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as Mgr)

            async def _go():
                mgr = await Mgr.request_async()
                paused = []
                for s in mgr.get_sessions():
                    try:
                        info = s.get_playback_info()
                        if info and int(info.playback_status) == self.PLAYING:
                            if await s.try_pause_async():
                                paused.append(s.source_app_user_model_id)
                    except Exception:
                        continue
                return paused

            self._paused = asyncio.run(_go())
            if self._paused:
                log.info("Media gepauzeerd: %s", ", ".join(self._paused))
        except ModuleNotFoundError:
            if not self._warned:
                self._warned = True
                self.app._notify("Pause media needs extra packages - "
                                 "run install.bat again.")
        except Exception:
            log.exception("Media pauzeren mislukt")

    def resume_paused(self):
        apps, self._paused = self._paused, []
        if not apps:
            return
        try:
            import asyncio
            from winrt.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as Mgr)

            async def _go():
                mgr = await Mgr.request_async()
                for s in mgr.get_sessions():
                    try:
                        if s.source_app_user_model_id in apps:
                            info = s.get_playback_info()
                            if info and int(info.playback_status) == self.PAUSED:
                                await s.try_play_async()
                    except Exception:
                        continue

            asyncio.run(_go())
            log.info("Media hervat: %s", ", ".join(apps))
        except Exception:
            log.exception("Media hervatten mislukt")


# ---------------------------------------------------------------- geluid

_beep_cache = {}


def beep(freq, dur_ms, volume=0.15):
    """Zachte sinustoon; volume 0.0-1.0. Speelt via winsound, volledig los van
    het opname-audiosysteem zodat de startpiep nooit botst met de microfoonstream."""
    if os.name != "nt":
        return
    def _b():
        try:
            import winsound
            key = (int(freq), int(dur_ms), round(float(volume), 3))
            data = _beep_cache.get(key)
            if data is None:
                import io
                import struct
                import wave as wavemod
                sr = 22050
                n = int(sr * dur_ms / 1000)
                fade = max(1, int(sr * 0.005))  # 5 ms in/uitfaden tegen tikjes
                amp = max(0.0, min(1.0, float(volume))) * 32767
                frames = bytearray()
                for i in range(n):
                    env = min(1.0, i / fade, (n - 1 - i) / fade)
                    frames += struct.pack(
                        "<h", int(amp * env * math.sin(2 * math.pi * freq * i / sr)))
                buf = io.BytesIO()
                with wavemod.open(buf, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(sr)
                    w.writeframes(bytes(frames))
                data = buf.getvalue()
                _beep_cache[key] = data
            winsound.PlaySound(data, winsound.SND_MEMORY)
        except Exception:
            log.exception("Beep mislukt")
    threading.Thread(target=_b, daemon=True).start()


# ---------------------------------------------------------------- opname

def list_input_devices():
    """Namen van beschikbare microfoons ('auto' = systeemstandaard)."""
    out, seen = ["auto"], set()
    try:
        import sounddevice as sd
        for d in sd.query_devices():
            if d.get("max_input_channels", 0) > 0:
                naam = d["name"]
                if naam not in seen:
                    seen.add(naam)
                    out.append(naam)
    except Exception:
        pass
    return out


class Recorder:
    def __init__(self):
        self._chunks = []
        self._stream = None
        self._lock = threading.Lock()
        self.level = 0.0  # actueel microfoonniveau (RMS), voor de overlay

    @property
    def recording(self):
        return self._stream is not None

    def start(self, device="auto"):
        import sounddevice as sd
        with self._lock:
            if self._stream is not None:
                return
            self._chunks = []
            dev = None
            if device and device != "auto":
                try:
                    for i, d in enumerate(sd.query_devices()):
                        if d.get("max_input_channels", 0) > 0 and d["name"] == device:
                            dev = i
                            break
                except Exception:
                    dev = None

            def callback(indata, frames, t, status):
                self._chunks.append(indata.copy())
                self.level = float((indata ** 2).mean()) ** 0.5

            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                callback=callback, device=dev,
            )
            self._stream.start()

    def stop(self):
        import numpy as np
        with self._lock:
            if self._stream is None:
                return None
            self._stream.stop()
            self._stream.close()
            self._stream = None
            self.level = 0.0
            if not self._chunks:
                return None
            audio = np.concatenate(self._chunks, axis=0).flatten()
            self._chunks = []
            return audio


# ---------------------------------------------------------------- overlay

class Overlay:
    """UI op de HOOFDthread: onzichtbare root + opname-overlay + instellingen.
    tkinter/CustomTkinter zijn niet thread-safe; daarom draait het tray-icoon
    juist in een eigen thread (run_detached) en de UI hier."""

    def __init__(self, app):
        self.app = app
        self._visible = False
        self._root = None
        self._ov = None
        self._phase = 0.0
        self._smooth = 0.0
        self._pending_settings = False
        self._settings_win = None
        self._quit = False

    def open_settings(self):
        """Vraag (vanaf elke thread) om het instellingenvenster te openen."""
        self._pending_settings = True

    def request_quit(self):
        self._quit = True

    def run_mainloop(self):
        import tkinter as tk
        try:
            try:
                import customtkinter as ctk
                ctk.set_appearance_mode("dark")
                root = ctk.CTk()
            except Exception:
                root = tk.Tk()
            self._root = root
            root.withdraw()
            ov = tk.Toplevel(root)
            self._ov = ov
            ov.withdraw()
            ov.overrideredirect(True)            # geen titelbalk
            ov.attributes("-topmost", True)      # altijd bovenop
            try:
                ov.attributes("-alpha", 0.93)    # licht doorschijnend
            except Exception:
                pass
            self._w, self._h = 460, 96
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            ov.geometry(f"{self._w}x{self._h}+{(sw - self._w) // 2}+{sh - self._h - 90}")
            self._canvas = tk.Canvas(ov, width=self._w, height=self._h,
                                     bg="#1e1e28", highlightthickness=0)
            self._canvas.pack()
            self._tick()
            root.mainloop()
        except Exception:
            log.exception("UI-thread gestopt")

    def _show(self):
        if not self._visible:
            self._ov.deiconify()
            self._ov.attributes("-topmost", True)
            self._visible = True

    def _hide(self):
        if self._visible:
            self._ov.withdraw()
            self._visible = False

    def _tick(self):
        if self._quit:
            try:
                self._root.quit()
            except Exception:
                pass
            return
        try:
            if self._pending_settings:
                self._pending_settings = False
                self._open_settings_window()
        except Exception:
            log.exception("Instellingenvenster openen mislukt")
        try:
            state = self.app.state
            c = self._canvas
            cy = self._h / 2
            if state == "opname" and self.app.cfg.get("overlay", True):
                cy = 32
                self._show()
                c.delete("all")
                self._phase += 0.35
                lvl = getattr(self.app.recorder, "level", 0.0)
                self._smooth = 0.7 * self._smooth + 0.3 * lvl
                # rode stip die zachtjes pulseert
                r = 7 + 2 * math.sin(self._phase * 0.6)
                c.create_oval(24 - r, cy - r, 24 + r, cy + r, fill="#e5484d", outline="")
                c.create_text(44, cy, anchor="w", text=tr("recording"), fill="#ffffff",
                              font=("Segoe UI", 12, "bold"))
                # geluidsbalkjes die meebewegen met je stem
                amp = min(1.0, self._smooth * 18)
                n, x0 = 30, 165
                for i in range(n):
                    hgt = 3 + 30 * amp * (0.35 + 0.65 * abs(math.sin(self._phase + i * 0.9)))
                    x = x0 + i * 9
                    c.create_rectangle(x, cy - hgt / 2, x + 5, cy + hgt / 2,
                                       fill="#4cc38a", outline="")
                pv = getattr(self.app, "preview_text", "")
                if pv:
                    if len(pv) > 62:
                        pv = "\u2026" + pv[-62:]
                    c.create_text(self._w / 2, 74, text=pv, fill="#c9c9d1",
                                  font=("Segoe UI", 10), width=self._w - 24)
            elif state == "verwerken" and self.app.cfg.get("overlay", True):
                self._show()
                c.delete("all")
                self._phase += 0.25
                dots = "." * (1 + int(self._phase) % 3)
                c.create_text(self._w / 2, cy, text=f"{tr('transcribing')}{dots}",
                              fill="#f5a623", font=("Segoe UI", 12, "bold"))
            else:
                self._hide()
        except Exception:
            pass
        self._root.after(50, self._tick)


    def _open_settings_window(self):
        import tkinter as tk
        try:
            import customtkinter as ctk
        except Exception:
            log.exception("customtkinter ontbreekt")
            self.app._notify("Missing package. Run: venv\\Scripts\\python.exe "
                             "-m pip install customtkinter")
            return
        if self._settings_win is not None:
            try:
                self._settings_win.deiconify()
                self._settings_win.lift()
                return
            except Exception:
                self._settings_win = None
        cfg = self.app.cfg
        ACCENT, ACCENT_H = "#2ea043", "#3fb950"
        BG, SIDE, CARD, DIM = "#101012", "#17171a", "#1d1d22", "#8b8b93"
        LBL = ctk.CTkFont("Segoe UI", 13)
        SUB = ctk.CTkFont("Segoe UI", 11)

        win = ctk.CTkToplevel(self._root)
        self._settings_win = win
        win.title("Dicteer")
        win.geometry("900x640")
        win.minsize(860, 600)
        win.configure(fg_color=BG)
        try:
            win.iconbitmap(os.path.join(APP_DIR, "dicteer.ico"))
        except Exception:
            pass
        win.grid_columnconfigure(1, weight=1)
        win.grid_rowconfigure(0, weight=1)
        v = {}

        # -------- zijbalk --------
        side = ctk.CTkFrame(win, width=190, corner_radius=0, fg_color=SIDE)
        side.grid(row=0, column=0, rowspan=2, sticky="nsw")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="Dicteer",
                     font=ctk.CTkFont("Segoe UI", 22, "bold")).pack(
            anchor="w", padx=20, pady=(26, 0))
        ctk.CTkLabel(side, text=VERSION, font=SUB, text_color=DIM).pack(
            anchor="w", padx=20, pady=(0, 22))

        pages, nav_buttons = {}, {}
        content = ctk.CTkFrame(win, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew", padx=28, pady=(28, 0))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        def show(name):
            for p in pages.values():
                p.grid_remove()
            pages[name].grid(row=0, column=0, sticky="nsew")
            for n, b in nav_buttons.items():
                b.configure(fg_color=(CARD if n == name else "transparent"))

        def nav(name, label):
            b = ctk.CTkButton(side, text=label, anchor="w", corner_radius=8,
                              fg_color="transparent", hover_color=CARD, height=38,
                              font=LBL, command=lambda: show(name))
            b.pack(fill="x", padx=12, pady=3)
            nav_buttons[name] = b
            p = ctk.CTkScrollableFrame(content, fg_color="transparent")
            pages[name] = p
            return p

        # -------- kaart + rijen (alles strikt via grid) --------
        def card(page, titel):
            c = ctk.CTkFrame(page, corner_radius=14, fg_color=CARD)
            c.pack(fill="x", pady=(0, 16))
            c.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(c, text=titel,
                         font=ctk.CTkFont("Segoe UI", 15, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 4))
            c._row = 1
            return c

        def row(c, label, maak):
            """Label links (kolom 0, rekt mee), widget rechts (kolom 1)."""
            r = c._row
            c._row += 1
            ctk.CTkLabel(c, text=label, wraplength=400, justify="left",
                         font=LBL).grid(row=r, column=0, sticky="w",
                                        padx=20, pady=9)
            w = maak(c)
            w.grid(row=r, column=1, sticky="e", padx=20, pady=9)
            return w

        def hint(c, tekst):
            ctk.CTkLabel(c, text=tekst, font=SUB, text_color=DIM,
                         wraplength=560, justify="left").grid(
                row=c._row, column=0, columnspan=2, sticky="w",
                padx=20, pady=(0, 6))
            c._row += 1

        def einde(c):
            ctk.CTkLabel(c, text="", height=1).grid(row=c._row, column=0,
                                                    pady=(0, 8))
            c._row += 1

        def schakel(c, label, key, default=False):
            var = tk.BooleanVar(value=bool(cfg.get(key, default)))
            v[key] = var
            row(c, label, lambda m: ctk.CTkSwitch(
                m, text="", variable=var, width=46, progress_color=ACCENT))

        def keuze(c, label, key, waarden, huidig):
            var = tk.StringVar(value=huidig)
            v[key] = var
            row(c, label, lambda m: ctk.CTkOptionMenu(
                m, variable=var, values=waarden, width=240, fg_color=BG,
                button_color=ACCENT, button_hover_color=ACCENT_H))

        def invoer(c, label, key, huidig, geheim=False):
            var = tk.StringVar(value=huidig)
            v[key] = var
            row(c, label, lambda m: ctk.CTkEntry(
                m, textvariable=var, width=280, show=("*" if geheim else "")))

        # -------- General --------
        p = nav("general", tr("tab_general"))
        c = card(p, tr("tab_general"))
        invoer(c, tr("hotkey"), "hotkey", cfg.get("hotkey", "ctrl+shift+s"))
        keuze(c, tr("mode"), "mode", ["toggle", "hold"], cfg.get("mode", "toggle"))
        hint(c, f"{tr('mode_toggle')}   |   {tr('mode_hold')}")
        einde(c)

        c = card(p, tr("spoken_lang"))
        codes = [cc for cc, _ in LANGUAGES]
        names = [n or tr("lang_auto") for _, n in LANGUAGES]
        cur = cfg.get("language", "auto")
        keuze(c, tr("spoken_lang"), "_langname", names,
              names[codes.index(cur)] if cur in codes else names[0])
        keuze(c, tr("model"), "model",
              ["large-v3-turbo", "large-v3", "medium", "small"],
              cfg.get("model", "large-v3-turbo"))
        keuze(c, tr("device"), "device", ["auto", "cuda", "cpu"],
              cfg.get("device", "auto"))
        einde(c)

        c = card(p, tr("ui_lang"))
        ui_codes = [cc for cc, _ in UI_LANGUAGES]
        ui_names = [n for _, n in UI_LANGUAGES]
        cur_ui = cfg.get("ui_language", "en")
        keuze(c, tr("ui_lang"), "_uiname", ui_names,
              ui_names[ui_codes.index(cur_ui)] if cur_ui in ui_codes else "English")
        hint(c, tr("ui_lang_note"))
        einde(c)

        # -------- Recording --------
        p = nav("recording", tr("tab_recording"))
        c = card(p, tr("tab_recording"))
        schakel(c, tr("pause_media"), "pause_media", False)
        schakel(c, tr("dc_mute"), "discord_mute", False)
        schakel(c, tr("dc_deafen"), "discord_deafen", False)
        einde(c)

        c = card(p, tr("tab_audio"))
        mics = list_input_devices()
        cur_mic = cfg.get("input_device", "auto")
        if cur_mic not in mics:
            mics.append(cur_mic)
        keuze(c, tr("mic"), "input_device", mics, cur_mic)
        schakel(c, tr("live_preview"), "live_preview", True)
        schakel(c, tr("beep"), "beep", True)
        vol = tk.DoubleVar(value=float(cfg.get("beep_volume", 0.15)))
        v["beep_volume"] = vol
        row(c, tr("beep_vol"), lambda m: ctk.CTkSlider(
            m, from_=0.0, to=1.0, width=240, variable=vol,
            progress_color=ACCENT))
        schakel(c, tr("overlay"), "overlay", True)
        einde(c)

        # -------- Discord --------
        p = nav("discord", "Discord")
        c = card(p, "Discord")
        invoer(c, tr("dc_id"), "discord_client_id",
               cfg.get("discord_client_id", ""))
        invoer(c, tr("dc_secret"), "discord_client_secret",
               cfg.get("discord_client_secret", ""), geheim=True)
        row(c, tr("dc_note"), lambda m: ctk.CTkButton(
            m, text=tr("dc_link"), fg_color=ACCENT, hover_color=ACCENT_H,
            command=lambda: self.app._discord_link()))
        einde(c)

        # -------- Statistieken --------
        p = nav("stats", tr("tab_stats"))
        st = load_stats()
        c = card(p, tr("tab_stats"))

        def stat(label, waarde):
            row(c, label, lambda m, w=waarde: ctk.CTkLabel(
                m, text=w, font=ctk.CTkFont("Segoe UI", 15, "bold")))

        mins = st.get("seconds", 0.0) / 60
        bespaard = max(0.0, st.get("words", 0) / 40 - mins)
        stat(tr("st_dictations"), f"{st.get('dictations', 0)}")
        stat(tr("st_words"), f"{st.get('words', 0)}")
        stat(tr("st_audio"), f"{int(mins)} min")
        stat(tr("st_saved"), f"\u2248 {int(bespaard)} min")
        einde(c)

        # -------- System --------
        p = nav("system", tr("tab_system"))
        c = card(p, tr("tab_system"))
        auto = tk.BooleanVar(value=autostart_enabled())
        v["_autostart"] = auto
        row(c, tr("autostart"), lambda m: ctk.CTkSwitch(
            m, text="", variable=auto, width=46, progress_color=ACCENT))
        schakel(c, tr("history"), "history", True)
        schakel(c, tr("restore_clip"), "restore_clipboard", True)
        schakel(c, tr("show_start"), "show_settings_on_start", True)
        row(c, "", lambda m: ctk.CTkButton(
            m, text=tr("shortcut"), fg_color=ACCENT, hover_color=ACCENT_H,
            command=lambda: self.app.make_shortcut()))
        einde(c)

        # -------- knoppenbalk --------
        def sluiten():
            self._settings_win = None
            win.destroy()

        def toepassen():
            cfg["hotkey"] = v["hotkey"].get().strip() or "ctrl+shift+s"
            cfg["mode"] = v["mode"].get()
            cfg["language"] = codes[names.index(v["_langname"].get())]
            cfg["model"] = v["model"].get()
            cfg["device"] = v["device"].get()
            cfg["ui_language"] = ui_codes[ui_names.index(v["_uiname"].get())]
            cfg["beep_volume"] = round(float(v["beep_volume"].get()), 2)
            cfg["input_device"] = v["input_device"].get()
            for key in ("beep", "overlay", "live_preview", "pause_media", "history",
                        "restore_clipboard", "show_settings_on_start",
                        "discord_mute", "discord_deafen"):
                cfg[key] = bool(v[key].get())
            cfg["discord_client_id"] = v["discord_client_id"].get().strip()
            cfg["discord_client_secret"] = v["discord_client_secret"].get().strip()
            save_config(cfg)
            try:
                set_autostart(bool(v["_autostart"].get()))
            except Exception:
                log.exception("Autostart wijzigen mislukt")
            threading.Thread(target=self.app.reload_config, daemon=True).start()
            self.app._notify(tr("saved"))

        bar = ctk.CTkFrame(win, fg_color="transparent")
        bar.grid(row=1, column=1, sticky="e", padx=28, pady=18)
        ctk.CTkButton(bar, text=tr("cancel"), width=110, fg_color="transparent",
                      border_width=1, border_color="#3a3a40", hover_color=CARD,
                      command=sluiten).grid(row=0, column=0, padx=(0, 10))
        ctk.CTkButton(bar, text=tr("apply"), width=110, fg_color="transparent",
                      border_width=1, border_color=ACCENT, text_color=ACCENT,
                      hover_color=CARD, command=toepassen).grid(
            row=0, column=1, padx=(0, 10))
        ctk.CTkButton(bar, text=tr("save"), width=110, fg_color=ACCENT,
                      hover_color=ACCENT_H,
                      command=lambda: (toepassen(), sluiten())).grid(row=0, column=2)

        win.protocol("WM_DELETE_WINDOW", sluiten)
        show("general")


# ---------------------------------------------------------------- plakken

def paste_text(text, restore_clipboard=True):
    import keyboard
    import pyperclip

    old = None
    if restore_clipboard:
        try:
            old = pyperclip.paste()
        except Exception:
            old = None

    pyperclip.copy(text)

    # Wacht tot alle modifier-toetsen los zijn (anders wordt het bv. ctrl+alt+v)
    for _ in range(100):
        try:
            if not any(keyboard.is_pressed(k) for k in ("ctrl", "alt", "shift", "windows")):
                break
        except Exception:
            break
        time.sleep(0.05)

    keyboard.send("ctrl+v")

    if restore_clipboard and old is not None:
        def _restore():
            time.sleep(0.8)
            try:
                pyperclip.copy(old)
            except Exception:
                pass
        threading.Thread(target=_restore, daemon=True).start()


# ---------------------------------------------------------------- hoofdapp

class DicteerApp:
    STATES = {
        "laden":     ((128, 128, 128), "state_load"),
        "klaar":     ((46, 160, 67),   "state_ready"),
        "opname":    ((220, 50, 47),   "state_rec"),
        "verwerken": ((255, 153, 0),   "state_proc"),
        "fout":      ((0, 0, 0),       "state_err"),
    }

    def __init__(self):
        self.cfg = load_config()
        self.recorder = Recorder()
        self.model = None
        self.state = "laden"
        self.icon = None
        self.overlay = None
        self.history = load_history()
        self._busy = threading.Lock()
        self._hotkey_handle = None
        self._esc_handle = None
        self._discord_worker = DiscordMuteWorker(self)
        self._media = MediaController(self)
        self.preview_text = ""
        self.stats = load_stats()

    def _beep(self, freq, dur_ms):
        if self.cfg.get("beep", True):
            beep(freq, dur_ms, float(self.cfg.get("beep_volume", 0.15)))

    # ---------- model

    def load_model(self):
        try:
            setup_cuda_dlls()
            from faster_whisper import WhisperModel

            device = self.cfg["device"]
            attempts = []
            if device in ("auto", "cuda"):
                attempts.append(("cuda", "float16"))
            if device in ("auto", "cpu"):
                attempts.append(("cpu", "int8"))

            last_err = None
            for dev, ctype in attempts:
                try:
                    log.info("Model %s laden op %s (%s)...", self.cfg["model"], dev, ctype)
                    self.model = WhisperModel(self.cfg["model"], device=dev, compute_type=ctype)
                    log.info("Model geladen op %s.", dev)
                    break
                except Exception as e:
                    log.warning("Laden op %s mislukt: %s", dev, e)
                    last_err = e

            if self.model is None:
                raise last_err or RuntimeError("model laden mislukt")

            self.set_state("klaar")
            self._beep(880, 100)
            try:
                n = repair_microphone()
                if n:
                    self._notify(tr("n_mic_restored"))
            except Exception:
                log.exception("Microfoon-reparatie mislukt")
        except Exception:
            log.exception("Model laden definitief mislukt")
            self.set_state("fout")

    # ---------- status/tray

    def set_state(self, state):
        self.state = state
        if self.icon is not None:
            self.icon.icon = self._draw_icon(state)
            color, key = self.STATES[state]
            self.icon.title = ("Dicteer - " + tr(key)).format(hotkey=self.cfg["hotkey"])

    def _draw_icon(self, state):
        from PIL import Image, ImageDraw
        color, _ = self.STATES[state]
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((8, 8, 56, 56), fill=color + (255,))
        # microfoontje
        d.rounded_rectangle((27, 18, 37, 36), radius=5, fill=(255, 255, 255, 255))
        d.arc((22, 26, 42, 44), start=0, end=180, fill=(255, 255, 255, 255), width=3)
        d.line((32, 44, 32, 50), fill=(255, 255, 255, 255), width=3)
        return img

    # ---------- opnemen & transcriberen

    def start_recording(self):
        if self.state not in ("klaar",):
            return
        try:
            self.preview_text = ""
            self.recorder.start(self.cfg.get("input_device", "auto"))
            self.set_state("opname")
            self._beep(1000, 120)
            self._discord_mute(True)
            self._media_pause()
            if self.cfg.get("live_preview", True):
                threading.Thread(target=self._preview_loop, daemon=True).start()
        except Exception as e:
            log.exception("Opname starten mislukt (microfoon?)")
            self.set_state("fout")
            self._notify(tr("n_rec_fail") + str(e))

    def stop_and_transcribe(self):
        if not self.recorder.recording:
            return
        audio = self.recorder.stop()
        self.preview_text = ""
        self._discord_mute(False)
        self._media_resume()
        self._beep(700, 120)
        self.set_state("verwerken")
        threading.Thread(target=self._transcribe, args=(audio,), daemon=True).start()

    def _transcribe(self, audio):
        with self._busy:
            try:
                if audio is None or len(audio) < SAMPLE_RATE * float(self.cfg["min_seconds"]):
                    self.set_state("klaar")
                    return
                lang = self.cfg["language"]
                lang = None if lang == "auto" else lang
                segments, info = self.model.transcribe(
                    audio,
                    language=lang,
                    beam_size=int(self.cfg["beam_size"]),
                    vad_filter=True,
                )
                text = " ".join(s.text.strip() for s in segments).strip()
                log.info("Transcriptie (%s): %r", getattr(info, "language", "?"), text)
                if text:
                    self._add_history(text)
                    self.stats["dictations"] += 1
                    self.stats["words"] += len(text.split())
                    self.stats["seconds"] += len(audio) / SAMPLE_RATE
                    save_stats(self.stats)
                    paste_text(text, self.cfg.get("restore_clipboard", True))
            except Exception:
                log.exception("Transcriptie mislukt")
            finally:
                self.set_state("klaar")

    # ---------- sneltoets

    def on_hotkey(self):
        if self.state == "laden":
            self._beep(300, 200)
            return
        if self.cfg["mode"] == "toggle":
            if self.recorder.recording:
                self.stop_and_transcribe()
            else:
                self.start_recording()
        else:  # hold
            if not self.recorder.recording:
                self.start_recording()
                threading.Thread(target=self._wait_for_release, daemon=True).start()

    def _wait_for_release(self):
        import keyboard
        time.sleep(0.15)
        try:
            while keyboard.is_pressed(self.cfg["hotkey"]):
                time.sleep(0.03)
        except Exception:
            pass
        self.stop_and_transcribe()

    def register_hotkey(self):
        import keyboard
        self._hotkey_handle = keyboard.add_hotkey(
            self.cfg["hotkey"], self.on_hotkey,
            suppress=bool(self.cfg.get("suppress_hotkey", True)),
        )
        self._esc_handle = keyboard.add_hotkey("esc", self.on_escape, suppress=False)
        log.info("Sneltoets actief: %s (modus: %s)", self.cfg["hotkey"], self.cfg["mode"])

    def reload_config(self, icon=None, item=None):
        """Herlaad config.json zonder herstart. Nieuwe sneltoets werkt direct;
        een ander model wordt op de achtergrond opnieuw geladen."""
        import keyboard
        old = self.cfg
        self.cfg = load_config()
        try:
            keyboard.remove_hotkey(self._hotkey_handle)
            if self._esc_handle is not None:
                keyboard.remove_hotkey(self._esc_handle)
        except Exception:
            keyboard.unhook_all()
        self.register_hotkey()
        if (old["model"] != self.cfg["model"]) or (old["device"] != self.cfg["device"]):
            self.model = None
            self.set_state("laden")
            threading.Thread(target=self.load_model, daemon=True).start()
        else:
            self.set_state(self.state)  # ververs traytitel (nieuwe hotkey)
        try:
            if self.icon is not None:
                self.icon.menu = self.build_menu()  # nieuwe UI-taal/labels
                self.icon.update_menu()
        except Exception:
            pass
        log.info("Config herladen.")

    def _notify(self, msg):
        """Windows-melding via het tray-icoon."""
        try:
            if self.icon is not None:
                self.icon.notify(msg, "Dicteer")
        except Exception:
            pass

    def _add_history(self, text):
        if not self.cfg.get("history", True):
            return
        self.history.insert(0, {"t": time.strftime("%H:%M"), "text": text})
        self.history = self.history[:10]
        save_history(self.history)
        if self.icon is not None:
            try:
                self.icon.update_menu()
            except Exception:
                pass

    def _copy_history(self, text):
        def handler(icon, item):
            import pyperclip
            pyperclip.copy(text)
        return handler

    def _history_items(self):
        from pystray import MenuItem as Item
        if not self.history:
            yield Item(tr("hist_empty"), None, enabled=False)
            return
        for e in self.history:
            txt = e.get("text", "")
            label = f"{e.get('t', '')}  {txt[:45]}" + ("..." if len(txt) > 45 else "")
            yield Item(label, self._copy_history(txt))

    def _toggle_autostart(self, icon=None, item=None):
        set_autostart(not autostart_enabled())

    def open_settings(self, icon=None, item=None):
        """Open het instellingenvenster (dubbelklik op tray-icoon of via menu)."""
        if self.overlay is None:
            self.overlay = Overlay(self)
        self.overlay.open_settings()

    def make_shortcut(self, icon=None, item=None):
        def _t():
            try:
                make_desktop_shortcut()
                self._notify(tr("n_shortcut_ok"))
            except Exception:
                log.exception("Snelkoppeling maken mislukt")
                self._notify(tr("n_shortcut_fail"))
        threading.Thread(target=_t, daemon=True).start()

    def _discord_configured(self):
        return bool(self.cfg.get("discord_client_id")) and \
            bool(self.cfg.get("discord_client_secret"))

    def _discord_mute(self, mute):
        """Demp/deafen Discord via de permanente RPC-verbinding."""
        if not (self.cfg.get("discord_mute", False)
                or self.cfg.get("discord_deafen", False)):
            return
        if not self._discord_configured():
            return
        self._discord_worker.request(mute)

    def _media_pause(self):
        if not self.cfg.get("pause_media", False):
            return
        threading.Thread(target=self._media.pause_playing, daemon=True).start()

    def _media_resume(self):
        if not self.cfg.get("pause_media", False):
            return
        threading.Thread(target=self._media.resume_paused, daemon=True).start()

    def _preview_loop(self):
        """Live meelezen: transcribeer tijdens de opname elke paar seconden
        de tot dan toe opgenomen audio (alleen als de GPU vrij is)."""
        import numpy as np
        while self.recorder.recording and self.cfg.get("live_preview", True):
            time.sleep(1.0)
            if not self.recorder.recording or self.model is None:
                break
            chunks = list(self.recorder._chunks)
            if not chunks:
                continue
            audio = np.concatenate(chunks, axis=0).flatten()
            if len(audio) < SAMPLE_RATE:
                continue
            # alleen de laatste ~15 s meenemen: preview blijft snel,
            # ook bij lange dictaten
            audio = audio[-15 * SAMPLE_RATE:]
            if not self._busy.acquire(blocking=False):
                continue
            try:
                lang = self.cfg["language"]
                lang = None if lang == "auto" else lang
                segments, _ = self.model.transcribe(
                    audio, language=lang, beam_size=1, vad_filter=True,
                    condition_on_previous_text=False)
                tekst = " ".join(s.text.strip() for s in segments).strip()
                if self.recorder.recording:
                    self.preview_text = tekst
            except Exception:
                pass
            finally:
                self._busy.release()

    def on_escape(self, *args):
        if self.recorder.recording:
            self.cancel_recording()

    def cancel_recording(self):
        """Esc: opname weggooien zonder te transcriberen."""
        if not self.recorder.recording:
            return
        self.recorder.stop()  # audio bewust weggooien
        self.preview_text = ""
        self._discord_mute(False)
        self._media_resume()
        self._beep(400, 150)
        self.set_state("klaar")
        log.info("Opname geannuleerd (Esc).")

    def _discord_link(self, icon=None, item=None):
        """Eenmalige koppeling + test: 2 seconden dempen."""
        def _t():
            try:
                if not self._discord_configured():
                    self._notify(tr("n_fill"))
                    return
                self._notify(tr("n_link_watch"))
                discord_rpc_set_mute(self.cfg, True, interactive=True)
                time.sleep(2)
                discord_rpc_set_mute(self.cfg, False)
                if not self.cfg.get("discord_mute", False):
                    self.cfg["discord_mute"] = True
                    save_config(self.cfg)
                self._notify(tr("n_linked"))
            except Exception as e:
                log.exception("Discord koppelen mislukt")
                self._notify(tr("n_link_fail") + str(e))
        threading.Thread(target=_t, daemon=True).start()

    # ---------- traymenu

    def _set_mode(self, mode):
        def handler(icon, item):
            self.cfg["mode"] = mode
            save_config(self.cfg)
        return handler

    def _set_lang(self, lang):
        def handler(icon, item):
            self.cfg["language"] = lang
            save_config(self.cfg)
        return handler

    def _toggle_cfg(self, key):
        def handler(icon, item):
            self.cfg[key] = not self.cfg.get(key, False)
            save_config(self.cfg)
            if key in ("discord_mute", "discord_deafen") and self.cfg[key] \
                    and not self._discord_configured():
                self._notify(tr("n_fill"))
        return handler

    def build_menu(self):
        import pystray
        from pystray import Menu, MenuItem as Item
        return Menu(
            Item(lambda item: f"{tr('menu_hotkey')}: {self.cfg['hotkey']}",
                 None, enabled=False),
            Menu.SEPARATOR,
            Item(tr("menu_settings"), self.open_settings, default=True),
            Item(tr("menu_mode"), Menu(
                Item(tr("menu_mode_hold"), self._set_mode("hold"),
                     checked=lambda i: self.cfg["mode"] == "hold", radio=True),
                Item(tr("menu_mode_toggle"), self._set_mode("toggle"),
                     checked=lambda i: self.cfg["mode"] == "toggle", radio=True),
            )),
            Item(tr("menu_lang"), Menu(*[
                Item(naam or tr("lang_auto"), self._set_lang(code), radio=True,
                     checked=(lambda c: (lambda i: self.cfg["language"] == c))(code))
                for code, naam in LANGUAGES
            ])),
            Item(tr("menu_history"), Menu(self._history_items)),
            Menu.SEPARATOR,
            Item(tr("menu_dc_mute"), self._toggle_cfg("discord_mute"),
                 checked=lambda i: bool(self.cfg.get("discord_mute", False))),
            Item(tr("menu_dc_deafen"), self._toggle_cfg("discord_deafen"),
                 checked=lambda i: bool(self.cfg.get("discord_deafen", False))),
            Item(tr("menu_media"), self._toggle_cfg("pause_media"),
                 checked=lambda i: bool(self.cfg.get("pause_media", False))),
            Item(tr("menu_dc_link"), self._discord_link),
            Item(tr("menu_autostart"), self._toggle_autostart,
                 checked=lambda i: autostart_enabled()),
            Menu.SEPARATOR,
            Item(tr("menu_config"), lambda icon, item: os.startfile(CONFIG_PATH)),
            Item(tr("menu_reload"), self.reload_config),
            Item(tr("menu_log"), lambda icon, item: os.startfile(LOG_PATH)),
            Menu.SEPARATOR,
            Item(tr("menu_quit"), self.quit),
        )

    def quit(self, icon=None, item=None):
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass
        if self.icon is not None:
            self.icon.stop()
        if self.overlay is not None:
            self.overlay.request_quit()

    # ---------- run

    def run(self):
        import pystray
        self.icon = pystray.Icon(
            "dicteer",
            icon=self._draw_icon("laden"),
            title="Dicteer - " + tr(self.STATES["laden"][1]),
            menu=self.build_menu(),
        )
        self.register_hotkey()
        self.overlay = Overlay(self)
        if self.cfg.get("show_settings_on_start", True):
            self.overlay.open_settings()
        threading.Thread(target=self.load_model, daemon=True).start()
        self.icon.run_detached()       # tray-icoon in eigen thread
        self.overlay.run_mainloop()    # UI op de hoofdthread (blokkeert)
        try:
            self.icon.stop()
        except Exception:
            pass


def ensure_single_instance():
    """Zorg dat er maar een Dicteer tegelijk draait (Windows-mutex)."""
    if os.name != "nt":
        return True
    import ctypes
    ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\Dicteer_single_instance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.user32.MessageBoxW(
            None,
            "Dicteer is already running!\n\nLook for the microphone icon in the "
            "system tray (bottom right, behind the ^ arrow). To restart, choose "
            "Exit there first.",
            "Dicteer", 0x40)  # MB_ICONINFORMATION
        return False
    return True


def main():
    if not ensure_single_instance():
        return
    setup_app_identity()
    log.info("=== Dicteer gestart (%s) ===", VERSION)
    try:
        app = DicteerApp()
        app.run()
    except Exception as e:
        log.exception("Dicteer gecrasht")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None, f"Dicteer is gecrasht:\n{e}\n\nZie dicteer.log en "
                      "dicteer_crash.log in de Dicteer-map.", "Dicteer", 0x10)
        except Exception:
            pass


if __name__ == "__main__":
    main()
