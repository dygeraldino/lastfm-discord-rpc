"""Simple localization system for LastfmPresence.

Keys are Spanish (the original UI language). English is the first
translation target. Default language is Spanish for backwards compatibility.
The selected language is persisted in the user config file.
"""

from __future__ import annotations

from typing import Optional

from src.infrastructure.persistence.json_config_repository import JsonConfigRepository


# Translation table: language -> {spanish_key: translated_value}
# Spanish ("es") is the identity map: keys are already Spanish.
TRANSLATIONS: dict[str, dict[str, str]] = {
    "es": {},
    "en": {
        # --- Player window ---
        "Sin portada": "No cover",
        "CONECTANDO": "CONNECTING",
        "Buscando tu última reproducción…": "Looking for your last played track…",
        "Leyendo tu actividad de Last.fm.": "Reading your Last.fm activity.",
        "Abrir en Last.fm": "Open on Last.fm",
        "Carátula": "Cover art",
        "Automática": "Automatic",
        "Guardar carátula": "Save cover",
        "Guardada": "Saved",
        "Quitar": "Remove",
        "Recientes": "Recent",
        "Volver a la actual": "Back to current",
        "Datos de Last.fm": "Last.fm data",
        "Sin carátulas personalizadas": "No custom covers",
        "Actualizando…": "Updating…",
        "No se pudo conectar con Last.fm.": "Could not connect to Last.fm.",
        "AHORA SUENA": "NOW PLAYING",
        "ÚLTIMA REPRODUCCIÓN": "LAST PLAYED",
        "VISTA PREVIA": "PREVIEW",
        "SIN CONFIGURAR": "NOT CONFIGURED",
        "Conecta tu cuenta": "Connect your account",
        "Añade tus credenciales de Last.fm y Discord para empezar.": "Add your Last.fm and Discord credentials to get started.",
        "Abrir ajustes": "Open settings",
        "Sin datos": "No data",
        "EN ESPERA": "IDLE",
        "Sin reproducción": "No playback",
        "Cuando empieces a escuchar algo, aparecerá aquí.": "When you start listening to something, it will appear here.",
        "Actualizar": "Refresh",
        "No se pudo actualizar. Se muestra la última lectura.": "Could not update. Showing the last read.",
        "No se pudo actualizar": "Could not update",
        "SIN CONEXIÓN": "OFFLINE",
        "No se pudo leer Last.fm": "Could not read Last.fm",
        "Reintentar": "Retry",
        "Sin conexión": "No connection",
        "Buscando carátulas en Deezer y MusicBrainz…": "Looking for cover art on Deezer and MusicBrainz…",
        "Consultando fuentes alternativas.": "Consulting alternative sources.",
        "No se encontraron carátulas alternativas.": "No alternative cover art found.",
        "No se pudieron consultar las fuentes alternativas.": "Could not consult alternative sources.",
        "Sin\nportada": "No\ncover",
        "Personalizada": "Custom",
        "No se pudo guardar la carátula.": "Could not save the cover.",
        "Sin portada. Se usará el logo de la app.": "No cover. The app logo will be used.",
        "Guardada. Discord la usará cuando cambie la pista.": "Saved. Discord will use it when the track changes.",
        "No se pudo quitar la personalización.": "Could not remove the customization.",
        "Personalización eliminada. Se usará la carátula automática.": "Customization removed. Automatic cover will be used.",
        "Esta canción no tenía una carátula personalizada.": "This song had no custom cover.",
        # --- OverrideManager ---
        "LastfmPresence - Carátulas personalizadas": "LastfmPresence - Custom covers",
        "Carátulas personalizadas": "Custom covers",
        "Se aplican cuando suena cada canción.": "Applied when each song plays.",
        "Cerrar": "Close",
        "Todavía no has personalizado ninguna carátula.": "You haven't customized any cover yet.",
        "0 personalizadas": "0 custom",
        "1 personalizada": "1 custom",
        # --- Settings window ---
        "LastfmPresence - Ajustes": "LastfmPresence - Settings",
        "Ajustes": "Settings",
        "Conexión con Last.fm y Discord": "Connection with Last.fm and Discord",
        "Configura tu cuenta para empezar": "Configure your account to get started",
        "Conexión": "Connection",
        "Last.fm alimenta tu estado; Discord lo muestra.": "Last.fm feeds your status; Discord shows it.",
        "Usuario de Last.fm": "Last.fm username",
        "API Key de Last.fm": "Last.fm API Key",
        "Discord Client ID": "Discord Client ID",
        "Obtener API Key": "Get API Key",
        "Crear aplicación": "Create application",
        "Comportamiento": "Behavior",
        "Cómo se actualiza el estado en Discord.": "How the status is updated on Discord.",
        "Intervalo de consulta": "Poll interval",
        "Cada cuántos segundos se consulta Last.fm.": "How many seconds between Last.fm polls.",
        "Carátulas alternativas": "Alternative covers",
        "Deezer y MusicBrainz cuando Last.fm no trae portada.": "Deezer and MusicBrainz when Last.fm has no cover.",
        "Probar conexión": "Test connection",
        "Guardar cambios": "Save changes",
        "Ocultar": "Hide",
        "Mostrar": "Show",
        "El intervalo debe ser un número entero.": "The interval must be a whole number.",
        "El intervalo mínimo es de 5 segundos.": "The minimum interval is 5 seconds.",
        "Faltan datos:": "Missing data:",
        "usuario de Last.fm": "Last.fm user",
        "API Key": "API Key",
        "Discord Client ID": "Discord Client ID",
        "No se pudo guardar la configuración.": "Could not save configuration.",
        "Guardado. Aplicando cambios…": "Saved. Applying changes…",
        "Guardado, pero no se pudo reiniciar Discord.": "Saved, but Discord could not be restarted.",
        "Listo. Discord usará estos ajustes.": "Done. Discord will use these settings.",
        "Probando…": "Testing…",
        "Probando credenciales de Last.fm…": "Testing Last.fm credentials…",
        "Usuario y API Key son obligatorios.": "Username and API Key are required.",
        "Last.fm respondió HTTP {status}.": "Last.fm responded HTTP {status}.",
        "Credenciales rechazadas.": "Credentials rejected.",
        "Last.fm: {message}": "Last.fm: {message}",
        "Conexión correcta con Last.fm.": "Connection to Last.fm successful.",
        "Last.fm tardó demasiado en responder.": "Last.fm took too long to respond.",
        "No se pudo conectar con Last.fm.": "Could not connect to Last.fm.",
        "Ahora": "Now",
        "Actualizado": "Updated",
        "1 carátula personalizada": "1 custom cover",
        "{count} carátulas personalizadas": "{count} custom covers",
        # --- Relative time (theme.py) ---
        "hace un momento": "just now",
        "hace {minutes} min": "{minutes} min ago",
        "hace {hours} h": "{hours} h ago",
        "hace {days} d": "{days} d ago",
        # --- Tray menu ---
        "Abrir reproductor": "Open player",
        "Abrir logs": "Open logs",
        "Buscar actualizaciones": "Check for updates",
        "Salir": "Exit",
        "LastfmPresence - Reproductor de Last.fm": "LastfmPresence - Last.fm Player",
    }
}

_current_lang: str = "es"


def get_language() -> str:
    """Return the currently active language code."""
    return _current_lang


def set_language(lang: str) -> None:
    """Set the active language code."""
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang


def load_language() -> str:
    """Load the persisted language from config, defaulting to Spanish."""
    global _current_lang
    try:
        repo = JsonConfigRepository()
        config = repo.load()
        lang = config.get("language", "es")
        if lang in TRANSLATIONS:
            _current_lang = lang
    except Exception:
        _current_lang = "es"
    return _current_lang


def save_language(lang: str) -> None:
    """Persist the language preference to config and activate it."""
    try:
        repo = JsonConfigRepository()
        config = repo.load()
        config["language"] = lang
        repo.save(config)
        set_language(lang)
    except Exception:
        pass


def t(spanish_text: str, **kwargs) -> str:
    """Translate a Spanish string to the current language.

    If the current language is Spanish, the original string is returned.
    Dynamic placeholders like {minutes} are preserved in translations and
    formatted with kwargs.
    """
    if _current_lang == "es":
        result = spanish_text
    else:
        translations = TRANSLATIONS.get(_current_lang, {})
        result = translations.get(spanish_text, spanish_text)

    if kwargs:
        try:
            result = result.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return result
