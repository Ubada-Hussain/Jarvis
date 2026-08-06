from ddgs import DDGS

def search_internet(query: str, max_results: int = 5) -> str:
    """
    Searches the internet using DuckDuckGo and returns a formatted string of results.
    """
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "No results found."
        
        formatted_results = []
        for i, res in enumerate(results):
            title = res.get('title', 'No Title')
            href = res.get('href', 'No URL')
            body = res.get('body', 'No Description')
            formatted_results.append(f"[{i+1}] Title: {title}\nURL: {href}\nSnippet: {body}\n")
            
        return "\n".join(formatted_results)
    except Exception as e:
        return f"Error performing web search: {str(e)}"

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

def open_url(url: str) -> str:
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
            return f"Successfully opened {url} in the default web browser."
        else:
            return f"Failed to open {url} in the browser."
    except Exception as e:
        return f"Error opening URL: {str(e)}"

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

def open_file_explorer(path: str = None) -> str:
    """
    Safely opens Windows Explorer to a specific directory.
    """
    try:
        print(f"[ACTION] Opening File Explorer: {path or 'Default'}")
        if path and os.path.isdir(path):
            os.startfile(path)
            return f"Successfully opened file explorer at {path}."
        else:
            # Fallback to current directory or default
            os.startfile(".")
            return "Successfully opened file explorer in the current directory."
    except Exception as e:
        return f"Error opening file explorer: {str(e)}"

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

def open_system_settings(setting_page: str = None) -> str:
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
            return f"Successfully opened system settings ({uri})."
        else:
            return "Failed to open system settings."
    except Exception as e:
        return f"Error opening system settings: {str(e)}"

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

def play_media(query: str) -> str:
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
            return f"Successfully searched and played '{query}' on YouTube."
        else:
            return f"Failed to play '{query}'."
    except Exception as e:
        return f"Error playing media: {str(e)}"

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

def remember_file(file_path: str) -> str:
    """
    Reads a file and ingests its contents into JARVIS's long-term memory (ChromaDB).
    """
    try:
        from core.rag_ingestion import ingest_file_to_chroma
        from core.database import LongTermMemory
        
        ltm = LongTermMemory()
        return ingest_file_to_chroma(file_path, ltm)
    except Exception as e:
        return f"Error remembering file: {str(e)}"

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
