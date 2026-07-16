"""Maakt de bureaublad-snelkoppeling voor Dicteer (gebruikt door install.bat)."""
from dicteer import make_desktop_shortcut

if __name__ == "__main__":
    try:
        print("Snelkoppeling gemaakt:", make_desktop_shortcut())
    except Exception as e:
        print("Snelkoppeling maken mislukt:", e)
