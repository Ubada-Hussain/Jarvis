from ddgs import DDGS
from core.verification import ToolResult, VerificationStatus

def search_internet(query: str, max_results: int = 5) -> ToolResult:
    """
    Searches the internet using DuckDuckGo and returns a formatted string of results.
    """
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return ToolResult(
                status=VerificationStatus.VERIFIED_SUCCESS,
                message="No results found.",
                evidence="DDGS().text returned an empty list."
            )
        
        formatted_results = []
        for i, res in enumerate(results):
            title = res.get('title', 'No Title')
            href = res.get('href', 'No URL')
            body = res.get('body', 'No Description')
            formatted_results.append(f"[{i+1}] Title: {title}\nURL: {href}\nSnippet: {body}\n")
            
        return ToolResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            message="\n".join(formatted_results),
            evidence=f"DDGS().text returned {len(results)} results."
        )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Error performing web search: {str(e)}",
            evidence="Exception raised during DDGS API call."
        )

# The schema for Groq function calling
SEARCH_INTERNET_TOOL = {
    "type": "function",
    "function": {
        "name": "search_internet",
        "description": "Searches the internet for real-time information, news, weather, or facts.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up on the internet (e.g., 'current price of Bitcoin', 'weather in London today')."
                }
            },
            "required": ["query"]
        }
    }
}

import webbrowser
import subprocess

def open_url(url: str) -> ToolResult:
    """
    Opens a URL in the default system web browser.
    """
    try:
        # Ensure url has http:// or https://
        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'https://' + url
            
        print(f"[ACTION] Opening browser to: {url}")
        success = webbrowser.open(url)
        if success:
            return ToolResult(
                status=VerificationStatus.UNVERIFIED,
                message=f"Successfully executed command to open {url} in the default web browser.",
                evidence="webbrowser.open returned True, but external browser state cannot be verified."
            )
        else:
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"Failed to open {url} in the browser.",
                evidence="webbrowser.open returned False."
            )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Error opening URL: {str(e)}",
            evidence="Exception raised during webbrowser.open."
        )

OPEN_URL_TOOL = {
    "type": "function",
    "function": {
        "name": "open_url",
        "description": "Opens a website URL in the user's default web browser. Use this when the user asks to 'open youtube', 'go to google', or open any website.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to open (e.g., 'https://www.youtube.com')."
                }
            },
            "required": ["url"]
        }
    }
}

import os

def open_file_explorer(path: str = None) -> ToolResult:
    """
    Safely opens Windows Explorer to a specific directory.
    """
    try:
        print(f"[ACTION] Opening File Explorer: {path or 'Default'}")
        if path and os.path.isdir(path):
            os.startfile(path)
            return ToolResult(
                status=VerificationStatus.UNVERIFIED,
                message=f"Successfully requested file explorer to open at {path}.",
                evidence="os.startfile executed without errors, but external window state is unverified."
            )
        else:
            # Fallback to current directory or default
            os.startfile(".")
            return ToolResult(
                status=VerificationStatus.UNVERIFIED,
                message="Successfully requested file explorer to open in the current directory.",
                evidence="os.startfile executed without errors, but external window state is unverified."
            )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Error opening file explorer: {str(e)}",
            evidence="Exception raised during os.startfile."
        )

OPEN_FILE_EXPLORER_TOOL = {
    "type": "function",
    "function": {
        "name": "open_file_explorer",
        "description": "Opens the Windows File Explorer. Use this when the user asks to 'open file explorer', 'show my files', or 'open folder'.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Optional specific path to open. Leave empty for default."
                }
            }
        }
    }
}

def open_system_settings(setting_page: str = None) -> ToolResult:
    """
    Opens Windows settings.
    """
    try:
        print(f"[ACTION] Opening System Settings: {setting_page or 'Default'}")
        uri = "ms-settings:"
        if setting_page:
            uri += setting_page
        success = webbrowser.open(uri)
        if success:
            return ToolResult(
                status=VerificationStatus.UNVERIFIED,
                message=f"Successfully requested system settings ({uri}) to open.",
                evidence="webbrowser.open returned True, but external window state cannot be verified."
            )
        else:
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message="Failed to open system settings.",
                evidence="webbrowser.open returned False."
            )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Error opening system settings: {str(e)}",
            evidence="Exception raised during webbrowser.open."
        )

OPEN_SYSTEM_SETTINGS_TOOL = {
    "type": "function",
    "function": {
        "name": "open_system_settings",
        "description": "Opens Windows System Settings. Use this when the user asks to 'open settings', 'check windows update' (windowsupdate), 'display settings' (display), etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "setting_page": {
                    "type": "string",
                    "description": "The specific settings page to open (e.g. 'windowsupdate', 'display', 'bluetooth'). Leave empty for general settings."
                }
            }
        }
    }
}

def play_media(query: str) -> ToolResult:
    """
    Searches for and plays a song/video on YouTube.
    """
    try:
        print(f"[ACTION] Playing media: {query}")
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={encoded_query}"
        success = webbrowser.open(url)
        if success:
            return ToolResult(
                status=VerificationStatus.UNVERIFIED,
                message=f"Successfully executed command to play '{query}' on YouTube.",
                evidence="webbrowser.open returned True, but playback state cannot be verified."
            )
        else:
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"Failed to play '{query}'.",
                evidence="webbrowser.open returned False."
            )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Error playing media: {str(e)}",
            evidence="Exception raised during webbrowser.open."
        )

PLAY_MEDIA_TOOL = {
    "type": "function",
    "function": {
        "name": "play_media",
        "description": "Plays a requested song, video, or media on YouTube. Use this when the user asks to 'play [song name]', 'play [video]', etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The name of the song, artist, or video to play."
                }
            },
            "required": ["query"]
        }
    }
}

def remember_file(file_path: str) -> ToolResult:
    """
    Reads a file and ingests its contents into JARVIS's long-term memory (ChromaDB).
    """
    try:
        from core.rag_ingestion import ingest_file_to_chroma
        from core.database import LongTermMemory
        
        ltm = LongTermMemory()
        result_msg = ingest_file_to_chroma(file_path, ltm)
        return ToolResult(
            status=VerificationStatus.UNVERIFIED,
            message=result_msg,
            evidence="Ingestion function returned without crashing. Deep DB check not implemented yet."
        )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Error remembering file: {str(e)}",
            evidence="Exception raised during ingestion."
        )

REMEMBER_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "remember_file",
        "description": "Reads a file (.pdf, .txt, .docx) and saves its contents into long-term memory for future retrieval. Use this when the user asks you to read, remember, or learn from a specific file.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute or relative path to the file."
                }
            },
            "required": ["file_path"]
        }
    }
}

def switch_voice_profile(profile_name: str) -> ToolResult:
    """
    Switches the TTS voice profile for the session.
    """
    try:
        from core.tts_engine import set_voice_profile
        success = set_voice_profile(profile_name)
        if success:
            return ToolResult(
                status=VerificationStatus.UNVERIFIED,
                message=f"Successfully switched voice profile to '{profile_name}'.",
                evidence="set_voice_profile returned True, but voice synthesis validation not performed."
            )
        else:
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"Failed: '{profile_name}' is not a valid profile. Valid profiles are: default, young_man, young_woman, old_man, old_woman, kid, flirty.",
                evidence="set_voice_profile returned False."
            )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Error switching voice profile: {str(e)}",
            evidence="Exception raised during voice profile switch."
        )

SWITCH_VOICE_PROFILE_TOOL = {
    "type": "function",
    "function": {
        "name": "switch_voice_profile",
        "description": "Switches the voice profile of JARVIS. Use this when the user asks you to change your voice (e.g. 'talk like an old man', 'use flirty voice', 'change voice to kid').",
        "parameters": {
            "type": "object",
            "properties": {
                "profile_name": {
                    "type": "string",
                    "enum": ["default", "young_man", "young_woman", "old_man", "old_woman", "kid", "flirty"],
                    "description": "The name of the voice profile to switch to."
                }
            },
            "required": ["profile_name"]
        }
    }
}
