import os
import sys
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.Label import Label
from Components.ActionMap import ActionMap
from enigma import getDesktop, eDVBDB
from Components.Pixmap import Pixmap

# Add plugin directory to sys.path for Python 2 compatibility
plugin_path = os.path.dirname(os.path.abspath(__file__))
if plugin_path not in sys.path:
    sys.path.append(plugin_path)

PLUGIN_VERSION = "1.0"
PLUGIN_NAME = "WebCamE2PrenjSF"
PLUGIN_DESC = "WebCam for userbouquet enigma2 Satelitski Forum @prenj"
PLUGIN_ICON = "/usr/lib/enigma2/python/Plugins/Extensions/WebCamE2PrenjSF/icon.png"
PLUGIN_LOGO = "/usr/lib/enigma2/python/Plugins/Extensions/WebCamE2PrenjSF/logo.png"

# Python 2/3 compatibility for urllib
if sys.version_info[0] >= 3:
    from urllib.request import urlopen
    from urllib.error import URLError, HTTPError
    to_unicode = str
else:
    from urllib2 import urlopen, URLError, HTTPError
    to_unicode = unicode

class WebCamE2PrenjSF(Screen):
    skin = """
    <screen name="WebCamE2PrenjSF" position="center,center" size="1200,700" title=":: WebCamE2 Satelitski Forum - Prenj Ciefp ::">
        <widget name="logo" position="0,0" size="1200,600" zPosition="0" alphatest="on" />
        <widget name="status" position="0,600" size="1200,50" font="Regular;24" halign="center" valign="center" />
        <widget name="version" position="0,650" size="1200,50" font="Regular;24" halign="center" valign="center" />
    </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.setTitle(":: WebCamE2 Satelitski Forum - Prenj Ciefp ::")
        
        # Initialize widgets
        self["logo"] = Pixmap()
        self["status"] = Label("Click OK to download and install")
        self["version"] = Label("")
        
        # Action map for OK and Cancel
        self["actions"] = ActionMap(["OkCancelActions"],
        {
            "ok": self.download_and_install,
            "cancel": self.close
        }, -1)
        
        # Load logo and version info after layout is finished
        self.onLayoutFinish.append(self.set_logo)
        self.onLayoutFinish.append(self.fetch_version_info)
    
    def set_logo(self):
        logo_path = PLUGIN_LOGO
        try:
            if not os.path.exists(logo_path):
                print("[WebCamE2PrenjSF] Logo file not found at:", logo_path)
                self["status"].setText("Logo file not found. Click OK to download and install.")
                return
            if not os.access(logo_path, os.R_OK):
                print("[WebCamE2PrenjSF] Logo file not readable:", logo_path)
                self["status"].setText("Logo file not accessible. Click OK to download and install.")
                return
            if self["logo"].instance:
                self["logo"].instance.setPixmapFromFile(logo_path)
            else:
                print("[WebCamE2PrenjSF] Logo widget instance is None")
                self["status"].setText("Logo widget not initialized. Click OK to download and install.")
        except Exception as e:
            print("[WebCamE2PrenjSF] Error loading logo:", str(e))
            self["status"].setText("Error loading logo: {}. Click OK to download and install.".format(to_unicode(str(e))))
    
    def fetch_version_info(self):
        try:
            url = "https://raw.githubusercontent.com/prenj-prog/webcam/refs/heads/main/userbouquet.web_cam____prenj___.tv"
            print("[WebCamE2PrenjSF] Fetching version from:", url)
            response = urlopen(url, timeout=10)
            # Read first line as bytes
            first_line = response.readline()
            print("[WebCamE2PrenjSF] Raw first line:", first_line)
            # Decode with fallback to ASCII if UTF-8 fails
            try:
                first_line = first_line.decode('utf-8').strip()
            except UnicodeDecodeError:
                first_line = first_line.decode('ascii', errors='ignore').strip()
            print("[WebCamE2PrenjSF] Decoded first line:", first_line)
            if first_line.startswith("#NAME"):
                version_text = first_line[6:].strip()
                # For Python 2, convert unicode to str with UTF-8 encoding
                if sys.version_info[0] < 3 and isinstance(version_text, unicode):
                    version_text = version_text.encode('utf-8')
                self["version"].setText(version_text)
                print("[WebCamE2PrenjSF] Version set to:", version_text)
            else:
                self["version"].setText("Version info not available")
                print("[WebCamE2PrenjSF] First line does not start with #NAME")
        except HTTPError as e:
            error_msg = "HTTP Error {}: {}".format(e.code, e.reason)
            print("[WebCamE2PrenjSF] Error fetching version:", error_msg)
            self["version"].setText("Failed to fetch version: {}".format(to_unicode(error_msg)))
        except URLError as e:
            error_msg = "URL Error: {}".format(str(e.reason))
            print("[WebCamE2PrenjSF] Error fetching version:", error_msg)
            self["version"].setText("Failed to fetch version: {}".format(to_unicode(error_msg)))
        except Exception as e:
            print("[WebCamE2PrenjSF] Error fetching version:", str(e))
            self["version"].setText("Failed to fetch version: {}".format(to_unicode(str(e))))

    def download_and_install(self):
        try:
            # Download the userbouquet file
            url = "https://raw.githubusercontent.com/prenj-prog/webcam/refs/heads/main/userbouquet.web_cam____prenj___.tv"
            response = urlopen(url, timeout=10)
            bouquet_data = response.read()
            
            # Get the version from the downloaded file
            new_version = ""
            first_line = bouquet_data.split(b'\n')[0]
            try:
                first_line = first_line.decode('utf-8').strip()
            except UnicodeDecodeError:
                first_line = first_line.decode('ascii', errors='ignore').strip()
            if first_line.startswith("#NAME"):
                new_version = first_line[6:].strip()
                print("[WebCamE2PrenjSF] Downloaded version:", new_version)
            
            # Check if file exists and compare versions
            bouquet_path = "/etc/enigma2/userbouquet.web_cam____prenj___.tv"
            if os.path.exists(bouquet_path):
                try:
                    with open(bouquet_path, "rb") as f:
                        existing_first_line = f.readline().decode('utf-8').strip()
                    existing_version = existing_first_line[6:].strip() if existing_first_line.startswith("#NAME") else ""
                    print("[WebCamE2PrenjSF] Existing version:", existing_version)
                    if existing_version == new_version:
                        print("[WebCamE2PrenjSF] File is already up-to-date, skipping write.")
                        self.session.open(MessageBox, 
                            "Bouquet file is already up-to-date (version: {}).".format(new_version), 
                            MessageBox.TYPE_INFO, timeout=5)
                        return
                except Exception as e:
                    print("[WebCamE2PrenjSF] Error reading existing file:", str(e))
            
            # Save to /etc/enigma2/
            with open(bouquet_path, "wb") as f:
                f.write(bouquet_data)
            print("[WebCamE2PrenjSF] File saved to:", bouquet_path)
            
            # Register in bouquets.tv
            self.register_bouquet()
            
            # Show success message and prompt for reload
            self.session.openWithCallback(self.confirm_reload, MessageBox, 
                "File successfully saved (version: {}). Do you want to reload settings now?".format(new_version or "unknown"), 
                MessageBox.TYPE_YESNO, default=True, timeout=10)
                
        except Exception as e:
            print("[WebCamE2PrenjSF] Download error:", str(e))
            self.session.open(MessageBox, "Download failed: {}".format(to_unicode(str(e))), 
                            MessageBox.TYPE_ERROR, timeout=5)

    def register_bouquet(self):
        bouquet_file = "/etc/enigma2/bouquets.tv"
        bouquet_entry = '#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.web_cam____prenj___.tv" ORDER BY bouquet\n'
        
        try:
            # Read existing bouquets.tv
            if os.path.exists(bouquet_file):
                with open(bouquet_file, "r") as f:
                    content = f.read()
                
                # Check if entry already exists to avoid duplicates
                if bouquet_entry not in content:
                    with open(bouquet_file, "a") as f:
                        f.write(bouquet_entry)
            else:
                # Create new bouquets.tv if it doesn't exist
                with open(bouquet_file, "w") as f:
                    f.write(bouquet_entry)
            print("[WebCamE2PrenjSF] Bouquet registered in:", bouquet_file)
        except Exception as e:
            print("[WebCamE2PrenjSF] Error registering bouquet:", str(e))
            self.session.open(MessageBox, "Failed to register bouquet: {}".format(to_unicode(str(e))), 
                            MessageBox.TYPE_ERROR, timeout=5)

    def confirm_reload(self, answer):
        if answer:
            self.reload_settings()

    def reload_settings(self):
        try:
            eDVBDB.getInstance().reloadServicelist()
            eDVBDB.getInstance().reloadBouquets()
            self.session.open(MessageBox, "Reload successful! New settings are now active. WebCamE2-PrenjSF", 
                            MessageBox.TYPE_INFO, timeout=5)
        except Exception as e:
            print("[WebCamE2PrenjSF] Reload error:", str(e))
            self.session.open(MessageBox, "Reload failed: {}".format(to_unicode(str(e))), 
                            MessageBox.TYPE_ERROR, timeout=5)

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