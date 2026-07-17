"""
Dicteer - lokale spraak-naar-tekst voor Windows.

Zoals Wispr Flow, maar gratis en 100% lokaal (faster-whisper op je eigen GPU/CPU).
Druk de sneltoets in, praat, en de tekst wordt geplakt in het venster waar je cursor staat.

Twee modi (instelbaar via het instellingenvenster, tray-icoon of config.json):
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

VERSION = "v29"

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
LOG_PATH = os.path.join(APP_DIR, "dicteer.log")
HISTORY_PATH = os.path.join(APP_DIR, "history.json")
DISCORD_TOKEN_PATH = os.path.join(APP_DIR, "discord_token.json")
STATS_PATH = os.path.join(APP_DIR, "stats.json")
VOCAB_PATH = os.path.join(APP_DIR, "vocabulary.txt")
REPL_PATH = os.path.join(APP_DIR, "replacements.txt")
DICTATIONS_PATH = os.path.join(APP_DIR, "dictations.txt")
PROJECTS_PATH = os.path.join(APP_DIR, "projects.json")
PROJECTS_DIR = os.path.join(APP_DIR, "projects")

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
    "check_updates": True,       # dagelijks controleren op nieuwe releases (GitHub)
    "vocabulary": [],            # woorden/namen die beter herkend moeten worden
    "replacements": {},          # vervangregels: {"fout": "goed"}
    "auto_enter": False,         # Enter indrukken na het plakken (direct versturen)
    "mouse_button": "none",      # zijknop muis als push-to-talk: "none", "x" of "x2"
    "repaste_hotkey": "ctrl+shift+v",  # laatste dictaat opnieuw plakken
    "restore_clipboard": True,
    "min_seconds": 0.4,
    "projects_enabled": False,   # dictaten per project bewaren (opt-in)
    "current_project": "",       # actief project (leeg = geen)
    "mute_other_apps": False,    # mic dempen voor alle andere apps tijdens opname
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
 "backup_title": "Backup & export",
 "backup": "Back up all settings to a zip file",
 "restore": "Restore a backup",
 "export_dict": "Export all dictations to a file (for ChatGPT / projects)",
 "copy_dict": "Copy all dictations to the clipboard",
 "btn_backup": "Back up...",
 "btn_restore": "Restore...",
 "btn_export": "Export...",
 "btn_copy": "Copy",
 "n_backup_ok": "Backup saved.",
 "n_backup_fail": "Backup failed - see dicteer.log.",
 "n_restore_ok": "Backup restored.",
 "n_restore_fail": "Restore failed - see dicteer.log.",
 "n_export_ok": "Dictations exported.",
 "n_copied": "All dictations copied to the clipboard.",
 "n_empty": "No dictations recorded yet.",
 "dict_wrong": "Wrong word",
 "dict_right": "Replace with",
 "btn_add": "Add",
 "dict_files_note": "Stored in vocabulary.txt and replacements.txt next to the app - easy to back up.",
 "tab_dict": "Dictionary", "auto_enter": "Press Enter after pasting (auto-send, handy for AI chats)",
 "dict_words": "Words and names to recognize better (one per line)", "dict_repl": "Replacements (one per line:  wrong => right)",
 "mouse_ptt": "Mouse side button = push-to-talk", "repaste": "Hotkey: paste last dictation again",
 "dc_setup_title": "How to link Discord (one-time, ~5 min)", "dc_portal": "Open Discord Developer Portal",
 "dc_steps": "1. Open the Discord Developer Portal (button below) and click 'New Application'; name it e.g. 'Dicteer'.\n2. On the OAuth2 tab: copy the Client ID, click 'Reset Secret' and copy the Client Secret.\n3. Under 'Redirects', add  http://127.0.0.1  and save.\n4. Paste the Client ID and Secret above and click Apply.\n5. Click 'Link / test Discord' and approve the popup inside Discord - your mic is muted for 2 seconds as a test.",
 "update_available": "Update available", "check_updates": "Check for updates automatically",
 "n_update": "Dicteer {tag} is available! Open the settings to view it.",
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
 "dc_link": "Link / test Discord", "dc_note": "One-time setup required - see the steps below.",
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
 "grp_controls": "Controls", "grp_language": "Language & model",
 "grp_during": "While recording", "grp_behavior": "Behavior",
 "grp_link": "Connection",
 "hotkey_lbl": "Hotkey", "hotkey_sub": "Starts and stops dictation",
 "model_lbl": "Model", "model_sub": "Reloaded after saving",
 "seg_toggle": "Toggle", "seg_hold": "Hold",
 "opt_none": "Off", "opt_auto": "Automatic",
 "press_keys": "Press a key combination…",
 "hk_click": "Click to record a shortcut", "edit_text": "Edit as text",
 "unsaved": "You have unsaved changes", "undo": "Undo",
 "repl_empty": "No replacement rules yet.", "btn_remove": "Remove",
 "btn_create": "Create", "unit_hour": "h",
 "beep_vol_lbl": "Beep volume",
 "ov_enter_on": "Auto-paste on", "ov_enter_off": "Auto-paste off",
 "auto_enter_sub": "Can be turned off per dictation with one click in the overlay",
 "tab_projects": "Projects",
 "projects_enable": "Use projects",
 "projects_enable_sub": "New dictations are also saved under the active project",
 "grp_proj_list": "Projects",
 "proj_new_ph": "New project name…",
 "proj_none": "No projects yet - add one above.",
 "proj_active": "Active", "proj_set_active": "Activate",
 "proj_count_suffix": "dictations",
 "proj_remove_note": "Removing a project keeps its dictations file in the 'projects' folder next to the app.",
 "tab_history": "History", "hist_recent": "Recent dictations",
 "proj_entries_title": "Project dictations",
 "proj_no_entries": "No dictations in this project yet.",
 "proj_header_title": "AI instruction for the active project",
 "proj_header_sub": "Added at the top of the export and clipboard copy",
 "proj_header_ph": "E.g. Summarize these dictations…",
 "btn_open": "Open", "mic_test": "Test microphone",
 "n_copied_one": "Copied to the clipboard.",
 "mute_apps": "Mute your virtual microphone while recording",
 "mute_apps_sub": "Mutes virtual mics (Voicemod, Voicemeeter…) that other apps listen to, so nobody hears your dictation. Only works with such a virtual mic setup",
 "mute_warn_novirt": "No virtual microphone found. Windows cannot mute a microphone per app, so without a virtual mic (e.g. Voicemod or VB-Cable) there is nothing to mute. Muting Discord does work - see the Discord page.",
 "grp_mic": "Microphone",
 "mic_auto": "Automatic (default device)",
 "mic_sub": "Using a virtual microphone (Voicemod, Voicemeeter…)? Select your REAL microphone here",
 "mute_warn_auto": "Select your real microphone above first - with 'Automatic', Dicteer can't tell which mic to protect, so nothing will be muted.",
 "mute_warn_virtual": "This looks like a virtual microphone. Select your real microphone above, otherwise your dictation goes silent and nothing will be muted.",
 "mute_ok": "Set up correctly: Dicteer protects this microphone and mutes your virtual mics while dictating.",
 "n_cpu_mode": "No NVIDIA GPU found - Dicteer is using the processor. That works fine but is slower; the 'medium' or 'small' model is faster on CPU.",
},
"nl": {
 "backup_title": "Backup & export",
 "backup": "Alle instellingen opslaan in een zip-bestand",
 "restore": "Een backup terugzetten",
 "export_dict": "Alle dictaten exporteren naar een bestand (voor ChatGPT / projecten)",
 "copy_dict": "Alle dictaten naar het klembord kopiëren",
 "btn_backup": "Backup...",
 "btn_restore": "Terugzetten...",
 "btn_export": "Exporteren...",
 "btn_copy": "Kopiëren",
 "n_backup_ok": "Backup opgeslagen.",
 "n_backup_fail": "Backup mislukt - zie dicteer.log.",
 "n_restore_ok": "Backup teruggezet.",
 "n_restore_fail": "Terugzetten mislukt - zie dicteer.log.",
 "n_export_ok": "Dictaten geëxporteerd.",
 "n_copied": "Alle dictaten gekopieerd naar het klembord.",
 "n_empty": "Nog geen dictaten opgeslagen.",
 "dict_wrong": "Fout woord",
 "dict_right": "Vervangen door",
 "btn_add": "Toevoegen",
 "dict_files_note": "Opgeslagen in vocabulary.txt en replacements.txt naast het programma - makkelijk te backuppen.",
 "tab_dict": "Woordenboek", "auto_enter": "Enter indrukken na het plakken (direct versturen, handig bij AI-chats)",
 "dict_words": "Woorden en namen die beter herkend moeten worden (één per regel)", "dict_repl": "Vervangingen (één per regel:  fout => goed)",
 "mouse_ptt": "Zijknop muis = push-to-talk", "repaste": "Sneltoets: laatste dictaat opnieuw plakken",
 "dc_setup_title": "Discord koppelen (eenmalig, ±5 min)", "dc_portal": "Open Discord Developer Portal",
 "dc_steps": "1. Open het Discord Developer Portal (knop hieronder) en klik op 'New Application'; noem hem bijv. 'Dicteer'.\n2. Ga naar het tabblad OAuth2: kopieer de Client ID, klik op 'Reset Secret' en kopieer de Client Secret.\n3. Voeg onder 'Redirects' toe:  http://127.0.0.1  en sla op.\n4. Plak de Client ID en Secret hierboven en klik op Toepassen.\n5. Klik op 'Discord koppelen / testen' en keur het venster in Discord goed - je mic gaat als test 2 seconden op mute.",
 "update_available": "Update beschikbaar", "check_updates": "Automatisch controleren op updates",
 "n_update": "Dicteer {tag} is beschikbaar! Open de instellingen om hem te bekijken.",
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
 "dc_link": "Discord koppelen / testen", "dc_note": "Eenmalige setup nodig - volg de stappen hieronder.",
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
 "grp_controls": "Bediening", "grp_language": "Taal & model",
 "grp_during": "Tijdens de opname", "grp_behavior": "Gedrag",
 "grp_link": "Koppeling",
 "hotkey_lbl": "Sneltoets", "hotkey_sub": "Start en stopt het dicteren",
 "model_lbl": "Model", "model_sub": "Wordt na opslaan opnieuw geladen",
 "seg_toggle": "Drukken", "seg_hold": "Vasthouden",
 "opt_none": "Uit", "opt_auto": "Automatisch",
 "press_keys": "Druk een toetsencombinatie…",
 "hk_click": "Klik om een sneltoets vast te leggen", "edit_text": "Als tekst bewerken",
 "unsaved": "Je hebt niet-opgeslagen wijzigingen", "undo": "Ongedaan maken",
 "repl_empty": "Nog geen vervangregels.", "btn_remove": "Verwijderen",
 "btn_create": "Aanmaken", "unit_hour": "u",
 "beep_vol_lbl": "Volume piepjes",
 "ov_enter_on": "Automatisch plakken aan", "ov_enter_off": "Automatisch plakken uit",
 "auto_enter_sub": "Per dictaat uit te zetten met één klik in de overlay",
 "tab_projects": "Projecten",
 "projects_enable": "Projecten gebruiken",
 "projects_enable_sub": "Nieuwe dictaten worden ook onder het actieve project bewaard",
 "grp_proj_list": "Projecten",
 "proj_new_ph": "Naam nieuw project…",
 "proj_none": "Nog geen projecten - voeg er hierboven een toe.",
 "proj_active": "Actief", "proj_set_active": "Activeren",
 "proj_count_suffix": "dictaten",
 "proj_remove_note": "Bij verwijderen blijft het dictatenbestand staan in de map 'projects' naast het programma.",
 "tab_history": "Geschiedenis", "hist_recent": "Laatste dictaten",
 "proj_entries_title": "Projectdictaten",
 "proj_no_entries": "Nog geen dictaten in dit project.",
 "proj_header_title": "AI-instructie voor het actieve project",
 "proj_header_sub": "Komt bovenaan de export en de klembordkopie",
 "proj_header_ph": "Bijv. Vat deze dictaten samen…",
 "btn_open": "Openen", "mic_test": "Microfoon testen",
 "n_copied_one": "Gekopieerd naar het klembord.",
 "mute_apps": "Je virtuele microfoon dempen tijdens de opname",
 "mute_apps_sub": "Dempt virtuele mics (Voicemod, Voicemeeter…) waar andere apps naar luisteren - zo hoort niemand je dictaat. Werkt alleen met zo'n virtuele mic-setup",
 "mute_warn_novirt": "Geen virtuele microfoon gevonden. Windows kan een microfoon niet per app dempen, dus zonder virtuele mic (bijv. Voicemod of VB-Cable) valt er niets te dempen. Discord dempen kan wél - zie de Discord-pagina.",
 "grp_mic": "Microfoon",
 "mic_auto": "Automatisch (standaardapparaat)",
 "mic_sub": "Gebruik je een virtuele microfoon (Voicemod, Voicemeeter…)? Kies hier je ÉCHTE microfoon",
 "mute_warn_auto": "Kies eerst hierboven je échte microfoon - bij 'Automatisch' weet Dicteer niet welke mic beschermd moet worden en wordt er niets gedempt.",
 "mute_warn_virtual": "Dit lijkt een virtuele microfoon. Kies hierboven je échte microfoon, anders valt je dictaat stil en wordt er niets gedempt.",
 "mute_ok": "Goed ingesteld: Dicteer beschermt deze microfoon en dempt je virtuele mics tijdens het dicteren.",
 "n_cpu_mode": "Geen NVIDIA-videokaart gevonden - Dicteer gebruikt de processor. Dat werkt prima maar is trager; het model 'medium' of 'small' is sneller op de CPU.",
},
"de": {
 "backup_title": "Backup & Export",
 "backup": "Alle Einstellungen in einer Zip-Datei sichern",
 "restore": "Ein Backup wiederherstellen",
 "export_dict": "Alle Diktate in eine Datei exportieren (für ChatGPT / Projekte)",
 "copy_dict": "Alle Diktate in die Zwischenablage kopieren",
 "btn_backup": "Sichern...",
 "btn_restore": "Wiederherstellen...",
 "btn_export": "Exportieren...",
 "btn_copy": "Kopieren",
 "n_backup_ok": "Backup gespeichert.",
 "n_backup_fail": "Backup fehlgeschlagen - siehe dicteer.log.",
 "n_restore_ok": "Backup wiederhergestellt.",
 "n_restore_fail": "Wiederherstellung fehlgeschlagen - siehe dicteer.log.",
 "n_export_ok": "Diktate exportiert.",
 "n_copied": "Alle Diktate in die Zwischenablage kopiert.",
 "n_empty": "Noch keine Diktate gespeichert.",
 "dict_wrong": "Falsches Wort",
 "dict_right": "Ersetzen durch",
 "btn_add": "Hinzufügen",
 "dict_files_note": "Gespeichert in vocabulary.txt und replacements.txt neben dem Programm - leicht zu sichern.",
 "tab_dict": "Wörterbuch", "auto_enter": "Nach dem Einfügen Enter drücken (direkt senden, praktisch für KI-Chats)",
 "dict_words": "Wörter und Namen zur besseren Erkennung (eins pro Zeile)", "dict_repl": "Ersetzungen (eine pro Zeile:  falsch => richtig)",
 "mouse_ptt": "Maus-Seitentaste = Push-to-talk", "repaste": "Tastenkürzel: letztes Diktat erneut einfügen",
 "dc_setup_title": "Discord verknüpfen (einmalig, ca. 5 Min.)", "dc_portal": "Discord Developer Portal öffnen",
 "dc_steps": "1. Öffne das Discord Developer Portal (Button unten) und klicke auf 'New Application'; nenne sie z. B. 'Dicteer'.\n2. Im Tab OAuth2: kopiere die Client-ID, klicke auf 'Reset Secret' und kopiere das Client-Secret.\n3. Füge unter 'Redirects' hinzu:  http://127.0.0.1  und speichere.\n4. Füge Client-ID und Secret oben ein und klicke auf Übernehmen.\n5. Klicke auf 'Discord verknüpfen / testen' und bestätige das Fenster in Discord - dein Mikro wird zum Test 2 Sekunden stummgeschaltet.",
 "update_available": "Update verfügbar", "check_updates": "Automatisch nach Updates suchen",
 "n_update": "Dicteer {tag} ist verfügbar! Öffne die Einstellungen.",
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
 "dc_link": "Discord verknüpfen / testen", "dc_note": "Einmalige Einrichtung nötig - siehe Schritte unten.",
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
 "grp_controls": "Bedienung", "grp_language": "Sprache & Modell",
 "grp_during": "Während der Aufnahme", "grp_behavior": "Verhalten",
 "grp_link": "Verknüpfung",
 "hotkey_lbl": "Tastenkürzel", "hotkey_sub": "Startet und stoppt das Diktieren",
 "model_lbl": "Modell", "model_sub": "Wird nach dem Speichern neu geladen",
 "seg_toggle": "Drücken", "seg_hold": "Halten",
 "opt_none": "Aus", "opt_auto": "Automatisch",
 "press_keys": "Tastenkombination drücken…",
 "hk_click": "Klicken, um ein Kürzel aufzunehmen", "edit_text": "Als Text bearbeiten",
 "unsaved": "Du hast ungespeicherte Änderungen", "undo": "Rückgängig",
 "repl_empty": "Noch keine Ersetzungsregeln.", "btn_remove": "Entfernen",
 "btn_create": "Erstellen", "unit_hour": "Std.",
 "beep_vol_lbl": "Lautstärke der Signaltöne",
 "ov_enter_on": "Auto-Einfügen an", "ov_enter_off": "Auto-Einfügen aus",
 "auto_enter_sub": "Pro Diktat per Klick im Overlay abschaltbar",
 "tab_projects": "Projekte", "projects_enable": "Projekte verwenden",
 "projects_enable_sub": "Neue Diktate werden zusätzlich im aktiven Projekt gespeichert",
 "grp_proj_list": "Projekte", "proj_new_ph": "Name des neuen Projekts…",
 "proj_none": "Noch keine Projekte - füge oben eins hinzu.",
 "proj_active": "Aktiv", "proj_set_active": "Aktivieren",
 "proj_count_suffix": "Diktate",
 "proj_remove_note": "Beim Entfernen bleibt die Diktatdatei im Ordner 'projects' neben dem Programm erhalten.",
 "tab_history": "Verlauf", "hist_recent": "Letzte Diktate",
 "proj_entries_title": "Projekt-Diktate",
 "proj_no_entries": "Noch keine Diktate in diesem Projekt.",
 "proj_header_title": "KI-Anweisung für das aktive Projekt",
 "proj_header_sub": "Steht oben im Export und in der Zwischenablage-Kopie",
 "proj_header_ph": "Z. B. Fasse diese Diktate zusammen…",
 "btn_open": "Öffnen", "mic_test": "Mikrofon testen",
 "n_copied_one": "In die Zwischenablage kopiert.",
 "mute_apps": "Virtuelles Mikrofon während der Aufnahme stummschalten",
 "mute_apps_sub": "Schaltet virtuelle Mikros (Voicemod, Voicemeeter…) stumm, die andere Apps abhören - so hört niemand dein Diktat. Funktioniert nur mit so einem virtuellen Mikro-Setup",
 "mute_warn_novirt": "Kein virtuelles Mikrofon gefunden. Windows kann ein Mikrofon nicht pro App stummschalten - ohne virtuelles Mikro (z. B. Voicemod oder VB-Cable) gibt es nichts stummzuschalten. Discord geht trotzdem - siehe die Discord-Seite.",
 "grp_mic": "Mikrofon",
 "mic_auto": "Automatisch (Standardgerät)",
 "mic_sub": "Nutzt du ein virtuelles Mikrofon (Voicemod, Voicemeeter…)? Wähle hier dein ECHTES Mikrofon",
 "mute_warn_auto": "Wähle zuerst oben dein echtes Mikrofon - bei 'Automatisch' weiß Dicteer nicht, welches Mikro geschützt werden soll, und es wird nichts stummgeschaltet.",
 "mute_warn_virtual": "Das sieht nach einem virtuellen Mikrofon aus. Wähle oben dein echtes Mikrofon, sonst verstummt dein Diktat und es wird nichts stummgeschaltet.",
 "mute_ok": "Richtig eingerichtet: Dicteer schützt dieses Mikrofon und schaltet deine virtuellen Mikros beim Diktieren stumm.",
 "n_cpu_mode": "Keine NVIDIA-Grafikkarte gefunden - Dicteer nutzt den Prozessor. Das funktioniert, ist aber langsamer; das Modell 'medium' oder 'small' ist auf der CPU schneller.",
},
"es": {
 "backup_title": "Copia y exportación",
 "backup": "Guardar todos los ajustes en un zip",
 "restore": "Restaurar una copia",
 "export_dict": "Exportar todos los dictados a un archivo (para ChatGPT / proyectos)",
 "copy_dict": "Copiar todos los dictados al portapapeles",
 "btn_backup": "Guardar...",
 "btn_restore": "Restaurar...",
 "btn_export": "Exportar...",
 "btn_copy": "Copiar",
 "n_backup_ok": "Copia guardada.",
 "n_backup_fail": "Error en la copia - ver dicteer.log.",
 "n_restore_ok": "Copia restaurada.",
 "n_restore_fail": "Error al restaurar - ver dicteer.log.",
 "n_export_ok": "Dictados exportados.",
 "n_copied": "Todos los dictados copiados al portapapeles.",
 "n_empty": "Aún no hay dictados guardados.",
 "dict_wrong": "Palabra errónea",
 "dict_right": "Sustituir por",
 "btn_add": "Añadir",
 "dict_files_note": "Guardado en vocabulary.txt y replacements.txt junto al programa - fácil de respaldar.",
 "tab_dict": "Diccionario", "auto_enter": "Pulsar Enter tras pegar (envío automático, útil en chats de IA)",
 "dict_words": "Palabras y nombres a reconocer mejor (uno por línea)", "dict_repl": "Sustituciones (una por línea:  mal => bien)",
 "mouse_ptt": "Botón lateral del ratón = pulsar para hablar", "repaste": "Atajo: pegar de nuevo el último dictado",
 "dc_setup_title": "Vincular Discord (una vez, ~5 min)", "dc_portal": "Abrir Discord Developer Portal",
 "dc_steps": "1. Abre el Discord Developer Portal (botón de abajo) y haz clic en 'New Application'; llámala p. ej. 'Dicteer'.\n2. En la pestaña OAuth2: copia el Client ID, haz clic en 'Reset Secret' y copia el Client Secret.\n3. En 'Redirects' añade  http://127.0.0.1  y guarda.\n4. Pega el Client ID y el Secret arriba y pulsa Aplicar.\n5. Pulsa 'Vincular / probar Discord' y aprueba la ventana en Discord: tu micro se silencia 2 segundos como prueba.",
 "update_available": "Actualización disponible", "check_updates": "Buscar actualizaciones automáticamente",
 "n_update": "¡Dicteer {tag} está disponible! Abre los ajustes para verlo.",
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
 "dc_link": "Vincular / probar Discord", "dc_note": "Requiere configuración única: sigue los pasos de abajo.",
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
 "grp_controls": "Controles", "grp_language": "Idioma y modelo",
 "grp_during": "Durante la grabación", "grp_behavior": "Comportamiento",
 "grp_link": "Conexión",
 "hotkey_lbl": "Atajo de teclado", "hotkey_sub": "Inicia y detiene el dictado",
 "model_lbl": "Modelo", "model_sub": "Se recarga después de guardar",
 "seg_toggle": "Pulsar", "seg_hold": "Mantener",
 "opt_none": "No", "opt_auto": "Automático",
 "press_keys": "Pulsa una combinación de teclas…",
 "hk_click": "Haz clic para grabar un atajo", "edit_text": "Editar como texto",
 "unsaved": "Tienes cambios sin guardar", "undo": "Deshacer",
 "repl_empty": "Aún no hay reglas de sustitución.", "btn_remove": "Quitar",
 "btn_create": "Crear", "unit_hour": "h",
 "beep_vol_lbl": "Volumen de los pitidos",
 "ov_enter_on": "Pegado automático: sí", "ov_enter_off": "Pegado automático: no",
 "auto_enter_sub": "Se puede desactivar por dictado con un clic en el overlay",
 "tab_projects": "Proyectos", "projects_enable": "Usar proyectos",
 "projects_enable_sub": "Los nuevos dictados también se guardan en el proyecto activo",
 "grp_proj_list": "Proyectos", "proj_new_ph": "Nombre del nuevo proyecto…",
 "proj_none": "Aún no hay proyectos: añade uno arriba.",
 "proj_active": "Activo", "proj_set_active": "Activar",
 "proj_count_suffix": "dictados",
 "proj_remove_note": "Al eliminar un proyecto, su archivo de dictados se conserva en la carpeta 'projects'.",
 "tab_history": "Historial", "hist_recent": "Últimos dictados",
 "proj_entries_title": "Dictados del proyecto",
 "proj_no_entries": "Aún no hay dictados en este proyecto.",
 "proj_header_title": "Instrucción de IA para el proyecto activo",
 "proj_header_sub": "Aparece al principio de la exportación y de la copia",
 "proj_header_ph": "P. ej. Resume estos dictados…",
 "btn_open": "Abrir", "mic_test": "Probar micrófono",
 "n_copied_one": "Copiado al portapapeles.",
 "mute_apps": "Silenciar tu micrófono virtual durante la grabación",
 "mute_apps_sub": "Silencia micros virtuales (Voicemod, Voicemeeter…) que escuchan otras apps: así nadie oye tu dictado. Solo funciona con ese tipo de micro virtual",
 "mute_warn_novirt": "No se encontró ningún micrófono virtual. Windows no puede silenciar un micrófono por aplicación; sin un micro virtual (p. ej. Voicemod o VB-Cable) no hay nada que silenciar. Discord sí funciona - mira la página de Discord.",
 "grp_mic": "Micrófono",
 "mic_auto": "Automático (dispositivo predeterminado)",
 "mic_sub": "¿Usas un micrófono virtual (Voicemod, Voicemeeter…)? Selecciona aquí tu micrófono REAL",
 "mute_warn_auto": "Selecciona primero arriba tu micrófono real: con 'Automático', Dicteer no sabe qué micro proteger y no se silenciará nada.",
 "mute_warn_virtual": "Esto parece un micrófono virtual. Selecciona arriba tu micrófono real; de lo contrario tu dictado se queda en silencio y no se silenciará nada.",
 "mute_ok": "Configurado correctamente: Dicteer protege este micrófono y silencia tus micros virtuales al dictar.",
 "n_cpu_mode": "No se encontró una GPU NVIDIA: Dicteer usa el procesador. Funciona bien pero es más lento; el modelo 'medium' o 'small' es más rápido en CPU.",
},
"fr": {
 "backup_title": "Sauvegarde et export",
 "backup": "Sauvegarder tous les paramètres dans un zip",
 "restore": "Restaurer une sauvegarde",
 "export_dict": "Exporter toutes les dictées dans un fichier (pour ChatGPT / projets)",
 "copy_dict": "Copier toutes les dictées dans le presse-papiers",
 "btn_backup": "Sauvegarder...",
 "btn_restore": "Restaurer...",
 "btn_export": "Exporter...",
 "btn_copy": "Copier",
 "n_backup_ok": "Sauvegarde enregistrée.",
 "n_backup_fail": "Échec de la sauvegarde - voir dicteer.log.",
 "n_restore_ok": "Sauvegarde restaurée.",
 "n_restore_fail": "Échec de la restauration - voir dicteer.log.",
 "n_export_ok": "Dictées exportées.",
 "n_copied": "Toutes les dictées copiées dans le presse-papiers.",
 "n_empty": "Aucune dictée enregistrée pour l'instant.",
 "dict_wrong": "Mot erroné",
 "dict_right": "Remplacer par",
 "btn_add": "Ajouter",
 "dict_files_note": "Enregistré dans vocabulary.txt et replacements.txt à côté du programme - facile à sauvegarder.",
 "tab_dict": "Dictionnaire", "auto_enter": "Appuyer sur Entrée après le collage (envoi auto, pratique pour les chats IA)",
 "dict_words": "Mots et noms à mieux reconnaître (un par ligne)", "dict_repl": "Remplacements (un par ligne :  faux => correct)",
 "mouse_ptt": "Bouton latéral souris = appuyer pour parler", "repaste": "Raccourci : recoller la dernière dictée",
 "dc_setup_title": "Lier Discord (une fois, ~5 min)", "dc_portal": "Ouvrir le Discord Developer Portal",
 "dc_steps": "1. Ouvrez le Discord Developer Portal (bouton ci-dessous) et cliquez sur 'New Application' ; nommez-la p. ex. 'Dicteer'.\n2. Onglet OAuth2 : copiez le Client ID, cliquez sur 'Reset Secret' et copiez le Client Secret.\n3. Sous 'Redirects', ajoutez  http://127.0.0.1  puis enregistrez.\n4. Collez le Client ID et le Secret ci-dessus et cliquez sur Appliquer.\n5. Cliquez sur 'Lier / tester Discord' et approuvez la fenêtre dans Discord : votre micro est coupé 2 secondes en test.",
 "update_available": "Mise à jour disponible", "check_updates": "Rechercher les mises à jour automatiquement",
 "n_update": "Dicteer {tag} est disponible ! Ouvrez les paramètres.",
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
 "dc_link": "Lier / tester Discord", "dc_note": "Configuration unique requise - voir les étapes ci-dessous.",
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
 "grp_controls": "Commandes", "grp_language": "Langue et modèle",
 "grp_during": "Pendant l'enregistrement", "grp_behavior": "Comportement",
 "grp_link": "Connexion",
 "hotkey_lbl": "Raccourci clavier", "hotkey_sub": "Démarre et arrête la dictée",
 "model_lbl": "Modèle", "model_sub": "Rechargé après l'enregistrement",
 "seg_toggle": "Appuyer", "seg_hold": "Maintenir",
 "opt_none": "Non", "opt_auto": "Automatique",
 "press_keys": "Appuyez sur une combinaison de touches…",
 "hk_click": "Cliquez pour enregistrer un raccourci", "edit_text": "Modifier comme texte",
 "unsaved": "Vous avez des modifications non enregistrées", "undo": "Annuler",
 "repl_empty": "Aucune règle de remplacement pour l'instant.", "btn_remove": "Supprimer",
 "btn_create": "Créer", "unit_hour": "h",
 "beep_vol_lbl": "Volume des bips",
 "ov_enter_on": "Collage auto activé", "ov_enter_off": "Collage auto désactivé",
 "auto_enter_sub": "Désactivable par dictée d'un clic dans l'overlay",
 "tab_projects": "Projets", "projects_enable": "Utiliser les projets",
 "projects_enable_sub": "Les nouvelles dictées sont aussi enregistrées dans le projet actif",
 "grp_proj_list": "Projets", "proj_new_ph": "Nom du nouveau projet…",
 "proj_none": "Pas encore de projets - ajoutez-en un ci-dessus.",
 "proj_active": "Actif", "proj_set_active": "Activer",
 "proj_count_suffix": "dictées",
 "proj_remove_note": "La suppression d'un projet conserve son fichier de dictées dans le dossier 'projects'.",
 "tab_history": "Historique", "hist_recent": "Dernières dictées",
 "proj_entries_title": "Dictées du projet",
 "proj_no_entries": "Pas encore de dictées dans ce projet.",
 "proj_header_title": "Instruction IA pour le projet actif",
 "proj_header_sub": "Placée en tête de l'export et de la copie",
 "proj_header_ph": "Par ex. Résume ces dictées…",
 "btn_open": "Ouvrir", "mic_test": "Tester le micro",
 "n_copied_one": "Copié dans le presse-papiers.",
 "mute_apps": "Couper votre micro virtuel pendant l'enregistrement",
 "mute_apps_sub": "Coupe les micros virtuels (Voicemod, Voicemeeter…) écoutés par les autres applications : personne n'entend votre dictée. Ne fonctionne qu'avec une telle configuration de micro virtuel",
 "mute_warn_novirt": "Aucun micro virtuel trouvé. Windows ne peut pas couper un micro par application ; sans micro virtuel (par ex. Voicemod ou VB-Cable), il n'y a rien à couper. Discord fonctionne quand même - voir la page Discord.",
 "grp_mic": "Microphone",
 "mic_auto": "Automatique (périphérique par défaut)",
 "mic_sub": "Vous utilisez un micro virtuel (Voicemod, Voicemeeter…) ? Sélectionnez ici votre VRAI micro",
 "mute_warn_auto": "Choisissez d'abord votre vrai micro ci-dessus - avec « Automatique », Dicteer ne sait pas quel micro protéger et rien ne sera coupé.",
 "mute_warn_virtual": "Ceci ressemble à un micro virtuel. Choisissez votre vrai micro ci-dessus, sinon votre dictée devient muette et rien ne sera coupé.",
 "mute_ok": "Bien configuré : Dicteer protège ce micro et coupe vos micros virtuels pendant la dictée.",
 "n_cpu_mode": "Aucune carte NVIDIA trouvée - Dicteer utilise le processeur. Cela fonctionne mais est plus lent ; le modèle « medium » ou « small » est plus rapide sur CPU.",
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


# ---------------------------------------------------------------- woordenboek

def load_vocabulary():
    try:
        with open(VOCAB_PATH, encoding="utf-8") as f:
            return [r.strip() for r in f if r.strip()]
    except Exception:
        return []


def save_vocabulary(items):
    try:
        with open(VOCAB_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(items) + "\n")
    except Exception:
        log.exception("vocabulary.txt niet opgeslagen")


def load_replacements():
    d = {}
    try:
        with open(REPL_PATH, encoding="utf-8") as f:
            for regel in f:
                if "=>" in regel:
                    a, b = regel.split("=>", 1)
                    if a.strip():
                        d[a.strip()] = b.strip()
    except Exception:
        pass
    return d


def save_replacements(d):
    try:
        with open(REPL_PATH, "w", encoding="utf-8") as f:
            for a, b in d.items():
                f.write(f"{a} => {b}\n")
    except Exception:
        log.exception("replacements.txt niet opgeslagen")


def apply_replacements(text, repl):
    """Pas de vervangregels toe (hoofdletter-ongevoelig)."""
    import re
    for fout, goed in (repl or {}).items():
        if not str(fout).strip():
            continue
        try:
            text = re.sub(re.escape(str(fout)), str(goed), text,
                          flags=re.IGNORECASE)
        except Exception:
            continue
    return text


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


# ---------------------------------------------------------------- projecten

def load_projects_data():
    """projects.json: {"projects": [namen], "headers": {naam: AI-instructie}}.
    Ondersteunt ook het oude formaat (kale lijst met namen)."""
    try:
        with open(PROJECTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):  # oud formaat
            return {"projects": [str(n) for n in data][:200], "headers": {}}
        return {"projects": [str(n) for n in data.get("projects", [])][:200],
                "headers": {str(k): str(v)
                            for k, v in dict(data.get("headers", {})).items()}}
    except Exception:
        return {"projects": [], "headers": {}}


def save_projects_data(data):
    try:
        with open(PROJECTS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        log.exception("projects.json niet opgeslagen")


def load_projects():
    return load_projects_data()["projects"]


def safe_filename(naam):
    import re
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(naam)).strip() or "project"


def project_file(naam):
    return os.path.join(PROJECTS_DIR, safe_filename(naam) + ".txt")


def project_count(naam):
    try:
        with open(project_file(naam), encoding="utf-8") as f:
            return sum(1 for r in f if r.strip())
    except Exception:
        return 0


def append_project_entry(naam, text):
    try:
        os.makedirs(PROJECTS_DIR, exist_ok=True)
        with open(project_file(naam), "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M')}] {text}\n")
    except Exception:
        log.exception("Project-dictaat niet opgeslagen")


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


# ---------------------------------------------------------------- updates

UPDATE_REPO = "Radeaus/dicteer"


def check_for_update():
    """Vraag de nieuwste release op bij GitHub. Geeft dict of None."""
    import urllib.request
    req = urllib.request.Request(
        f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest",
        headers={"User-Agent": "Dicteer",
                 "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    tag = str(data.get("tag_name", ""))
    try:
        latest = int(tag.lstrip("vV").split(".")[0])
        current = int(VERSION.lstrip("vV").split(".")[0])
    except ValueError:
        return None
    if latest > current:
        return {"tag": tag, "url": data.get("html_url", "")}
    return None


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
    """(pid, procesnaam, sessiestatus, ISimpleAudioVolume) voor elke
    opnamesessie op alle actieve microfoons. Status: 0=inactief, 1=actief
    (neemt nu op), 2=verlopen."""
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
                try:
                    state = int(ctl2.GetState())
                except Exception:
                    state = -1
                yield pid, name, state, ctl2.QueryInterface(ISimpleAudioVolume)
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
            for _pid, name, _state, svol in _iter_capture_sessions():
                try:
                    # herstel ALLE hangende sessiedempingen (bijv. na een crash
                    # met 'andere apps dempen' aan): Windows onthoudt deze en
                    # er bestaat geen zichtbare knop voor in de interface
                    if svol.GetMute():
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


class AppMuteWorker:
    """Dempt tijdens de opname VIRTUELE microfoon-apparaten (Voicemod,
    Voicemeeter, VB-Cable, NVIDIA Broadcast...) waar andere apps naar
    luisteren, en herstelt daarna precies wat wij gedempt hebben.

    Waarom apparaten en geen audiosessies: Windows kent geen echte demping
    per app voor opname - het 'sessievolume' van een opnamestroom stuurt in
    de praktijk het hele apparaat aan, dus per-app dempen zet altijd ook je
    eigen microfoon dicht. Apparaat-demping werkt wel betrouwbaar: laat
    Dicteer de ECHTE microfoon gebruiken, dan wordt tijdens het dicteren de
    virtuele mic gedempt waar Discord, games, OBS en Teams naar luisteren.
    De microfoon van Dicteer zelf wordt altijd beschermd.

    Al het COM-werk gebeurt binnen één taak op dezelfde thread en wordt daar
    ook opgeruimd (zie repair_microphone voor het waarom)."""

    # herkenning van virtuele microfoons op naamdeel
    VIRTUEEL_DELEN = (
        "voicemod", "voicemeeter", "vb-audio", "vb-cable", "cable",
        "virtual", "virtueel", "sonar", "steelseries", "broadcast",
        "nahimic", "goxlr", "wave link", "wavelink", "krisp",
    )

    def __init__(self, app):
        self.app = app
        self._desired = None
        self._cv = threading.Condition()
        self._muted_ids = set()  # endpoint-ids die WIJ gedempt hebben
        threading.Thread(target=self._run, daemon=True, name="app-mute").start()

    def request(self, mute):
        with self._cv:
            self._desired = bool(mute)
            self._cv.notify()

    def _run(self):
        while True:
            with self._cv:
                while self._desired is None:
                    self._cv.wait()
                mute = self._desired
                self._desired = None
            try:
                self._apply(mute)
            except Exception:
                log.exception("Demping andere apps mislukt")

    def _apply(self, mute):
        if not pycaw_available():
            return
        if not mute and not self._muted_ids:
            return  # niets te herstellen
        import gc
        import comtypes
        from ctypes import POINTER, cast
        from pycaw.pycaw import IAudioEndpointVolume, IMMDeviceEnumerator
        try:
            from pycaw.constants import CLSID_MMDeviceEnumerator
        except ImportError:
            from pycaw.pycaw import CLSID_MMDeviceEnumerator
        comtypes.CoInitialize()
        try:
            enumerator = collection = None
            try:
                enumerator = comtypes.CoCreateInstance(
                    CLSID_MMDeviceEnumerator, IMMDeviceEnumerator,
                    comtypes.CLSCTX_INPROC_SERVER)
                namen = self._endpoint_names()
                beschermd = self._protected_ids(enumerator, namen) if mute else set()
                if mute and beschermd is None:
                    log.warning("Virtuele mics NIET gedempt: de microfoon van "
                                "Dicteer is niet met zekerheid herkend.")
                    return
                collection = enumerator.EnumAudioEndpoints(1, 1)  # eCapture, ACTIVE
                n = 0
                nieuw = set()
                for i in range(collection.GetCount()):
                    dev = itf = vol = None
                    try:
                        dev = collection.Item(i)
                        did = str(dev.GetId())
                        naam = namen.get(did, "")
                        if mute:
                            if did in beschermd:
                                continue
                            if not any(deel in naam.lower()
                                       for deel in self.VIRTUEEL_DELEN):
                                continue  # alleen virtuele mics dempen
                        elif did not in self._muted_ids:
                            continue
                        itf = dev.Activate(IAudioEndpointVolume._iid_,
                                           comtypes.CLSCTX_ALL, None)
                        vol = cast(itf, POINTER(IAudioEndpointVolume))
                        if mute:
                            if not vol.GetMute():
                                vol.SetMute(1, None)
                                nieuw.add(did)
                                n += 1
                                log.info("Virtuele microfoon gedempt: %s", naam)
                        else:
                            if vol.GetMute():
                                vol.SetMute(0, None)
                                n += 1
                                log.info("Microfoon hersteld: %s", naam)
                    except Exception:
                        pass
                    finally:
                        dev = itf = vol = None
                if mute:
                    self._muted_ids = nieuw
                    if not n:
                        log.info("Geen virtuele microfoon gevonden om te "
                                 "dempen (of Dicteer gebruikt hem zelf - kies "
                                 "dan je echte microfoon in de instellingen).")
                else:
                    self._muted_ids = set()
            finally:
                enumerator = collection = None
                gc.collect()  # COM-objecten op deze thread opruimen
        finally:
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass

    @staticmethod
    def _endpoint_names():
        """{endpoint-id: weergavenaam} voor alle audio-apparaten."""
        namen = {}
        try:
            from pycaw.pycaw import AudioUtilities
            for d in AudioUtilities.GetAllDevices():
                try:
                    namen[str(d.id)] = str(getattr(d, "FriendlyName", "") or "")
                except Exception:
                    continue
        except Exception:
            log.exception("Apparaatnamen opvragen mislukt")
        return namen

    def _protected_ids(self, enumerator, namen):
        """Endpoint-ids die nooit gedempt mogen worden (de mic van Dicteer).
        None betekent: niet met zekerheid vast te stellen -> demp dan niets."""
        doel = str(self.app.cfg.get("input_device", "auto")).strip()
        ids = set()
        if doel in ("", "auto"):
            for rol in (0, 2):  # eConsole en eCommunications
                try:
                    ids.add(str(enumerator.GetDefaultAudioEndpoint(1, rol).GetId()))
                except Exception:
                    pass
            return ids or None
        frag = doel.lower()[:25]  # sounddevice kapt lange namen af
        for did, naam in namen.items():
            if frag and frag in naam.lower():
                ids.add(did)
        return ids or None


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

class WebApi:
    """Brug tussen het HTML-instellingenvenster (JavaScript) en de app.
    Alle publieke methodes zijn vanuit JS aanroepbaar via window.pywebview.api."""

    def __init__(self, app, ui):
        self._app = app
        self._ui = ui

    def _window(self):
        return self._ui._win

    # -------- state naar de UI

    def state(self):
        app = self._app
        cfg = app.cfg
        lang = cfg.get("ui_language", "en")
        mics = list_input_devices()
        cur_mic = cfg.get("input_device", "auto")
        if cur_mic not in mics:
            mics.append(cur_mic)
        safe_cfg = {k: v for k, v in cfg.items()
                    if k not in ("vocabulary", "replacements")}
        return {
            "version": VERSION,
            "cfg": safe_cfg,
            "vocab": list(app.vocab),
            "repl": dict(app.repl),
            "stats": load_stats(),
            "mics": mics,
            "languages": [[c, n] for c, n in LANGUAGES],
            "ui_languages": [[c, n] for c, n in UI_LANGUAGES],
            "models": ["large-v3-turbo", "large-v3", "medium", "small"],
            "devices": ["auto", "cuda", "cpu"],
            "mouse_buttons": ["none", "x", "x2"],
            "autostart": autostart_enabled(),
            "update": app.update_info,
            "lang": lang,
            "projects": self._projects_state()["projects"],
            "history": list(app.history),
            "tr": {**TR["en"], **TR.get(lang, {})},
        }

    # -------- opslaan

    def save(self, data):
        app = self._app
        cfg = app.cfg
        data = data or {}
        cfg["hotkey"] = str(data.get("hotkey") or "ctrl+shift+s").strip()
        cfg["mode"] = data.get("mode") if data.get("mode") in ("toggle", "hold") else "toggle"
        cfg["language"] = str(data.get("language") or "auto")
        cfg["model"] = str(data.get("model") or cfg.get("model", "large-v3-turbo"))
        cfg["device"] = str(data.get("device") or "auto")
        cfg["ui_language"] = str(data.get("ui_language") or "en")
        try:
            cfg["beep_volume"] = round(float(data.get("beep_volume", 0.15)), 2)
        except (TypeError, ValueError):
            pass
        cfg["input_device"] = str(data.get("input_device") or "auto")
        cfg["mouse_button"] = str(data.get("mouse_button") or "none")
        cfg["repaste_hotkey"] = str(data.get("repaste_hotkey") or "").strip()
        for key in ("beep", "overlay", "live_preview", "pause_media", "history",
                    "restore_clipboard", "show_settings_on_start", "check_updates",
                    "auto_enter", "discord_mute", "discord_deafen",
                    "projects_enabled", "mute_other_apps"):
            if key in data:
                cfg[key] = bool(data[key])
        cfg["discord_client_id"] = str(data.get("discord_client_id") or "").strip()
        cfg["discord_client_secret"] = str(data.get("discord_client_secret") or "").strip()
        app.vocab = [str(r).strip() for r in (data.get("vocab") or [])
                     if str(r).strip()]
        save_vocabulary(app.vocab)
        save_config(cfg)
        global UI_LANG
        UI_LANG = cfg["ui_language"]
        try:
            set_autostart(bool(data.get("_autostart")))
        except Exception:
            log.exception("Autostart wijzigen mislukt")
        threading.Thread(target=app.reload_config, daemon=True).start()
        return self.state()

    # -------- woordenboek

    def repl_add(self, wrong, right):
        wrong = str(wrong or "").strip()
        right = str(right or "").strip()
        if wrong:
            self._app.repl[wrong] = right
            save_replacements(self._app.repl)
        return dict(self._app.repl)

    def repl_remove(self, wrong):
        self._app.repl.pop(str(wrong), None)
        save_replacements(self._app.repl)
        return dict(self._app.repl)

    def stats(self):
        return load_stats()

    # -------- projecten

    def _projects_state(self):
        data = load_projects_data()
        return {"projects": [{"name": n, "count": project_count(n),
                              "header": data["headers"].get(n, "")}
                             for n in data["projects"]],
                "current": self._app.cfg.get("current_project", "")}

    def project_add(self, name):
        name = str(name or "").strip()[:60]
        if name:
            data = load_projects_data()
            if name not in data["projects"]:
                data["projects"].append(name)
                save_projects_data(data)
            if not self._app.cfg.get("current_project"):
                self._app.cfg["current_project"] = name
                save_config(self._app.cfg)
        return self._projects_state()

    def project_remove(self, name):
        data = load_projects_data()
        data["projects"] = [n for n in data["projects"] if n != name]
        data["headers"].pop(str(name), None)
        save_projects_data(data)
        if self._app.cfg.get("current_project") == name:
            self._app.cfg["current_project"] = ""
            save_config(self._app.cfg)
        return self._projects_state()

    def project_set_header(self, name, text):
        """AI-instructie die bovenaan de export/kopie van dit project komt."""
        data = load_projects_data()
        if name in data["projects"]:
            data["headers"][str(name)] = str(text or "").strip()
            save_projects_data(data)
        return True

    def project_entries(self, name):
        try:
            with open(project_file(name), encoding="utf-8") as f:
                return [r.rstrip("\n") for r in f if r.strip()]
        except Exception:
            return []

    def project_entry_remove(self, name, index):
        regels = self.project_entries(name)
        try:
            i = int(index)
            if 0 <= i < len(regels):
                regels.pop(i)
                with open(project_file(name), "w", encoding="utf-8") as f:
                    f.write("\n".join(regels) + ("\n" if regels else ""))
        except Exception:
            log.exception("Projectregel verwijderen mislukt")
        return self.project_entries(name)

    def _project_content(self, name):
        with open(project_file(name), encoding="utf-8") as f:
            inhoud = f.read()
        kop = load_projects_data()["headers"].get(str(name), "").strip()
        top = f"# Dicteer - {name}\n\n"
        if kop:
            top += kop + "\n\n---\n\n"
        return top + inhoud

    def project_select(self, name):
        if name in load_projects():
            self._app.cfg["current_project"] = name
            save_config(self._app.cfg)
        return self._projects_state()

    def project_export(self, name):
        pf = project_file(name)
        if not os.path.exists(pf):
            self._app._notify(tr("n_empty"))
            return False
        pad = self._dialog(
            True, f"dicteer-{safe_filename(name)}-{time.strftime('%Y%m%d')}.md",
            ("Markdown (*.md)", "Text (*.txt)"))
        if not pad:
            return False
        try:
            with open(pad, "w", encoding="utf-8") as f:
                f.write(self._project_content(name))
            self._app._notify(tr("n_export_ok"))
            return True
        except Exception:
            log.exception("Project-export mislukt")
            return False

    def project_copy(self, name):
        import pyperclip
        try:
            pyperclip.copy(self._project_content(name))
            self._app._notify(tr("n_copied"))
            return True
        except Exception:
            self._app._notify(tr("n_empty"))
            return False

    def history(self):
        return list(self._app.history)

    def copy_text(self, text):
        import pyperclip
        try:
            pyperclip.copy(str(text or ""))
            return True
        except Exception:
            return False

    # -------- microfoontest (live meter in de instellingen)

    def mic_test_start(self, device=None):
        if self._app.state == "opname":
            return False
        self.mic_test_stop()
        try:
            import sounddevice as sd
            naam = str(device or self._app.cfg.get("input_device", "auto"))
            dev = None
            if naam and naam != "auto":
                try:
                    for i, d in enumerate(sd.query_devices()):
                        if d.get("max_input_channels", 0) > 0 and d["name"] == naam:
                            dev = i
                            break
                except Exception:
                    dev = None
            self._mic_level = 0.0

            def _cb(indata, frames, t, status):
                try:
                    self._mic_level = float((indata ** 2).mean()) ** 0.5
                except Exception:
                    pass

            self._mic_stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                device=dev, callback=_cb)
            self._mic_stream.start()
            timer = threading.Timer(30.0, self.mic_test_stop)  # vangnet
            timer.daemon = True
            timer.start()
            return True
        except Exception:
            log.exception("Microfoontest starten mislukt")
            self._mic_stream = None
            return False

    def mic_test_stop(self):
        s = getattr(self, "_mic_stream", None)
        self._mic_stream = None
        if s is not None:
            try:
                s.stop()
                s.close()
            except Exception:
                pass
        return True

    def mic_level(self):
        if getattr(self, "_mic_stream", None) is None:
            return -1.0
        return min(1.0, float(getattr(self, "_mic_level", 0.0)) * 18)

    # -------- sneltoetsen pauzeren tijdens vastleggen

    def hotkeys_suspend(self):
        self._app.suspend_hotkeys()
        return True

    def hotkeys_resume(self):
        self._app.resume_hotkeys()
        return True

    def open_config(self):
        try:
            os.startfile(CONFIG_PATH)
        except Exception:
            pass
        return True

    def open_log(self):
        try:
            os.startfile(LOG_PATH)
        except Exception:
            pass
        return True

    # -------- acties

    def discord_link(self):
        self._app._discord_link()
        return True

    def make_shortcut(self):
        self._app.make_shortcut()
        return True

    def copy_dictations(self):
        self._app.copy_dictations()
        return True

    def _dialog(self, save, filename="", file_types=()):
        import webview
        win = self._window()
        if win is None:
            return None
        fd = getattr(webview, "FileDialog", None)
        if fd is not None:
            mode = fd.SAVE if save else fd.OPEN
        else:  # oudere pywebview-versies
            mode = webview.SAVE_DIALOG if save else webview.OPEN_DIALOG
        try:
            res = win.create_file_dialog(mode, save_filename=filename,
                                         file_types=tuple(file_types))
        except Exception:
            log.exception("Bestandsdialoog mislukt")
            return None
        if not res:
            return None
        if isinstance(res, (list, tuple)):
            return res[0] if res else None
        return res

    def backup(self):
        pad = self._dialog(True, f"dicteer-backup-{time.strftime('%Y%m%d')}.zip",
                           ("Zip (*.zip)",))
        if pad:
            self._app.backup_settings(pad)
        return bool(pad)

    def restore(self):
        pad = self._dialog(False, file_types=("Zip (*.zip)",))
        if pad:
            self._app.restore_settings(pad)
        return bool(pad)

    def export(self):
        pad = self._dialog(True, f"dicteer-dictations-{time.strftime('%Y%m%d')}.md",
                           ("Markdown (*.md)", "Text (*.txt)"))
        if pad:
            self._app.export_dictations(pad)
        return bool(pad)

    def open_url(self, url):
        import webbrowser
        if str(url).startswith(("http://", "https://")):
            webbrowser.open(str(url))
        return True

    def close(self):
        win = self._window()
        if win is not None:
            try:
                win.hide()
            except Exception:
                pass
        return True


class Overlay:
    """UI-huishouding.
    - Instellingen: web-based venster (pywebview) op de HOOFDthread. Het venster
      wordt bij sluiten alleen verborgen, zodat de GUI-lus blijft draaien.
    - Opname-overlay: lichtgewicht tkinter-venster in een EIGEN thread; alle
      tk-aanroepen blijven binnen die thread (tkinter is niet thread-safe)."""

    OV_W, OV_H = 460, 92
    C_BG, C_BORDER = "#121412", "#2d322d"
    C_TEXT, C_MUTED = "#e9ebe7", "#9ba49c"
    C_GREEN, C_RED, C_AMBER = "#58b47e", "#e0605a", "#d9a03c"
    TRANS = "#010203"  # 'magische' kleur -> transparante hoeken op Windows

    def __init__(self, app):
        self.app = app
        self._quit = False
        self._win = None          # pywebview-venster (instellingen)
        self._ui_ready = False
        self._webview_failed = False
        self._visible = False
        self._phase = 0.0
        self._smooth = 0.0
        self._root = None
        self._ov = None
        self._canvas = None

    # -------- instellingen openen (mag vanaf elke thread)

    def open_settings(self):
        if self._webview_failed:
            self.app._notify("Missing package. Run: venv\\Scripts\\python.exe "
                             "-m pip install pywebview")
            return
        win = self._win
        if win is None:
            return  # venster verschijnt vanzelf zodra de GUI-lus start
        def _t():
            try:
                if self._ui_ready:
                    try:
                        win.evaluate_js("window.__refresh && window.__refresh()")
                    except Exception:
                        pass
                win.show()
                try:
                    win.restore()
                except Exception:
                    pass
            except Exception:
                log.exception("Instellingen tonen mislukt")
        threading.Thread(target=_t, daemon=True).start()

    def request_quit(self):
        self._quit = True
        win, self._win = self._win, None
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass

    # -------- hoofdlus

    def run_mainloop(self):
        try:
            import webview
        except Exception:
            webview = None
        if webview is None:
            self._webview_failed = True
            log.error("pywebview ontbreekt; instellingenvenster niet beschikbaar. "
                      "Installeer met: venv\\Scripts\\python.exe -m pip install pywebview")
            self.app._notify("Missing package. Run: venv\\Scripts\\python.exe "
                             "-m pip install pywebview")
            self._tk_overlay_loop()  # overlay blijft werken (blokkeert)
            return
        threading.Thread(target=self._tk_overlay_loop, daemon=True,
                         name="overlay-ui").start()
        self._run_webview(webview)

    def _run_webview(self, webview):
        api = WebApi(self.app, self)
        show = bool(self.app.cfg.get("show_settings_on_start", True))
        html_path = os.path.join(APP_DIR, "ui", "settings.html")
        try:
            win = webview.create_window(
                "Dicteer", url=html_path, js_api=api,
                width=940, height=680, min_size=(820, 560),
                hidden=not show, background_color="#0E0F0E")
            self._win = win
            win.events.loaded += self._on_loaded
            win.events.before_show += self._on_before_show
            win.events.closing += self._on_closing
            webview.start(http_server=True)
        except Exception:
            log.exception("Webview-hoofdlus gestopt")
        finally:
            self._win = None

    def _on_loaded(self, *args):
        self._ui_ready = True

    def _on_before_show(self, *args):
        """Donkere titelbalk (Windows 10 20H1+) en eigen venstericoon."""
        try:
            import ctypes
            hwnd = self._win.native.Handle.ToInt32()
            value = ctypes.c_int(1)
            for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(value),
                        ctypes.sizeof(value)) == 0:
                    break
        except Exception:
            pass
        try:
            import System.Drawing  # via pythonnet (geladen door pywebview)
            ico = os.path.join(APP_DIR, "dicteer.ico")
            if os.path.exists(ico):
                self._win.native.Icon = System.Drawing.Icon(ico)
        except Exception:
            pass

    def _on_closing(self, *args):
        """Kruisje = verbergen, niet sluiten: de GUI-lus moet blijven draaien."""
        if self._quit:
            return None
        win = self._win
        if win is not None:
            threading.Thread(target=lambda: win.hide(), daemon=True).start()
        return False

    # -------- opname-overlay (tkinter; alles binnen deze thread)

    def _tk_overlay_loop(self):
        import tkinter as tk
        try:
            root = tk.Tk()
            self._root = root
            root.withdraw()
            ov = tk.Toplevel(root)
            self._ov = ov
            ov.withdraw()
            ov.overrideredirect(True)            # geen titelbalk
            ov.attributes("-topmost", True)      # altijd bovenop
            try:
                ov.attributes("-transparentcolor", self.TRANS)
            except Exception:
                pass
            w, h = self.OV_W, self.OV_H
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            ov.geometry(f"{w}x{h}+{(sw - w) // 2}+{sh - h - 90}")
            self._canvas = tk.Canvas(ov, width=w, height=h, bg=self.TRANS,
                                     highlightthickness=0)
            self._canvas.pack()
            self._no_activate(ov)  # klik mag geen focus stelen (anders faalt plakken)
            self._canvas.tag_bind("entertoggle", "<Button-1>", self._toggle_enter)
            self._canvas.tag_bind("entertoggle", "<Enter>",
                                  lambda e: ov.configure(cursor="hand2"))
            self._canvas.tag_bind("entertoggle", "<Leave>",
                                  lambda e: ov.configure(cursor=""))
            self._canvas.tag_bind("projtoggle", "<Button-1>",
                                  lambda e: self.app.next_project())
            self._canvas.tag_bind("projtoggle", "<Enter>",
                                  lambda e: ov.configure(cursor="hand2"))
            self._canvas.tag_bind("projtoggle", "<Leave>",
                                  lambda e: ov.configure(cursor=""))
            self._tick()
            root.mainloop()
        except Exception:
            log.exception("Overlay-thread gestopt")

    def _show(self):
        if not self._visible:
            self._ov.deiconify()
            self._ov.attributes("-topmost", True)
            self._visible = True

    def _hide(self):
        if self._visible:
            self._ov.withdraw()
            self._visible = False

    @staticmethod
    def _round_rect(c, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return c.create_polygon(pts, smooth=True, **kw)

    def _pill(self, c, height):
        self._round_rect(c, 1, 1, self.OV_W - 1, height - 1, 20,
                         fill=self.C_BG, outline=self.C_BORDER)

    @staticmethod
    def _no_activate(win):
        """WS_EX_NOACTIVATE: overlay reageert op klikken zonder de focus af te
        pakken van het venster waarin gedicteerd wordt."""
        if os.name != "nt":
            return
        try:
            import ctypes
            win.update_idletasks()
            GWL_EXSTYLE, WS_EX_NOACTIVATE = -20, 0x08000000
            u = ctypes.windll.user32
            for hwnd in {win.winfo_id(), u.GetParent(win.winfo_id())}:
                if hwnd:
                    stijl = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    u.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                     stijl | WS_EX_NOACTIVATE)
        except Exception:
            log.exception("WS_EX_NOACTIVATE instellen mislukt")

    def _toggle_enter(self, event=None):
        """Klik op de Enter-chip: auto-verzenden alleen voor dit dictaat aan/uit."""
        self.app.enter_once_off = not self.app.enter_once_off

    def _draw_enter_chip(self, c):
        aan = not self.app.enter_once_off
        kleur = self.C_GREEN if aan else self.C_MUTED
        label = tr("ov_enter_on") if aan else tr("ov_enter_off")
        self._round_rect(c, 288, 16, 446, 40, 12, fill=self.C_BG,
                         outline=kleur, tags="entertoggle")
        c.create_text(367, 28, text=label, fill=kleur,
                      font=("Segoe UI", 9, "bold"), tags="entertoggle")

    def _project_naam(self):
        """Naam van het actieve project voor in de overlay, of None."""
        if not self.app.cfg.get("projects_enabled", False):
            return None
        naam = str(self.app.cfg.get("current_project", "")).strip()
        if not naam:
            return None
        return (naam[:17] + "…") if len(naam) > 18 else naam

    def _tick(self):
        if self._quit:
            try:
                self._root.quit()
                self._root.destroy()
            except Exception:
                pass
            return
        try:
            state = self.app.state
            c = self._canvas
            cy = 28
            if state == "opname" and self.app.cfg.get("overlay", True):
                self._show()
                c.delete("all")
                self._phase += 0.35
                lvl = getattr(self.app.recorder, "level", 0.0)
                self._smooth = 0.7 * self._smooth + 0.3 * lvl
                pv = getattr(self.app, "preview_text", "")
                self._pill(c, 84 if pv else 56)
                # zacht pulserende opname-stip
                pnaam = self._project_naam()
                ly = 20 if pnaam else cy
                r = 5.5 + 1.5 * math.sin(self._phase * 0.6)
                c.create_oval(26 - r, ly - r, 26 + r, ly + r,
                              fill=self.C_RED, outline="")
                c.create_text(42, ly, anchor="w", text=tr("recording"),
                              fill=self.C_TEXT, font=("Segoe UI", 11, "bold"))
                if pnaam:
                    c.create_rectangle(40, 29, 170, 45, fill=self.C_BG,
                                       outline="", tags="projtoggle")
                    c.create_text(42, 37, anchor="w", text=pnaam + "  ›",
                                  fill=self.C_MUTED, font=("Segoe UI", 8),
                                  tags="projtoggle")
                # spraak-capsules, gespiegeld rond de middellijn
                chip = bool(self.app.cfg.get("auto_enter", False))
                amp = min(1.0, self._smooth * 18)
                n, x0, stap = (11 if chip else 26), 172, 10
                for i in range(n):
                    f = 0.3 + 0.7 * abs(math.sin(self._phase + i * 0.85))
                    hh = 2.0 + 13.0 * amp * f
                    x = x0 + i * stap
                    c.create_line(x, cy - hh, x, cy + hh, fill=self.C_GREEN,
                                  width=4, capstyle="round")
                if chip:
                    self._draw_enter_chip(c)
                if pv:
                    if len(pv) > 64:
                        pv = "…" + pv[-64:]
                    c.create_text(self.OV_W / 2, 68, text=pv, fill=self.C_MUTED,
                                  font=("Segoe UI", 9), width=self.OV_W - 48)
            elif state == "verwerken" and self.app.cfg.get("overlay", True):
                self._show()
                c.delete("all")
                self._phase += 0.25
                self._pill(c, 56)
                pnaam = self._project_naam()
                ly = 20 if pnaam else cy
                r = 5.5 + 1.5 * math.sin(self._phase * 1.2)
                c.create_oval(26 - r, ly - r, 26 + r, ly + r,
                              fill=self.C_AMBER, outline="")
                dots = "." * (1 + int(self._phase) % 3)
                c.create_text(42, ly, anchor="w",
                              text=f"{tr('transcribing')}{dots}",
                              fill=self.C_TEXT, font=("Segoe UI", 11, "bold"))
                if pnaam:
                    c.create_rectangle(40, 29, 170, 45, fill=self.C_BG,
                                       outline="", tags="projtoggle")
                    c.create_text(42, 37, anchor="w", text=pnaam + "  ›",
                                  fill=self.C_MUTED, font=("Segoe UI", 8),
                                  tags="projtoggle")
                if self.app.cfg.get("auto_enter", False):
                    self._draw_enter_chip(c)  # kan tijdens transcriberen nog uit
            else:
                self._hide()
        except Exception:
            pass
        self._root.after(50, self._tick)


# ---------------------------------------------------------------- plakken

def paste_text(text, restore_clipboard=True, press_enter=False):
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
    if press_enter:
        time.sleep(0.15)
        keyboard.send("enter")

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
        self._hotkey_handles = []
        self._mouse_handles = []
        self.last_text = ""
        self._discord_worker = DiscordMuteWorker(self)
        self._app_mute = AppMuteWorker(self)
        self._media = MediaController(self)
        self.preview_text = ""
        self.enter_once_off = False  # auto-enter alleen voor dit dictaat uit
        self.stats = load_stats()
        self.update_info = None
        self.vocab = load_vocabulary()
        self.repl = load_replacements()
        # migratie: woordenboek uit config.json (v27) naar losse bestanden
        if not self.vocab and self.cfg.get("vocabulary"):
            self.vocab = [str(w) for w in self.cfg["vocabulary"]]
            save_vocabulary(self.vocab)
        if not self.repl and self.cfg.get("replacements"):
            self.repl = dict(self.cfg["replacements"])
            save_replacements(self.repl)

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
            geladen = None
            for dev, ctype in attempts:
                try:
                    log.info("Model %s laden op %s (%s)...", self.cfg["model"], dev, ctype)
                    self.model = WhisperModel(self.cfg["model"], device=dev, compute_type=ctype)
                    log.info("Model geladen op %s.", dev)
                    geladen = dev
                    break
                except Exception as e:
                    log.warning("Laden op %s mislukt: %s", dev, e)
                    last_err = e

            if self.model is None:
                raise last_err or RuntimeError("model laden mislukt")

            self.set_state("klaar")
            self._beep(880, 100)
            if geladen == "cpu" and device == "auto":
                # geen NVIDIA-GPU (AMD/Intel of geen kaart): eerlijk melden
                self._notify(tr("n_cpu_mode"))
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
            self.enter_once_off = False
            self.recorder.start(self.cfg.get("input_device", "auto"))
            self.set_state("opname")
            self._beep(1000, 120)
            self._discord_mute(True)
            self._app_mute_request(True)
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
        self._app_mute_request(False)
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
                    initial_prompt=self._vocab_prompt(),
                )
                text = " ".join(s.text.strip() for s in segments).strip()
                text = apply_replacements(text, self.repl)
                if text:
                    self.last_text = text
                log.info("Transcriptie (%s): %r", getattr(info, "language", "?"), text)
                if text:
                    self._add_history(text)
                    self._add_project_entry(text)
                    self.stats["dictations"] += 1
                    self.stats["words"] += len(text.split())
                    self.stats["seconds"] += len(audio) / SAMPLE_RATE
                    save_stats(self.stats)
                    paste_text(text, self.cfg.get("restore_clipboard", True),
                               bool(self.cfg.get("auto_enter", False))
                               and not self.enter_once_off)
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

    def _register_keyboard(self):
        import keyboard
        self._hotkey_handles = [keyboard.add_hotkey(
            self.cfg["hotkey"], self.on_hotkey,
            suppress=bool(self.cfg.get("suppress_hotkey", True)),
        )]
        self._hotkey_handles.append(
            keyboard.add_hotkey("esc", self.on_escape, suppress=False))
        rp = str(self.cfg.get("repaste_hotkey", "")).strip()
        if rp:
            try:
                self._hotkey_handles.append(
                    keyboard.add_hotkey(rp, self.on_repaste, suppress=True))
            except Exception:
                log.exception("Repaste-sneltoets ongeldig: %s", rp)

    def suspend_hotkeys(self):
        """Pauzeer de globale sneltoetsen (tijdens het vastleggen van een
        nieuwe combinatie in de instellingen). Vangnet: na 25 s automatisch
        weer actief, ook als de UI vergeet te hervatten."""
        import keyboard
        for h in self._hotkey_handles:
            try:
                keyboard.remove_hotkey(h)
            except Exception:
                pass
        self._hotkey_handles = []
        timer = threading.Timer(25.0, self.resume_hotkeys)
        timer.daemon = True
        timer.start()

    def resume_hotkeys(self):
        if self._hotkey_handles:
            return  # al actief
        try:
            self._register_keyboard()
        except Exception:
            log.exception("Sneltoetsen hervatten mislukt")

    def register_hotkey(self):
        self._register_keyboard()
        self._mouse_handles = []
        btn = self.cfg.get("mouse_button", "none")
        if btn in ("x", "x2"):
            try:
                import mouse
                self._mouse_handles.append(mouse.on_button(
                    self._mouse_down, buttons=(btn,), types=("down",)))
                self._mouse_handles.append(mouse.on_button(
                    self._mouse_up, buttons=(btn,), types=("up",)))
                log.info("Muisknop-PTT actief: %s", btn)
            except Exception:
                log.exception("Muisknop-PTT registreren mislukt")
        log.info("Sneltoets actief: %s (modus: %s)", self.cfg["hotkey"], self.cfg["mode"])

    def reload_config(self, icon=None, item=None):
        """Herlaad config.json zonder herstart. Nieuwe sneltoets werkt direct;
        een ander model wordt op de achtergrond opnieuw geladen."""
        import keyboard
        old = self.cfg
        self.cfg = load_config()
        for h in self._hotkey_handles:
            try:
                keyboard.remove_hotkey(h)
            except Exception:
                pass
        self._hotkey_handles = []
        try:
            import mouse
            for h in self._mouse_handles:
                try:
                    mouse.unhook(h)
                except Exception:
                    pass
        except Exception:
            pass
        self._mouse_handles = []
        self.register_hotkey()
        self.vocab = load_vocabulary()
        self.repl = load_replacements()
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
        try:
            with open(DICTATIONS_PATH, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M')}] {text}\n")
        except Exception:
            pass
        self.history.insert(0, {"t": time.strftime("%H:%M"), "text": text})
        self.history = self.history[:10]
        save_history(self.history)
        if self.icon is not None:
            try:
                self.icon.update_menu()
            except Exception:
                pass

    def _add_project_entry(self, text):
        """Bewaar het dictaat ook onder het actieve project (indien aan)."""
        if not self.cfg.get("projects_enabled", False):
            return
        naam = str(self.cfg.get("current_project", "")).strip()
        if naam:
            append_project_entry(naam, text)

    def next_project(self, *args):
        """Wissel (klik in de overlay) naar het volgende project in de lijst."""
        namen = load_projects()
        if not namen:
            return
        huidig = str(self.cfg.get("current_project", ""))
        try:
            i = (namen.index(huidig) + 1) % len(namen)
        except ValueError:
            i = 0
        self.cfg["current_project"] = namen[i]
        save_config(self.cfg)

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

    def _vocab_prompt(self):
        """Whisper-hint met eigen woorden/namen voor betere herkenning."""
        vocab = [str(w).strip() for w in self.vocab if str(w).strip()]
        if not vocab:
            return None
        return "Glossary: " + ", ".join(vocab)

    def _mouse_down(self):
        if not self.recorder.recording:
            self._mouse_ptt = True
            self.start_recording()

    def _mouse_up(self):
        if getattr(self, "_mouse_ptt", False) and self.recorder.recording:
            self._mouse_ptt = False
            self.stop_and_transcribe()

    def on_repaste(self):
        """Plak het laatste dictaat opnieuw."""
        text = self.last_text or (self.history[0].get("text", "")
                                  if self.history else "")
        if text:
            threading.Thread(
                target=paste_text, args=(text,),
                kwargs={"restore_clipboard": self.cfg.get("restore_clipboard", True),
                        "press_enter": bool(self.cfg.get("auto_enter", False))},
                daemon=True).start()

    def backup_settings(self, pad):
        import zipfile
        if not pad:
            return
        try:
            with zipfile.ZipFile(pad, "w", zipfile.ZIP_DEFLATED) as z:
                for f in (CONFIG_PATH, VOCAB_PATH, REPL_PATH, HISTORY_PATH,
                          STATS_PATH, DICTATIONS_PATH, DISCORD_TOKEN_PATH,
                          PROJECTS_PATH):
                    if os.path.exists(f):
                        z.write(f, os.path.basename(f))
                if os.path.isdir(PROJECTS_DIR):
                    for naam in os.listdir(PROJECTS_DIR):
                        p = os.path.join(PROJECTS_DIR, naam)
                        if os.path.isfile(p):
                            z.write(p, "projects/" + naam)
            self._notify(tr("n_backup_ok"))
        except Exception:
            log.exception("Backup mislukt")
            self._notify(tr("n_backup_fail"))

    def restore_settings(self, pad):
        import zipfile
        if not pad:
            return
        try:
            toegestaan = {os.path.basename(p) for p in (
                CONFIG_PATH, VOCAB_PATH, REPL_PATH, HISTORY_PATH,
                STATS_PATH, DICTATIONS_PATH, DISCORD_TOKEN_PATH,
                PROJECTS_PATH)}
            with zipfile.ZipFile(pad) as z:
                for naam in z.namelist():
                    basis = os.path.basename(naam)
                    if naam.replace("\\", "/").startswith("projects/") and basis:
                        os.makedirs(PROJECTS_DIR, exist_ok=True)
                        with open(os.path.join(PROJECTS_DIR, basis), "wb") as f:
                            f.write(z.read(naam))
                    elif basis in toegestaan:
                        z.extract(naam, APP_DIR)
            self.history = load_history()
            self.stats = load_stats()
            threading.Thread(target=self.reload_config, daemon=True).start()
            self._notify(tr("n_restore_ok"))
        except Exception:
            log.exception("Backup terugzetten mislukt")
            self._notify(tr("n_restore_fail"))

    def export_dictations(self, pad):
        if not os.path.exists(DICTATIONS_PATH):
            self._notify(tr("n_empty"))
            return
        if not pad:
            return
        try:
            with open(DICTATIONS_PATH, encoding="utf-8") as f:
                inhoud = f.read()
            with open(pad, "w", encoding="utf-8") as f:
                f.write("# Dicteer - dictations\n\n" + inhoud)
            self._notify(tr("n_export_ok"))
        except Exception:
            log.exception("Export mislukt")

    def copy_dictations(self):
        import pyperclip
        try:
            with open(DICTATIONS_PATH, encoding="utf-8") as f:
                pyperclip.copy(f.read())
            self._notify(tr("n_copied"))
        except Exception:
            self._notify(tr("n_empty"))

    def _update_loop(self):
        """Controleer bij de start en daarna dagelijks op nieuwe releases."""
        time.sleep(10)
        gemeld = None
        while True:
            if self.cfg.get("check_updates", True):
                try:
                    info = check_for_update()
                    if info:
                        self.update_info = info
                        if gemeld != info["tag"]:
                            gemeld = info["tag"]
                            self._notify(tr("n_update").format(tag=info["tag"]))
                except Exception:
                    log.info("Update-check mislukt (geen internet?)")
            time.sleep(24 * 3600)

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

    def _app_mute_request(self, mute):
        """Demp andere apps (indien aan). Herstellen gebeurt altijd, ook als
        de instelling net is uitgezet - anders blijven apps gedempt staan."""
        if mute and not self.cfg.get("mute_other_apps", False):
            return
        self._app_mute.request(mute)

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
                    condition_on_previous_text=False,
                    initial_prompt=self._vocab_prompt())
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
        self._app_mute_request(False)
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

    def build_menu(self):
        """Minimaal traymenu: alles staat in het instellingenvenster."""
        from pystray import Menu, MenuItem as Item
        return Menu(
            Item(lambda item: f"{tr('menu_hotkey')}: {self.cfg['hotkey']}",
                 None, enabled=False),
            Menu.SEPARATOR,
            Item(tr("menu_settings"), self.open_settings, default=True),
            Item(tr("menu_history"), Menu(self._history_items)),
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
        threading.Thread(target=self._update_loop, daemon=True).start()
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
