# Dicteer

Lokale spraak-naar-tekst voor Windows, zoals Wispr Flow maar gratis en 100% offline. Draait op je NVIDIA GPU met Whisper (large-v3-turbo), herkent Nederlands en Engels automatisch.

## Installatie

1. Installeer [Python 3.10 t/m 3.12](https://www.python.org/downloads/) — vink **"Add python.exe to PATH"** aan.
2. Dubbelklik op **install.bat** (eenmalig, duurt enkele minuten).
3. Dubbelklik op **start.bat**. De eerste keer wordt het spraakmodel gedownload (~1,6 GB); daarna is alles offline.

install.bat zet ook een snelkoppeling **Dicteer** op je bureaublad — voortaan start je gewoon daarmee.

Er verschijnt een microfoontje in je systeemvak (rechtsonder). Groen = klaar voor gebruik.

## Gebruik

Zet je cursor in een tekstveld (mail, Word, browser, waar dan ook):

- Druk **`Ctrl+Shift+S`** → opname start. Praat. Druk nogmaals **`Ctrl+Shift+S`** → de tekst wordt automatisch geplakt.
- Piepje hoog = opname gestart, piepje laag = gestopt.
- Tijdens de opname zie je onderin beeld een klein venstertje met geluidsbalkjes die meebewegen met je stem; tijdens het omzetten staat er "Bezig met omzetten...". Het verdwijnt vanzelf. Uitzetten kan met `"overlay": false` in config.json.

Andere sneltoets? Pas `hotkey` aan in config.json (bijv. `"f9"`).

**Stoppen**: rechtsklik op het tray-icoon → **Afsluiten**.

Kleuren van het tray-icoon: grijs = model laden, groen = klaar, rood = opname, oranje = bezig met omzetten.

## Instellingen

Bij het starten opent het instellingenvenster vanzelf (uit te zetten via *Show this window at startup*). Het venster sluiten stopt Dicteer niet — hij blijft in de tray draaien; afsluiten doe je via rechtsklik op het tray-icoon → Exit. Het venster heeft een donker dashboard-uiterlijk met zijbalk (General / Recording / Discord / System) en naast Save en Cancel ook een **Apply**-knop die toepast zonder te sluiten. De interface is standaard Engels en is om te zetten naar Nederlands, Duits, Spaans of Frans (*Interface language*). Nieuw: *Deafen Discord* (je hoort zelf ook niets tijdens het dicteren) en *Pause media* (muziek/video pauzeert tijdens de opname en hervat daarna — werkt als play/pauze-schakelaar).

**Dubbelklik op het tray-icoon** (of rechtsklik → *Instellingen...*) voor het instellingenvenster: daar stel je alles in — sneltoets, modus, taal, model, piep-volume, overlay, Discord, automatisch starten — zonder in config.json te hoeven werken. Opslaan past alles direct toe.

Rechtsklik op het tray-icoon:

- **Modus**: aan/uit schakelen (standaard) of ingedrukt houden (walkietalkie).
- **Taal**: automatisch detecteren (alle talen), of vast: Nederlands, Engels, Duits, Frans, Spaans, Italiaans, Portugees, Pools, Turks.
- **Geschiedenis**: je laatste 10 dictaten; aanklikken zet de tekst weer op je klembord.
- **Discord dempen tijdens opname** + **Discord koppelen / testen**: zie hieronder.
- **Automatisch starten met Windows**: aan/uit, geen gedoe met de opstartmap.

Meer opties in `config.json` (via traymenu te openen):

| Optie | Uitleg |
|---|---|
| `hotkey` | Sneltoets, bijv. `"ctrl+shift+s"` of `"f9"` |
| `beep_volume` | Volume van de piepjes, `0.0` (stil) t/m `1.0` (hard); standaard `0.15` |
| `overlay` | Zwevend venstertje onderin beeld tijdens opname/omzetten |
| `suppress_hotkey` | Onderschep de sneltoets zodat die niets triggert in andere programma's |
| `model` | `large-v3-turbo` (standaard), `large-v3` (nauwkeurigst), `medium` (lichter) |
| `device` | `auto` probeert GPU, valt terug op CPU |
| `restore_clipboard` | Zet je oude klembordinhoud terug na het plakken |
| `history` | Geschiedenis bijhouden (staat lokaal in `history.json`) |

Na het wijzigen van config.json: rechtsklik op het tray-icoon → **Config herladen**. Een nieuwe sneltoets werkt direct; een ander model wordt op de achtergrond opnieuw geladen.

## Updaten

Nieuwe versie gekregen? Sluit Dicteer af, vervang `dicteer.py` (en evt. `README.md`) door de nieuwe versie en start opnieuw met `start.bat`. Je `config.json`, de venv en het gedownloade model blijven staan — `install.bat` hoeft niet opnieuw. Alleen als `requirements.txt` is veranderd voer je eenmalig uit: `venv\Scripts\python.exe -m pip install -r requirements.txt`.

## Discord automatisch dempen

Werkt via de **officiële Discord-API**: tijdens het dicteren gaat je Discord-mic op mute (mét het bekende icoontje, zichtbaar voor jou en je team) en daarna weer aan. Stond je zelf al op mute, dan blijf je gemute. Eenmalige setup, ~5 minuten:

1. Ga naar <https://discord.com/developers/applications> → **New Application** → noem hem bijv. "Dicteer".
2. Tabblad **OAuth2**: kopieer de **Client ID**; klik **Reset Secret** en kopieer de **Client Secret**. Voeg onder **Redirects** toe: `http://127.0.0.1` en sla op.
3. Zet beide in config.json (traymenu → Config openen):
   `"discord_client_id": "…"`, `"discord_client_secret": "…"`
4. Traymenu → **Config herladen**, daarna **Discord koppelen / testen**. Keur het venster in Discord goed → ter controle gaat je mic 2 seconden op mute.

Daarna gaat het vanzelf zolang **Discord dempen tijdens opname** aangevinkt staat. De koppeling staat lokaal in `discord_token.json`; je secret verlaat je pc niet.

## Automatisch starten met Windows

Rechtsklik op het tray-icoon → vink **Automatisch starten met Windows** aan. Klaar.

## Problemen

- **Werkt de GPU niet?** Kijk in `dicteer.log`. Het programma valt automatisch terug op CPU (langzamer maar werkt altijd).
- **Er wordt niets geplakt in een programma dat als administrator draait** — start Dicteer dan ook als administrator.
- **Geen opname?** Controleer je microfoon: Windows-instellingen → Privacy → Microfoon.
- **Crasht Dicteer bij het opstarten (icoontje verschijnt en verdwijnt)?** Start één keer met `debug.bat` — dan blijft er een venster open waarin je de foutmelding ziet. Kijk ook in `dicteer_crash.log`. Helpt dat niet: controleer in Windows-beveiliging → Beveiligingsgeschiedenis of Defender Dicteer/Python heeft geblokkeerd (programma's met een globale sneltoets worden soms ten onrechte tegengehouden) en voeg desnoods de Dicteer-map toe als uitsluiting.
- **Lijkt Dicteer direct af te sluiten na start.bat?** Waarschijnlijk draait hij al — kijk bij de verborgen pictogrammen rechtsonder (pijltje omhoog in de taakbalk). Dicteer bewaakt dit nu zelf: een tweede start toont een melding.
