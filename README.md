# Dicteer

Local speech-to-text dictation for Windows — free, 100% offline, powered by Whisper (large-v3-turbo) on your own GPU. Press a hotkey, speak, and your words are pasted wherever your cursor is. Works in any app. Like Wispr Flow, but yours.

## Features

- **Dictate anywhere**: press `Ctrl+Shift+S`, speak, press again — your text is pasted into whatever app has focus
- **~100 languages** with automatic detection (or pin one: Dutch, English, German, French, Spanish, Italian, Portuguese, Polish, Turkish, ...)
- **Live preview**: see your words appear in the on-screen overlay while you speak
- **100% private**: everything runs locally on your machine; audio never leaves your PC
- **Discord integration**: automatically mute and/or deafen Discord while dictating (via the official Discord API), restored afterwards
- **Virtual mic mute** (optional): while dictating, mute the virtual microphone (Voicemod, Voicemeeter, VB-Cable, ...) that other apps listen to — Discord, games, OBS and Teams hear nothing while Dicteer keeps hearing your real mic; restored afterwards. (Windows offers no true per-app mic muting, so this is the reliable way.)
- **Smart media pause**: playing music/video is paused during recording and resumed afterwards — only what was actually playing
- **Modern dark settings UI** (web-based) in English, Dutch, German, Spanish and French
- **Projects** (optional): save dictations per project, add an AI instruction per project, and export or copy a whole project at once — ready to paste into your favorite AI model. Switch projects with one click in the overlay
- **Smart overlay**: live waveform and preview while you speak, per-dictation toggle for auto-paste/auto-send, current project display — all without stealing focus from the app you're typing in
- **Quality of life**: history page (view, copy and clean up dictations), statistics, microphone test meter, hotkey recorder, Esc to cancel, beeps with volume control, start with Windows, desktop shortcut

## Requirements

- Windows 10/11
- [Python 3.10 or newer](https://www.python.org/downloads/) — check **"Add python.exe to PATH"** during installation
- **GPU acceleration is NVIDIA-only** (the speech engine, CTranslate2, only supports CUDA). With an NVIDIA card (GTX 10-series or newer), transcription takes seconds.
- **AMD and Intel GPUs are not supported for acceleration** — Dicteer detects this automatically and runs on the **CPU** instead. This works fine, just slower; pick the `medium` or `small` model for extra speed. The installer also skips the ~600 MB of NVIDIA libraries on those systems.

## Installation

1. Download the latest release and extract it to a folder (e.g. `Documents\Dicteer`)
2. Double-click **install.bat** (one-time, takes a few minutes)
3. Start Dicteer with the **Dicteer** shortcut on your desktop (created by the installer) or **start.bat**

On first start the speech model (~1.6 GB) is downloaded once; after that everything works offline. A microphone icon appears in the system tray — green means ready.

## Usage

Put your cursor in any text field:

- Press **`Ctrl+Shift+S`** → recording starts (high beep, overlay appears). Speak. Press **`Ctrl+Shift+S`** again → your text is pasted (low beep).
- Press **`Esc`** during a recording to cancel it.
- High beep = recording started, low beep = stopped. Tray icon: grey = loading model, green = ready, red = recording, orange = transcribing.
- With *auto-send* enabled, the overlay shows an **Auto-paste** chip during recording — click it to keep this one dictation from being sent automatically (handy when you spot a typo in the preview).

**Quitting**: right-click the tray icon → Exit. Closing the settings window does *not* quit the app; it keeps running in the tray.

## Settings

The settings window opens at startup (disable via *Show this window at startup*). You can also open it any time by double-clicking the tray icon.

- **General**: hotkey (click to record a new combination), mode (press to start/stop, or hold while speaking), dictation language, model, device, interface language
- **Recording**: pause media, mute/deafen Discord, auto-send (Enter after pasting), microphone selection with live test meter, live preview, beeps and volume, overlay
- **Dictionary**: words/names to recognize better, and replacement rules
- **Projects**: enable projects, create/activate/remove them, set an AI instruction per project (added at the top of every export), export or copy a project
- **History**: read back and copy recent dictations; view a project's dictations and delete individual ones before exporting
- **Discord**: client ID/secret and the link button (see below)
- **Statistics**: dictations, words, recording time, estimated time saved
- **System**: start with Windows, history, clipboard restore, desktop shortcut, backup/restore, open config/log

Changes are saved via the save bar that appears at the bottom whenever something changed. Closing the window keeps Dicteer running in the tray.

### Projects (optional)

Enable *Use projects* on the Projects page and create e.g. "Project A". Every dictation is now also saved under the active project (`projects\Project A.txt`). The overlay shows the active project during recording — click it to switch to the next project. Give the project an AI instruction (e.g. "Summarize these dictations into a spec") and use **Export**/**Copy**: the instruction is placed on top, so the result can be pasted straight into any AI chat.

## Discord auto-mute/deafen (optional)

Uses the official Discord API: while dictating, your Discord mic is muted (with the familiar mute icon, visible to your team) and restored afterwards. If you were already muted, you stay muted. One-time setup (~5 minutes):

1. Go to <https://discord.com/developers/applications> → **New Application** → name it e.g. "Dicteer"
2. **OAuth2** tab: copy the **Client ID**; click **Reset Secret** and copy the **Client Secret**. Under **Redirects**, add `http://127.0.0.1` and save
3. Paste both into Dicteer's settings (Discord page) and click **Apply**
4. Click **Link / test Discord** and approve the popup inside Discord — as a test your mic is muted for 2 seconds

The link is stored locally in `discord_token.json`; your secret never leaves your PC.

## Updating

Dicteer checks GitHub for new releases and shows a notification plus an update button in the settings when one is available. Manual update: quit Dicteer, replace `dicteer.py` (and any other changed files) with the new version, restart. Your config, the venv and the downloaded model are untouched. Only when `requirements.txt` changed, run once: `venv\Scripts\python.exe -m pip install -r requirements.txt`.

## Troubleshooting

- **GPU not working?** Check `dicteer.log`. Dicteer automatically falls back to CPU. Note: only NVIDIA GPUs are supported — on AMD/Intel systems CPU mode is expected behavior.
- **Nothing is pasted into an app running as administrator** — run Dicteer as administrator too.
- **No recording?** Check Windows Settings → Privacy → Microphone.
- **Crashes at startup (icon appears then disappears)?** Run `debug.bat` once — a console window stays open with the error. Also check `dicteer_crash.log`. If both are empty, check Windows Security → Protection history: apps with a global hotkey are sometimes blocked by Defender; add the Dicteer folder as an exclusion.
- **Seems to quit right after starting?** It's probably already running — check the hidden tray icons (the ^ arrow in your taskbar). A second start shows a message.

## Privacy

All recognition happens on your machine. No audio, text or telemetry is sent anywhere. The only network traffic is the one-time model download (Hugging Face), the optional Discord link (Discord API) and the update check (GitHub API).

## Support

Dicteer is free and open source. If it saves you time, you can support development here:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/G7V323BNTU)

Or visit <https://ko-fi.com/sudareq>. Thank you!

## License

MIT — see [LICENSE](LICENSE).
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              