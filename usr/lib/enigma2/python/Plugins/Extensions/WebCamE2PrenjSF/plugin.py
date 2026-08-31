import os
import sys
import json
import datetime
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Components.Label import Label
from Components.ActionMap import ActionMap
from enigma import getDesktop, eDVBDB
from Components.Pixmap import Pixmap
from Components.MenuList import MenuList
from Components.ConfigList import ConfigListScreen
from Components.config import config, ConfigSelection, ConfigSubsection, getConfigListEntry
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
import threading
import subprocess
import time
from enigma import eTimer, eServiceReference

# Add plugin directory to sys.path for Python 2/3 compatibility
plugin_path = os.path.dirname(os.path.abspath(__file__))
if plugin_path not in sys.path:
    sys.path.append(plugin_path)

PLUGIN_VERSION = "1.5"
PLUGIN_NAME = "WebCamE2PrenjSF"
PLUGIN_DESC = "WebCam for userbouquet enigma2 Satelitski Forum @prenj"
PLUGIN_ICON = "/usr/lib/enigma2/python/Plugins/Extensions/WebCamE2PrenjSF/icon.png"
PLUGIN_LOGO = "/usr/lib/enigma2/python/Plugins/Extensions/WebCamE2PrenjSF/logoprenj.png"
SETTINGS_FILE = "/usr/lib/enigma2/python/Plugins/Extensions/WebCamE2PrenjSF/settings.json"
BROKEN_LINKS_LOG = "/tmp/webcam_broken_links.log"

# Default settings
DEFAULT_SETTINGS = {
    'quality': '1080',
    'mini_skin_opacity': '50',
    'player_type': '4097',
    'webcam_timeout': 20,
    'youtube_timeout_mode': 'fixed',
    'youtube_timeout_min': 15,
    'youtube_timeout_max': 30,
    'youtube_timeout_step': 5
}

def load_settings():
    """Load settings from JSON file"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
                for key in DEFAULT_SETTINGS:
                    if key not in settings:
                        settings[key] = DEFAULT_SETTINGS[key]
                return settings
    except Exception as e:
        print("[WebCamE2] Error loading settings: {}".format(e))
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """Save settings to JSON file"""
    try:
        settings_dir = os.path.dirname(SETTINGS_FILE)
        if not os.path.exists(settings_dir):
            os.makedirs(settings_dir, mode=0o755)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
        return True
    except Exception as e:
        print("[WebCamE2] Error saving settings: {}".format(e))
        return False

def load_quality_setting():
    settings = load_settings()
    return settings.get('quality', '1080')

def get_video_format(quality):
    format_map = {
        'best': 'bestvideo+bestaudio/best',
        '2160': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',
        '1080': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        '720': 'bestvideo[height<=720]+bestaudio/best[height<=720]'
    }
    return format_map.get(quality, 'bestvideo[height<=1080]+bestaudio/best[height<=1080]')

def get_streamlink_quality(quality):
    quality_map = {
        'best': 'best',
        '2160': '2160p,4k,best',
        '1080': '1080p,720p,best',
        '720': '720p,480p,best'
    }
    return quality_map.get(quality, '1080p,best')

def get_player_type():
    settings = load_settings()
    return settings.get('player_type', '4097')

def get_mini_skin_opacity():
    settings = load_settings()
    return settings.get('mini_skin_opacity', '50')

def get_webcam_timeout():
    settings = load_settings()
    return int(settings.get('webcam_timeout', 20))

def get_youtube_timeout_mode():
    settings = load_settings()
    return settings.get('youtube_timeout_mode', 'fixed')

def get_youtube_timeout_min():
    settings = load_settings()
    return int(settings.get('youtube_timeout_min', 15))

def get_youtube_timeout_max():
    settings = load_settings()
    return int(settings.get('youtube_timeout_max', 30))

def get_youtube_timeout_step():
    settings = load_settings()
    return int(settings.get('youtube_timeout_step', 5))

def log_broken_link(url, title, error_msg=""):
    """Loguje neispravan link u fajl"""
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(BROKEN_LINKS_LOG, 'a') as f:
            f.write("\n{}\n".format('─'*80))
            f.write("[{}]\n".format(timestamp))
            f.write("TITLE: {}\n".format(title))
            f.write("URL: {}\n".format(url))
            if error_msg:
                f.write("ERROR: {}\n".format(error_msg))
            f.write("{}\n".format('─'*80))
    except:
        pass

def is_youtube_url(url):
    """Proverava da li je URL YouTube link"""
    youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com', 'm.youtube.com', 'yewtu.be', 'invidious']
    url_lower = url.lower()
    for domain in youtube_domains:
        if domain in url_lower:
            return True
    return False

# Python 2/3 compatibility for urllib
if sys.version_info[0] >= 3:
    from urllib.request import urlopen
    from urllib.error import URLError, HTTPError
    to_unicode = str
else:
    from urllib2 import urlopen, URLError, HTTPError
    to_unicode = unicode


class LogViewerScreen(Screen):
    """Screen za pregled log fajla sa skrolovanjem - FHD verzija"""
    skin = """
        <screen position="center,center" size="1920,1080" title="Broken Links Log Viewer" backgroundColor="#228B22" flags="wfNoBorder">
            <eLabel position="0,0" size="1920,1080" backgroundColor="#0a1a0a" zPosition="-1" />
            <eLabel position="0,0" size="1920,80" backgroundColor="#1a1a1a" zPosition="1" />
            <eLabel text="BROKEN LINKS LOG" position="40,20" size="600,50" font="Regular;34" foregroundColor="#ffcc00" backgroundColor="#00000000" transparent="1" zPosition="2" />
            <eLabel position="0,80" size="1920,2" backgroundColor="#ffcc00" zPosition="1" />
            <widget name="log_text" position="40,100" size="1840,850" font="Regular;26" foregroundColor="#ffffff" backgroundColor="#0a1a0a" halign="left" valign="top" transparent="0" />
            <widget name="separator2" position="0,955" size="1920,3" backgroundColor="#d5fa02" zPosition="1" /> 
            <eLabel position="0,960" size="1920,120" backgroundColor="#1a1a1a" zPosition="1" />
            <widget name="info" position="40,970" size="1200,50" font="Regular;24" foregroundColor="#00ffcc" backgroundColor="#00000000" transparent="1" halign="left" zPosition="2" />
            <eLabel position="1500,975" size="50,50" backgroundColor="#ff0000" zPosition="2" />
            <eLabel text="EXIT" position="1570,970" size="100,50" font="Regular;28" foregroundColor="#ffffff" backgroundColor="#00000000" transparent="1" zPosition="2" />
            <eLabel position="1720,975" size="50,50" backgroundColor="#00ff00" zPosition="2" />
            <eLabel text="CLEAR" position="1790,970" size="120,50" font="Regular;28" foregroundColor="#ffffff" backgroundColor="#00000000" transparent="1" zPosition="2" />
            <eLabel text="▲" position="1850,120" size="40,40" font="Regular;32" foregroundColor="#ffcc00" backgroundColor="#00000000" transparent="1" halign="center" zPosition="2" />
            <eLabel text="▼" position="1850,900" size="40,40" font="Regular;32" foregroundColor="#ffcc00" backgroundColor="#00000000" transparent="1" halign="center" zPosition="2" />
            <eLabel position="0,1078" size="1920,2" backgroundColor="#ffcc00" zPosition="1" />
        </screen>
    """

    def __init__(self, session, log_file):
        Screen.__init__(self, session)
        self.session = session
        self.log_file = log_file

        self["log_text"] = Label("")
        self["info"] = Label("")
        self["separator2"] = Label()

        self["actions"] = ActionMap(["SetupActions", "DirectionActions", "ColorActions"], {
            "cancel": self.close,
            "red": self.close,
            "green": self.clear_log,
            "yellow": self.clear_log,
            "blue": self.clear_log,
            "up": self.scroll_up,
            "down": self.scroll_down,
            "left": self.scroll_page_up,
            "right": self.scroll_page_down,
        }, -1)

        self.scroll_position = 0
        self.lines = []
        self.max_lines_on_screen = 32

        self.load_log_content()

    def load_log_content(self):
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    content = f.read()
                self.lines = content.split('\n')
                self.update_display()
            else:
                self["log_text"].setText("Log file does not exist.\n\nNo broken links recorded yet.")
                self["info"].setText("No log file found")
        except Exception as e:
            self["log_text"].setText("Error reading log file:\n{}".format(str(e)))
            self["info"].setText("Error loading log")

    def update_display(self):
        if not self.lines:
            self["log_text"].setText("Log file is empty.")
            self["info"].setText("Log is empty | Red: Exit | Green: Clear")
            return

        start = self.scroll_position
        end = min(start + self.max_lines_on_screen, len(self.lines))
        visible_lines = self.lines[start:end]
        display_text = "\n".join(visible_lines)

        total_lines = len(self.lines)
        if total_lines > 0:
            percent = int((self.scroll_position / total_lines) * 100)
            self["info"].setText(
                "Lines: {}-{} of {} ({}%) | Up/Down scroll | Left/Right page | Green: Clear | Red: Exit".format(
                    start + 1, end, total_lines, percent))

        if len(display_text) > 10000:
            display_text = display_text[-10000:] + "\n\n... (truncated)"
        self["log_text"].setText(display_text)

    def scroll_up(self):
        if self.scroll_position > 0:
            self.scroll_position -= 1
            self.update_display()

    def scroll_down(self):
        if self.scroll_position + self.max_lines_on_screen < len(self.lines):
            self.scroll_position += 1
            self.update_display()

    def scroll_page_up(self):
        if self.scroll_position > 0:
            self.scroll_position = max(0, self.scroll_position - self.max_lines_on_screen)
            self.update_display()

    def scroll_page_down(self):
        if self.scroll_position + self.max_lines_on_screen < len(self.lines):
            self.scroll_position = min(len(self.lines) - self.max_lines_on_screen,
                                       self.scroll_position + self.max_lines_on_screen)
            self.update_display()

    def clear_log(self):
        def confirm_clear(answer):
            if answer:
                try:
                    with open(self.log_file, 'w') as f:
                        f.write("")
                    self.lines = []
                    self.scroll_position = 0
                    self.update_display()
                    self.session.open(MessageBox, "Log file cleared!", MessageBox.TYPE_INFO)
                except Exception as e:
                    self.session.open(MessageBox, "Error clearing log: {}".format(str(e)), MessageBox.TYPE_ERROR)

        self.session.openWithCallback(confirm_clear, MessageBox,
                                      "Are you sure you want to clear the log file?\n\nThis action cannot be undone!",
                                      MessageBox.TYPE_YESNO)


class WebCamE2PrenjSF(Screen):
    skin = """
        <screen position="center,center" size="1920,1080" title="CiefpYouTube" backgroundColor="#228B22" flags="wfNoBorder">
            <eLabel position="0,0" size="1920,100" backgroundColor="#1a1a1a" zPosition="-1" />
            <eLabel text=":: WebCamE2 Satelitski Forum - Prenj Ciefp ::" position="60,25" size="900,50" font="Regular;40" foregroundColor="#ffffff" backgroundColor="#00000000" transparent="1" />

            <widget name="camera_list" position="60,150" size="800,600" scrollbarMode="showOnDemand" itemHeight="50" font="Regular;26" foregroundColor="#ffffff" backgroundColor="#1a1a1a" zPosition="2" />

            <widget name="logo" position="900,150" size="1000,600" zPosition="1" alphatest="on" />

            <eLabel position="0,800" size="1920,150" backgroundColor="#1a1a1a" zPosition="1" />
            <widget name="status" position="0,820" size="1920,50" font="Regular;24" halign="center" foregroundColor="#ffcc00" backgroundColor="#1a1a1a" transparent="1" zPosition="2" />
            <widget name="version" position="0,870" size="1920,50" font="Regular;24" halign="center" foregroundColor="#ffcc00" backgroundColor="#1a1a1a" transparent="1" zPosition="2" />

            <eLabel position="0,980" size="1920,100" backgroundColor="#1a1a1a" zPosition="1" />
            <eLabel position="60,1015" size="30,30" backgroundColor="red" zPosition="2" />
            <eLabel text="EXIT"  position="105,1010" size="150,40" font="Regular;30" foregroundColor="#ffffff" backgroundColor="#1a1a1a" transparent="1" zPosition="2" />

            <eLabel position="200,1015" size="30,30" backgroundColor="green" zPosition="2" />
            <eLabel text="DOWNLOAD"  position="245,1010" size="200,40" font="Regular;30" foregroundColor="#ffffff" backgroundColor="#1a1a1a" transparent="1" zPosition="2" />

            <eLabel position="510,1015" size="30,30" backgroundColor="yellow" zPosition="2" />
            <eLabel text="SETTINGS" position="555,1010" size="200,40" font="Regular;30" foregroundColor="#ffffff" backgroundColor="#1a1a1a" transparent="1" zPosition="2" />

            <eLabel position="755,1015" size="30,30" backgroundColor="blue" zPosition="2" />
            <eLabel text="LOGVIEWER" position="795,1010" size="200,40" font="Regular;30" foregroundColor="#ffffff" backgroundColor="#1a1a1a" transparent="1" zPosition="2" />

            <eLabel position="1000,1015" size="30,30" backgroundColor="#FF8C00" zPosition="2" />
            <eLabel text="MENU:RELOAD" position="1045,1010" size="300,40" font="Regular;30" foregroundColor="#ffffff" backgroundColor="#1a1a1a" transparent="1" zPosition="2" />
        </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.setTitle(":: WebCamE2 Satelitski Forum - Prenj Ciefp ::")
        
        self["logo"] = Pixmap()
        self.menu_list = []
        self.display_list = []
        self.playlist = []
        self["camera_list"] = MenuList(self.menu_list)
        self["status"] = Label("Click GREEN:DOWNLOAD to download and install")
        self["version"] = Label("")
        self.webcam_mode = True
        self.bouquet_version = ""
        
        self["actions"] = ActionMap(["OkCancelActions", "SetupActions", "ColorActions", "MenuActions"],
        {
            "ok": self.okClicked,
            "cancel": self.close,
            "red": self.close,
            "green": self.download_and_install,
            "yellow": self.openSettings,
            "blue": self.openLogViewer,
            "menu": self.reload_from_local,
            "down": self["camera_list"].down,
            "up": self["camera_list"].up
        }, -1)
        
        self.onLayoutFinish.append(self.set_logo)
        self.onLayoutFinish.append(self.fetch_version_info)
        self.onLayoutFinish.append(self.load_playlist)

    def openLogViewer(self):
        self.session.open(LogViewerScreen, BROKEN_LINKS_LOG)

    def reload_from_local(self):
        try:
            bouquet_path = "/etc/enigma2/userbouquet.web_cam____prenj___.tv"
            if not os.path.exists(bouquet_path):
                self.session.open(MessageBox,
                                  "Bouquet file not found!\n\nPlease download first using GREEN button.",
                                  MessageBox.TYPE_ERROR, timeout=5)
                return

            try:
                with open(bouquet_path, "r", encoding="utf-8", errors="ignore") as f:
                    first_line = f.readline().strip()
                if first_line.startswith("#NAME"):
                    local_version = first_line[6:].strip()
                else:
                    local_version = "Unknown"
            except:
                local_version = "Unknown"

            self.load_playlist()

            self.bouquet_version = local_version
            self["version"].setText(local_version)

            self.session.open(MessageBox,
                              "Local bouquet reloaded successfully!\n\n"
                              "Version: {}\n"
                              "Cameras: {}\n"
                              "Categories: {}".format(
                                  local_version,
                                  len(self.playlist),
                                  len([x for x in self.display_list if x.get('is_marker', False)])
                              ),
                              MessageBox.TYPE_INFO, timeout=5)

            self["status"].setText("Reloaded from local file - Version: {}".format(local_version))

        except Exception as e:
            print("[WebCamE2PrenjSF] Reload local error: {}".format(e))
            self.session.open(MessageBox,
                              "Error reloading local bouquet:\n{}".format(str(e)),
                              MessageBox.TYPE_ERROR, timeout=5)

    def load_playlist(self):
        try:
            bouquet_path = "/etc/enigma2/userbouquet.web_cam____prenj___.tv"
            if not os.path.exists(bouquet_path):
                self["status"].setText("Bouquet file not found. Click GREEN to download.")
                return

            self.playlist = []
            self.display_list = []
            self.menu_list = []

            with open(bouquet_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = [line.strip() for line in f.readlines()]

            current_category = ""
            i = 0
            while i < len(lines):
                line = lines[i]

                if not line:
                    i += 1
                    continue

                if line.startswith("#SERVICE 1:64:") or "===" in line:
                    if i + 1 < len(lines) and lines[i + 1].startswith("#DESCRIPTION"):
                        current_category = lines[i + 1].replace("#DESCRIPTION", "").strip()
                        i += 1
                    elif "===" in line:
                        parts = line.split("===")
                        if len(parts) > 1:
                            current_category = parts[1].strip()

                    if current_category:
                        self.display_list.append({
                            "is_marker": True,
                            "name": current_category,
                            "category": current_category
                        })
                        self.menu_list.append(current_category)

                    i += 1
                    continue

                if line.startswith("#SERVICE 4097:") or line.startswith("#SERVICE 5002:"):
                    servicetype = 4097 if line.startswith("#SERVICE 4097:") else 5002
                    is_youtube = False
                    is_streamlink = False
                    url = ""
                    name = ""

                    prefix_len = 15
                    raw_content = line[prefix_len:].strip()

                    parts = raw_content.split(':', 9)
                    if len(parts) == 10:
                        payload = parts[9]
                    else:
                        payload = raw_content

                    if "http" in payload and ":" in payload:
                        url_and_name = payload.split(':', 1)
                        if payload.startswith("http%3a//") or payload.startswith("https%3a//") or payload.startswith("http://") or payload.startswith("https://") or payload.startswith("streamlink%3a//") or payload.startswith("streamlink://"):
                            clean_payload = payload.replace("%3a", ":").replace("%3A", ":")
                            p_parts = clean_payload.split(":")
                            if len(p_parts) > 3 and not p_parts[-1].startswith("//"):
                                name = p_parts[-1].strip()
                                raw_url = ":".join(p_parts[:-1])
                            else:
                                raw_url = payload
                        else:
                            raw_url = payload
                    else:
                        raw_url = payload

                    if 'streamlink%3a//' in raw_url.lower() or 'streamlink://' in raw_url.lower():
                        is_streamlink = True
                        for prefix in ['streamlink%3a//', 'streamlink://', 'STREAMLINK%3A//', 'STREAMLINK://']:
                            if prefix in raw_url:
                                raw_url = raw_url.split(prefix)[-1]
                                break

                    if 'YT-DLP%3a//' in raw_url or 'YT-DLP://' in raw_url or 'YT-DLP%3A//' in raw_url:
                        is_youtube = True
                        for prefix in ['YT-DLP%3a//', 'YT-DLP://', 'YT-DLP%3A//']:
                            if prefix in raw_url:
                                raw_url = raw_url.split(prefix)[-1]
                                break

                    try:
                        from urllib.parse import unquote
                        url = unquote(raw_url)
                    except:
                        url = raw_url.replace("%3a", ":").replace("%3A", ":").replace("%2f", "/").replace("%2F", "/")

                    if not is_youtube and is_youtube_url(url):
                        is_youtube = True

                    if not name and i + 1 < len(lines) and lines[i + 1].startswith("#DESCRIPTION"):
                        name = lines[i + 1].replace("#DESCRIPTION", "").strip()
                        try:
                            from urllib.parse import unquote
                            name = unquote(name)
                        except:
                            pass
                        i += 1

                    if not name:
                        name = url.split('/')[-1].replace('.m3u8', '').replace('.ts', '')
                        if '?' in name:
                            name = name.split('?')[0]

                    if len(name) > 80:
                        name = name[:77] + "..."

                    if url:
                        item_data = {
                            "is_marker": False,
                            "name": name,
                            "url": url,
                            "title": name,
                            "category": current_category,
                            "servicetype": servicetype,
                            "is_youtube": is_youtube,
                            "is_streamlink": is_streamlink
                        }
                        self.display_list.append(item_data)
                        self.menu_list.append(name)
                        self.playlist.append(item_data)

                i += 1

            self["camera_list"].setList(self.menu_list)
            self["status"].setText("Loaded {} cameras. Press OK to play.".format(len(self.playlist)))

        except Exception as e:
            print("[WebCamE2PrenjSF] Error loading playlist: {}".format(e))
            self["status"].setText("Error loading playlist: {}".format(str(e)))

    def okClicked(self):
        if not self.playlist:
            self["status"].setText("No cameras in playlist. Click GREEN to download.")
            return
            
        current_idx = self["camera_list"].getSelectedIndex()
        if current_idx is None or current_idx < 0:
            current_idx = 0
            
        if current_idx < len(self.display_list) and self.display_list[current_idx].get('is_marker', False):
            self["status"].setText("Category selected. Please select a camera.")
            return
        
        selected_item = self.display_list[current_idx]
        if selected_item.get('is_marker', False):
            return
            
        choices = [
            ("Play this camera only", "single"),
            ("Play all cameras in sequence (WebCam Mode)", "playlist"),
            ("Play from here (WebCam Mode)", "playlist_from_here")
        ]
        self.session.openWithCallback(self.choiceCallback, ChoiceBox,
                                      title="Select playback mode:", list=choices)

    def choiceCallback(self, answer):
        if not answer:
            return

        mode = answer[1]
        current_idx = self["camera_list"].getSelectedIndex()

        def openPlayerPostponed():
            if mode == "single":
                if current_idx is not None and current_idx < len(self.display_list):
                    item = self.display_list[current_idx]
                    if not item.get('is_marker', False):
                        single_playlist = [{
                            "url": item.get('url'),
                            "title": item.get('title'),
                            "servicetype": item.get('servicetype', 4097),
                            "is_youtube": item.get('is_youtube', False),
                            "is_streamlink": item.get('is_streamlink', False)
                        }]
                        self.session.open(CiefpWebcamPlaylistPlayer, single_playlist, 0, self.bouquet_version)

            elif mode == "playlist":
                if self.playlist:
                    self.session.open(CiefpWebcamPlaylistPlayer, self.playlist, 0, self.bouquet_version)

            elif mode == "playlist_from_here":
                if current_idx is not None and current_idx < len(self.display_list):
                    item = self.display_list[current_idx]
                    if not item.get('is_marker', False):
                        target_url = item.get('url', '')
                        start_index = 0
                        for i, cam in enumerate(self.playlist):
                            if cam.get('url') == target_url:
                                start_index = i
                                break
                        self.session.open(CiefpWebcamPlaylistPlayer, self.playlist, start_index, self.bouquet_version)

        from enigma import eTimer
        self.postpone_timer = eTimer()
        try:
            self.postpone_timer_conn = self.postpone_timer.timeout.connect(openPlayerPostponed)
        except:
            self.postpone_timer.callback.append(openPlayerPostponed)
        self.postpone_timer.start(150, True)

    def set_logo(self):
        logo_path = PLUGIN_LOGO
        try:
            if not os.path.exists(logo_path):
                self["status"].setText("Logo file not found. Click GREEN to download and install.")
                return
            if not os.access(logo_path, os.R_OK):
                self["status"].setText("Logo file not accessible. Click GREEN to download and install.")
                return
            if self["logo"].instance:
                self["logo"].instance.setPixmapFromFile(logo_path)
            else:
                self["status"].setText("Logo widget not initialized. Click GREEN to download and install.")
        except Exception as e:
            self["status"].setText("Error loading logo: {}. Click GREEN to download and install.".format(to_unicode(str(e))))
    
    def fetch_version_info(self):
        try:
            url = "https://raw.githubusercontent.com/prenj-prog/webcam/refs/heads/main/userbouquet.web_cam____prenj___.tv"
            response = urlopen(url, timeout=10)
            first_line = response.readline()
            try:
                first_line = first_line.decode('utf-8').strip()
            except UnicodeDecodeError:
                first_line = first_line.decode('ascii', errors='ignore').strip()
            if first_line.startswith("#NAME"):
                version_text = first_line[6:].strip()
                self.bouquet_version = version_text
                self["version"].setText(version_text)
            else:
                self["version"].setText("Version info not available")
        except Exception as e:
            self["version"].setText("Failed to fetch version: {}".format(to_unicode(str(e))))

    def download_and_install(self):
        try:
            url = "https://raw.githubusercontent.com/prenj-prog/webcam/refs/heads/main/userbouquet.web_cam____prenj___.tv"
            response = urlopen(url, timeout=10)
            bouquet_data = response.read()
            
            new_version = ""
            first_line = bouquet_data.split(b'\n')[0]
            try:
                first_line = first_line.decode('utf-8').strip()
            except UnicodeDecodeError:
                first_line = first_line.decode('ascii', errors='ignore').strip()
            if first_line.startswith("#NAME"):
                new_version = first_line[6:].strip()
            
            bouquet_path = "/etc/enigma2/userbouquet.web_cam____prenj___.tv"
            if os.path.exists(bouquet_path):
                try:
                    with open(bouquet_path, "rb") as f:
                        existing_first_line = f.readline().decode('utf-8').strip()
                    existing_version = existing_first_line[6:].strip() if existing_first_line.startswith("#NAME") else ""
                    if existing_version == new_version:
                        self.session.open(MessageBox, 
                            "Bouquet file is already up-to-date (version: {}).".format(new_version), 
                            MessageBox.TYPE_INFO, timeout=5)
                        return
                except Exception as e:
                    print("[WebCamE2PrenjSF] Error reading existing file: {}".format(str(e)))
            
            with open(bouquet_path, "wb") as f:
                f.write(bouquet_data)
            print("[WebCamE2PrenjSF] File saved to: {}".format(bouquet_path))
            
            self.register_bouquet()
            
            self.session.openWithCallback(self.confirm_reload, MessageBox, 
                "File successfully saved (version: {}). Do you want to reload settings now?".format(new_version or "unknown"), 
                MessageBox.TYPE_YESNO, default=True, timeout=10)
                
        except Exception as e:
            print("[WebCamE2PrenjSF] Download error: {}".format(str(e)))
            self.session.open(MessageBox, "Download failed: {}".format(to_unicode(str(e))), 
                            MessageBox.TYPE_ERROR, timeout=5)

    def register_bouquet(self):
        bouquet_file = "/etc/enigma2/bouquets.tv"
        bouquet_entry = '#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.web_cam____prenj___.tv" ORDER BY bouquet\n'
        
        try:
            if os.path.exists(bouquet_file):
                with open(bouquet_file, "r") as f:
                    content = f.read()
                if bouquet_entry not in content:
                    with open(bouquet_file, "a") as f:
                        f.write(bouquet_entry)
            else:
                with open(bouquet_file, "w") as f:
                    f.write(bouquet_entry)
            print("[WebCamE2PrenjSF] Bouquet registered in: {}".format(bouquet_file))
        except Exception as e:
            print("[WebCamE2PrenjSF] Error registering bouquet: {}".format(str(e)))

    def confirm_reload(self, answer):
        if answer:
            self.reload_settings()

    def reload_settings(self):
        try:
            eDVBDB.getInstance().reloadServicelist()
            eDVBDB.getInstance().reloadBouquets()
            self.session.open(MessageBox, "Reload successful! New settings are now active. WebCamE2-PrenjSF", 
                            MessageBox.TYPE_INFO, timeout=5)
            self.load_playlist()
        except Exception as e:
            print("[WebCamE2PrenjSF] Reload error: {}".format(str(e)))
            self.session.open(MessageBox, "Reload failed: {}".format(to_unicode(str(e))),
                            MessageBox.TYPE_ERROR, timeout=5)

    def openSettings(self):
        self.session.open(WebCamE2PrenjSFSettings)


class WebCamE2PrenjSFSettings(Screen, ConfigListScreen):
    skin = """
        <screen position="center,center" size="1920,1080" backgroundColor="#011a2e">
            <widget name="separator0" position="0,5" size="1920,3" backgroundColor="#d5fa02" zPosition="1" />  
            <widget name="plugin_title" position="0,10" size="1920,60" font="Bold;30" halign="center" backgroundColor="#012e01" foregroundColor="#FFFFFF" text="..:: WebcamE2 Settings ::.." />
            <widget name="separator1" position="0,75" size="1920,3" backgroundColor="#d5fa02" zPosition="1" /> 

            <widget name="config" position="200,90" size="1400,820" font="Regular;26" itemHeight="45" scrollbarMode="showOnDemand" backgroundColor="#012e01"/>

            <widget name="separator2" position="0,927" size="1920,3" backgroundColor="#d5fa02" zPosition="1" /> 
            <eLabel position="0,930" size="1920,70" backgroundColor="#1a1a1a" zPosition="1" />
            <eLabel position="30,945" size="30,30" backgroundColor="red" zPosition="2" />
            <eLabel text="Exit" position="70,940" size="100,40" font="Regular;26" foregroundColor="#ffffff" backgroundColor="#00000000" transparent="1" zPosition="2" />
            <eLabel position="250,945" size="30,30" backgroundColor="green" zPosition="2" />
            <eLabel text="Save" position="290,940" size="100,40" font="Regular;26" foregroundColor="#ffffff" backgroundColor="#00000000" transparent="1" zPosition="2" />
            <widget name="separator3" position="0,1000" size="1920,3" backgroundColor="#d5fa02" zPosition="1" /> 
        </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.settings = load_settings()

        self.list = []
        self.setup_config()

        self.list.append(getConfigListEntry("Video Quality:", self.quality_entry))
        self.list.append(getConfigListEntry("Mini Skin Opacity:", self.mini_opacity_entry))
        self.list.append(getConfigListEntry("Media Player Type:", self.player_entry))
        self.list.append(getConfigListEntry("Webcam Auto-Switch Timeout:", self.webcam_timeout_entry))
        self.list.append(getConfigListEntry("YouTube Timeout Mode:", self.youtube_timeout_mode_entry))
        self.list.append(getConfigListEntry("YouTube Min Timeout:", self.youtube_timeout_min_entry))
        self.list.append(getConfigListEntry("YouTube Max Timeout:", self.youtube_timeout_max_entry))
        self.list.append(getConfigListEntry("YouTube Step Size:", self.youtube_timeout_step_entry))

        ConfigListScreen.__init__(self, self.list, session=self.session, on_change=self.changedEntry)

        self["separator0"] = Label()
        self["separator1"] = Label()
        self["separator2"] = Label()
        self["separator3"] = Label()
        self["plugin_title"] = Label("..:: WebCamE2PrenjSF ::..")

        self["actions"] = ActionMap(["SetupActions", "ColorActions"],
                                    {
                                        "cancel": self.cancel,
                                        "red": self.cancel,
                                        "green": self.save,
                                        "ok": self.save
                                    }, -1)

    def setup_config(self):
        self.quality_choices = [
            ("best", "Best Available (4K/8K)"),
            ("2160", "4K UHD (2160p)"),
            ("1080", "Full HD (1080p)"),
            ("720", "HD Ready (720p)")
        ]

        self.mini_opacity_choices = [
            ("100", "100%"), ("90", "90%"), ("80", "80%"), ("70", "70%"),
            ("60", "60%"), ("50", "50% (Default)"), ("40", "40%"),
            ("30", "30%"), ("20", "20%"), ("10", "10%"), ("0", "0%")
        ]

        self.player_choices = [
            ("4097", "GStreamer Media Player (Recommended)"),
            ("5002", "DVB Player (Original)"),
            ("5001", "Exteplayer3 (if installed ServiceApp)"),
            ("movieplayer", "MoviePlayer (Single play only)"),
        ]

        self.webcam_timeout_choices = [
            ("15", "15 seconds"),
            ("20", "20 seconds"),
            ("25", "25 seconds"),
            ("30", "30 seconds"),
            ("40", "40 seconds"),
            ("50", "50 seconds"),
            ("60", "60 seconds"),
            ("70", "70 seconds"),
            ("80", "80 seconds"),
            ("90", "90 seconds"),
        ]

        self.quality_entry = ConfigSelection(
            choices=self.quality_choices,
            default=self.settings.get('quality', '1080')
        )

        self.mini_opacity_entry = ConfigSelection(
            choices=self.mini_opacity_choices,
            default=self.settings.get('mini_skin_opacity', '50')
        )

        self.player_entry = ConfigSelection(
            choices=self.player_choices,
            default=self.settings.get('player_type', '4097')
        )

        self.webcam_timeout_entry = ConfigSelection(
            choices=self.webcam_timeout_choices,
            default=str(self.settings.get('webcam_timeout', 20))
        )

        self.youtube_timeout_mode_choices = [
            ("fixed", "Fixed timeout (same for all)"),
            ("variable", "Variable timeout (YouTube only)")
        ]

        self.youtube_timeout_min_choices = [
            ("10", "10 seconds"), ("15", "15 seconds"), ("20", "20 seconds"),
            ("25", "25 seconds"), ("30", "30 seconds"), ("35", "35 seconds")
        ]

        self.youtube_timeout_max_choices = [
            ("20", "20 seconds"), ("25", "25 seconds"), ("30", "30 seconds"),
            ("35", "35 seconds"), ("40", "40 seconds"), ("45", "45 seconds"),
            ("50", "50 seconds"), ("60", "60 seconds")
        ]

        self.youtube_timeout_step_choices = [
            ("5", "5 seconds"), ("10", "10 seconds"), ("15", "15 seconds")
        ]

        self.youtube_timeout_mode_entry = ConfigSelection(
            choices=self.youtube_timeout_mode_choices,
            default=self.settings.get('youtube_timeout_mode', 'fixed')
        )

        self.youtube_timeout_min_entry = ConfigSelection(
            choices=self.youtube_timeout_min_choices,
            default=str(self.settings.get('youtube_timeout_min', 15))
        )

        self.youtube_timeout_max_entry = ConfigSelection(
            choices=self.youtube_timeout_max_choices,
            default=str(self.settings.get('youtube_timeout_max', 30))
        )

        self.youtube_timeout_step_entry = ConfigSelection(
            choices=self.youtube_timeout_step_choices,
            default=str(self.settings.get('youtube_timeout_step', 5))
        )

    def changedEntry(self):
        pass

    def save(self):
        try:
            self.settings['quality'] = self.quality_entry.value
            self.settings['mini_skin_opacity'] = self.mini_opacity_entry.value
            self.settings['player_type'] = self.player_entry.value
            self.settings['webcam_timeout'] = int(self.webcam_timeout_entry.value)
            self.settings['youtube_timeout_mode'] = self.youtube_timeout_mode_entry.value
            self.settings['youtube_timeout_min'] = int(self.youtube_timeout_min_entry.value)
            self.settings['youtube_timeout_max'] = int(self.youtube_timeout_max_entry.value)
            self.settings['youtube_timeout_step'] = int(self.youtube_timeout_step_entry.value)

            if save_settings(self.settings):
                self.session.open(MessageBox, "Settings saved successfully!", MessageBox.TYPE_INFO, timeout=3)
                self.close()
            else:
                self.session.open(MessageBox, "Error saving settings!", MessageBox.TYPE_ERROR, timeout=5)
        except Exception as e:
            print("[WebCamE2PrenjSFSettings] Save error: {}".format(e))
            self.session.open(MessageBox, "Error saving settings: {}".format(str(e)), MessageBox.TYPE_ERROR, timeout=5)

    def cancel(self):
        self.close()


class CiefpWebcamPlaylistPlayer(Screen):
    def __init__(self, session, playlist, start_index=0, bouquet_version=""):
        self.is_closed = False
        self.session = session
        self.playlist = playlist
        self.index = start_index
        self.bouquet_version = bouquet_version
        self.is_paused = False
        self.is_loading = False
        self.pending_next_title = ""
        self.is_single_play = len(playlist) == 1
        self.auto_switch_timer = None
        self.countdown_timer = None
        self.movie_player_timer = None

        try:
            self.webcam_timeout = get_webcam_timeout()
        except:
            self.webcam_timeout = 30

        alpha_hex = get_mini_skin_opacity()
        self.skin = """
        <screen position="center,0" size="1920,160" title="WebCam Player" backgroundColor="#ff000000" flags="wfNoBorder">
            <eLabel position="0,0" size="1920,160" backgroundColor="#{}00000e" zPosition="1" />
            <eLabel text="NOW PLAYING:" position="50,20" size="180,40" font="Regular;22" foregroundColor="#ffffff" backgroundColor="#00000000" transparent="1" zPosition="2" />
            <widget name="title" position="260,15" size="1630,50" font="Regular;30" foregroundColor="#ffffff" backgroundColor="#{}00000e" transparent="1" zPosition="2" />
            <eLabel text="NEXT:" position="50,75" size="180,40" font="Regular;20" foregroundColor="#ffffff" backgroundColor="#00000000" transparent="1" zPosition="2" />
            <widget name="next_title" position="260,72" size="1200,40" font="Regular;24" foregroundColor="#ffcc00" backgroundColor="#{}00000e" transparent="1" zPosition="2" />
            <widget name="playlist_info" position="50,120" size="300,30" font="Regular;22" foregroundColor="#00ffcc" backgroundColor="transparent" transparent="1" zPosition="2" />
            <widget name="bouquet_version" position="900,20" size="1000,30" font="Regular;24" halign="right" foregroundColor="#ffffff" backgroundColor="transparent" transparent="1" zPosition="2" />
            <widget name="status" position="900,120" size="500,30" font="Regular;22" halign="right" foregroundColor="#ffcc00" backgroundColor="transparent" transparent="1" zPosition="2" />    
            <widget name="controls" position="260,120" size="700,30" font="Regular;22" foregroundColor="#03fc1c" backgroundColor="#{}00000e" transparent="1" zPosition="2" />
            <widget name="time" position="1600,110" size="300,50" font="Regular;36" halign="right" foregroundColor="#ffffff" backgroundColor="transparent" transparent="1" zPosition="2"/>
        </screen>
        """.format(alpha_hex, alpha_hex, alpha_hex, alpha_hex)

        Screen.__init__(self, session)

        self["title"] = Label("Loading...")
        self["next_title"] = Label("")
        self["status"] = Label("")
        self["playlist_info"] = Label("")

        if self.is_single_play:
            self["controls"] = Label("Single play mode | EXIT: Exit")
        else:
            self["controls"] = Label(
                "WEBCAM | Auto-switch: {}s | OK: Pause | Up/Down: Skip | EXIT: Exit".format(self.webcam_timeout))

        self["time"] = Label("")
        version_text = bouquet_version[:100] if len(bouquet_version) > 100 else bouquet_version
        self["bouquet_version"] = Label(version_text)

        self["actions"] = ActionMap(["SetupActions", "DirectionActions"], {
            "cancel": self.handleExit,
            "ok": self.pauseToggle,
            "down": self.nextVideo,
            "up": self.prevVideo
        }, -1)

        self.time_timer = eTimer()
        self.time_timer.callback.append(self.updateTime)
        self.time_timer.start(1000)
        self.current_youtube_timeout = 15
        self.youtube_timeout_mode = get_youtube_timeout_mode()
        self.youtube_timeout_min = get_youtube_timeout_min()
        self.youtube_timeout_max = get_youtube_timeout_max()
        self.youtube_timeout_step = get_youtube_timeout_step()

        self.onLayoutFinish.append(self.startExtraction)

    def updateTime(self):
        if getattr(self, 'is_closed', True):
            return
        try:
            import time
            self["time"].setText(time.strftime("%H:%M:%S"))
        except:
            pass

    def startExtraction(self):
        if getattr(self, 'is_closed', True):
            return

        if self.auto_switch_timer:
            self.auto_switch_timer.stop()
        if self.countdown_timer:
            self.countdown_timer.stop()

        if self.index >= len(self.playlist):
            self.handleExit()
            return

        current_video = self.playlist[self.index]
        url = current_video.get('url')
        title = current_video.get('title', 'Camera')
        servicetype = current_video.get('servicetype', 4097)
        is_youtube = current_video.get('is_youtube', False)
        is_streamlink = current_video.get('is_streamlink', False)

        try:
            self["title"].setText("Loading: {}...".format(title))
            self["status"].setText("Loading stream...")
        except:
            pass

        self.is_loading = True

        if self.index + 1 < len(self.playlist):
            self.pending_next_title = self.playlist[self.index + 1].get('title', '')
        else:
            self.pending_next_title = "End of playlist"

        try:
            self["playlist_info"].setText("Camera: {} of {}".format(self.index + 1, len(self.playlist)))
        except:
            pass

        player_type = get_player_type()

        # MoviePlayer radionica za single play
        if self.is_single_play and player_type == "movieplayer":
            print("[WebcamPlayer] Single play with MoviePlayer")
            if is_streamlink:
                threading.Thread(target=self.extractStreamlinkStream, args=(url, title, True), daemon=True).start()
            elif is_youtube:
                threading.Thread(target=self.extractYouTubeForMoviePlayer, args=(url, title), daemon=True).start()
            else:
                self.movie_player_timer = eTimer()
                self.movie_player_timer.callback.append(lambda: self.playWithMoviePlayer(url, title))
                self.movie_player_timer.start(200, True)
            return

        # STREAMLINK stream
        if is_streamlink:
            print("[WebcamPlayer] Streamlink stream detected: {}".format(title))
            threading.Thread(target=self.extractStreamlinkStream, args=(url, title, False), daemon=True).start()
        # YOUTUBE stream
        elif is_youtube:
            print("[WebcamPlayer] YouTube stream detected: {}".format(title))
            threading.Thread(target=self.extractYouTubeStream, args=(url, title), daemon=True).start()
        else:
            print("[WebcamPlayer] Direct stream: {}".format(title))
            self.playVideoDirect(url, title, servicetype)

    def extractStreamlinkStream(self, url, title, for_movie_player=False):
        """Ekstrakcija strima pomoću Streamlink alata uz fallback na yt-dlp ako streamlink nedostaje"""
        if getattr(self, 'is_closed', True):
            return

        quality = load_quality_setting()
        sl_quality = get_streamlink_quality(quality)

        print("[WebcamPlayer] Extracting Streamlink: {}".format(title))
        print("[WebcamPlayer] URL: {}".format(url))
        print("[WebcamPlayer] Quality: {}".format(sl_quality))

        try:
            cmd = ['streamlink', '--stream-url', url, sl_quality]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)

            if result.returncode == 0 and result.stdout.strip():
                video_url = result.stdout.strip().split('\n')[0]
                print("[WebcamPlayer] Streamlink extracted successfully")
                from twisted.internet import reactor
                if for_movie_player:
                    reactor.callFromThread(self.playWithMoviePlayer, video_url, title)
                else:
                    reactor.callFromThread(self.playVideoDirect, video_url, title, 5002)
            else:
                print("[WebcamPlayer] Streamlink extraction failed, trying yt-dlp fallback...")
                if is_youtube_url(url):
                    self.extractYouTubeStream(url, title)
                else:
                    from twisted.internet import reactor
                    reactor.callFromThread(self.showError, "Streamlink extraction failed")

        except (OSError, FileNotFoundError) as err:
            print("[WebcamPlayer] Streamlink binary not found on system! Error: {}".format(err))
            if is_youtube_url(url):
                print("[WebcamPlayer] Falling back to yt-dlp for YouTube link...")
                if for_movie_player:
                    self.extractYouTubeForMoviePlayer(url, title)
                else:
                    self.extractYouTubeStream(url, title)
            else:
                from twisted.internet import reactor
                reactor.callFromThread(self.showError, "Streamlink binary not installed")

        except subprocess.TimeoutExpired:
            print("[WebcamPlayer] Streamlink extraction timeout")
            from twisted.internet import reactor
            reactor.callFromThread(self.showError, "Streamlink timeout")
        except Exception as e:
            print("[WebcamPlayer] Streamlink error: {}".format(e))
            log_broken_link(url, title, str(e)[:30])
            from twisted.internet import reactor
            reactor.callFromThread(self.showError, str(e)[:30])

    def extractYouTubeForMoviePlayer(self, url, title):
        if getattr(self, 'is_closed', True):
            return

        quality = load_quality_setting()
        video_format = get_video_format(quality)

        try:
            cmd = ['yt-dlp', '-g', '-f', video_format, '--no-warnings', url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)

            if result.returncode == 0 and result.stdout.strip():
                video_url = result.stdout.strip().split('\n')[0]
                from twisted.internet import reactor
                reactor.callFromThread(self.playWithMoviePlayer, video_url, title)
            else:
                cmd_fallback = ['yt-dlp', '-g', '-f', 'best', '--no-warnings', url]
                result_fallback = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=45)
                if result_fallback.returncode == 0 and result_fallback.stdout.strip():
                    video_url = result_fallback.stdout.strip().split('\n')[0]
                    from twisted.internet import reactor
                    reactor.callFromThread(self.playWithMoviePlayer, video_url, title)
                else:
                    from twisted.internet import reactor
                    reactor.callFromThread(self.showError, "Cannot extract YouTube stream")
        except subprocess.TimeoutExpired:
            from twisted.internet import reactor
            reactor.callFromThread(self.showError, "YouTube extraction timeout")
        except Exception as e:
            log_broken_link(url, title, str(e)[:30])
            from twisted.internet import reactor
            reactor.callFromThread(self.showError, str(e)[:30])

    def playWithMoviePlayer(self, url, title):
        if getattr(self, 'is_closed', True):
            return
        try:
            from Screens.InfoBar import MoviePlayer
            ref = eServiceReference(4097, 0, url)
            ref.setName(title)
            self.session.openWithCallback(self.handleExit, MoviePlayer, ref)
        except Exception as e:
            print("[WebcamPlayer] MoviePlayer error: {}".format(e))
            self.playVideoDirect(url, title, 4097)

    def extractYouTubeStream(self, url, title):
        if getattr(self, 'is_closed', True):
            return

        quality = load_quality_setting()
        video_format = get_video_format(quality)

        try:
            cmd = ['yt-dlp', '-g', '-f', video_format, '--no-warnings', url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)

            if result.returncode == 0 and result.stdout.strip():
                video_url = result.stdout.strip().split('\n')[0]
                from twisted.internet import reactor
                reactor.callFromThread(self.playVideoDirect, video_url, title, 5002)
            else:
                cmd_fallback = ['yt-dlp', '-g', '-f', 'best', '--no-warnings', url]
                result_fallback = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=45)
                if result_fallback.returncode == 0 and result_fallback.stdout.strip():
                    video_url = result_fallback.stdout.strip().split('\n')[0]
                    from twisted.internet import reactor
                    reactor.callFromThread(self.playVideoDirect, video_url, title, 5002)
                else:
                    from twisted.internet import reactor
                    reactor.callFromThread(self.showError, "Cannot extract YouTube stream")
        except subprocess.TimeoutExpired:
            from twisted.internet import reactor
            reactor.callFromThread(self.showError, "YouTube extraction timeout")
        except Exception as e:
            log_broken_link(url, title, str(e)[:30])
            from twisted.internet import reactor
            reactor.callFromThread(self.showError, str(e)[:30])

    def playVideoDirect(self, video_url, title, servicetype=4097):
        if getattr(self, 'is_closed', True):
            return

        try:
            try:
                ref = eServiceReference(servicetype, 0, video_url)
                ref.setName(title)
                self.session.nav.playService(ref)
            except Exception as e1:
                try:
                    ref = eServiceReference(4097, 0, video_url)
                    ref.setName(title)
                    self.session.nav.playService(ref)
                except Exception as e2:
                    try:
                        ref = eServiceReference(5002, 0, video_url)
                        ref.setName(title)
                        self.session.nav.playService(ref)
                    except Exception as e3:
                        log_broken_link(video_url, title, str(e3)[:30])
                        self.showError("Cannot play stream")

            try:
                self["title"].setText(title)
                self["next_title"].setText(self.pending_next_title)
                self["status"].setText("")
            except:
                pass

            self.is_loading = False

            if not self.is_single_play:
                current_video = self.playlist[self.index]
                is_youtube = current_video.get('is_youtube', False)

                if is_youtube and self.youtube_timeout_mode == 'variable':
                    self.generate_youtube_timeout()
                else:
                    self.webcam_timeout = get_webcam_timeout()

                self.start_auto_switch_timer()

        except Exception as e:
            print("[WebcamPlayer] Error: {}".format(e))
            self.is_loading = False
            self.showError(str(e)[:30])

    def start_auto_switch_timer(self):
        if self.is_single_play or getattr(self, 'is_closed', True):
            return

        if self.auto_switch_timer:
            self.auto_switch_timer.stop()
        if self.countdown_timer:
            self.countdown_timer.stop()

        self.countdown = self.webcam_timeout

        current_video = self.playlist[self.index]
        is_youtube = current_video.get('is_youtube', False)

        if is_youtube and self.youtube_timeout_mode == 'variable':
            timeout_label = "VAR: {}s".format(self.webcam_timeout)
        else:
            timeout_label = "{}s".format(self.webcam_timeout)

        try:
            self["controls"].setText(
                "WEBCAM | Auto-switch: {} | OK: Pause | Up/Down: Skip | EXIT: Exit".format(timeout_label))
        except:
            pass

        self.countdown_timer = eTimer()
        self.countdown_timer.callback.append(self.update_countdown)
        self.countdown_timer.start(1000)

        self.auto_switch_timer = eTimer()
        self.auto_switch_timer.callback.append(self.auto_switch_callback)
        self.auto_switch_timer.start(self.webcam_timeout * 1000, True)

    def generate_youtube_timeout(self):
        if self.youtube_timeout_mode == 'variable':
            import random
            steps = int((self.youtube_timeout_max - self.youtube_timeout_min) / self.youtube_timeout_step)
            random_step = random.randint(0, steps)
            self.webcam_timeout = self.youtube_timeout_min + (random_step * self.youtube_timeout_step)
        else:
            self.webcam_timeout = get_webcam_timeout()

    def update_countdown(self):
        if getattr(self, 'is_closed', True) or self.is_paused or self.is_loading or self.is_single_play:
            return
        if self.countdown > 0:
            self.countdown -= 1
            try:
                self["status"].setText("Next camera in: {}s".format(self.countdown))
            except:
                pass
        else:
            if self.countdown_timer:
                self.countdown_timer.stop()

    def auto_switch_callback(self):
        if getattr(self, 'is_closed', True) or self.is_paused or self.is_loading or self.is_single_play:
            return
        self.nextVideo()

    def nextVideo(self):
        if self.is_loading or self.is_single_play or getattr(self, 'is_closed', True):
            return

        if self.auto_switch_timer:
            self.auto_switch_timer.stop()
        if self.countdown_timer:
            self.countdown_timer.stop()
        self.is_paused = False

        if self.index >= len(self.playlist) - 1:
            self.handleExit()
            return

        try:
            self.session.nav.stopService()
        except:
            pass

        self.is_loading = True
        self.index += 1
        self.startExtraction()

    def prevVideo(self):
        if self.is_loading or self.is_single_play or getattr(self, 'is_closed', True):
            return

        if self.auto_switch_timer:
            self.auto_switch_timer.stop()
        if self.countdown_timer:
            self.countdown_timer.stop()
        self.is_paused = False

        try:
            self.session.nav.stopService()
        except:
            pass

        self.is_loading = True
        if self.index > 0:
            self.index -= 1
        else:
            self.index = len(self.playlist) - 1

        self.startExtraction()

    def showError(self, error_msg):
        if getattr(self, 'is_closed', True):
            return

        if hasattr(self, 'playlist') and self.index < len(self.playlist):
            current_video = self.playlist[self.index]
            log_broken_link(
                current_video.get('url', 'unknown'),
                current_video.get('title', 'unknown'),
                error_msg
            )

        try:
            self["status"].setText("Error: {}. Skipping...".format(error_msg))
        except:
            pass

        try:
            self.session.nav.stopService()
        except:
            pass

        self.is_loading = False

        if not self.is_single_play and self.index < len(self.playlist) - 1:
            self.index += 1
            self.startExtraction()
        else:
            self.handleExit()

    def pauseToggle(self):
        if self.is_single_play or getattr(self, 'is_closed', True):
            return

        try:
            service = self.session.nav.getCurrentService()
            if service and hasattr(service, 'pause'):
                service.pause()
                self.is_paused = not self.is_paused
                if self.is_paused:
                    if self.auto_switch_timer:
                        self.auto_switch_timer.stop()
                    if self.countdown_timer:
                        self.countdown_timer.stop()
                    try:
                        self["controls"].setText("WEBCAM PAUSED | OK: Resume | Up/Down: Skip | EXIT: Exit")
                        self["status"].setText("PAUSED")
                    except:
                        pass
                else:
                    self.start_auto_switch_timer()
                    try:
                        self["controls"].setText(
                            "WEBCAM | Auto-switch: {}s | OK: Pause | Up/Down: Skip | EXIT: Exit".format(
                                self.webcam_timeout))
                    except:
                        pass
        except Exception as e:
            print("[WebcamPlayer] Pause error: {}".format(e))

    def handleExit(self):
        if getattr(self, 'is_closed', True):
            return

        self.is_closed = True

        if self.auto_switch_timer:
            self.auto_switch_timer.stop()
            self.auto_switch_timer = None
        if self.countdown_timer:
            self.countdown_timer.stop()
            self.countdown_timer = None
        if self.time_timer:
            self.time_timer.stop()
            self.time_timer = None
        if self.movie_player_timer:
            self.movie_player_timer.stop()
            self.movie_player_timer = None

        try:
            self.session.nav.stopService()
        except:
            pass
        self.close()

def main(session, **kwargs):
    session.open(WebCamE2PrenjSF)

def Plugins(**kwargs):
    icon_path = PLUGIN_ICON
    return PluginDescriptor(
        name=PLUGIN_NAME,
        description="{} ({})".format(PLUGIN_DESC, PLUGIN_VERSION),
        where=PluginDescriptor.WHERE_PLUGINMENU,
        icon=icon_path,
        fnc=main
    )