import requests
import os
import time
import random

# Anti-Cache-Header für GitHub / Edge-Server
NO_CACHE_HEADERS = {
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0'
}

class OTAUpdater:
    """
    A class to handle Over-the-Air updates for a MicroPython device.
    """
    def __init__(self, repo_url, filenames):
        self.repo_url = repo_url.rstrip('/')
        self.filenames = filenames
        self.current_version = self.get_local_version()

    def _get_nocache_url(self, base_url):
        """ Appends a unique timestamp & random ID to bypass CDN/HTTP caching. """
        cache_buster = f"{time.ticks_ms()}_{random.getrandbits(16)}"
        return f"{base_url}?nocache={cache_buster}"

    def get_local_version(self):
        """ Read the local version number from version.txt. """
        try:
            with open('version.txt', 'r') as f:
                stri = f.read().strip()
                return stri
        except OSError:
            # If the file doesn't exist, assume version 0
            return "0.0"

    def fetch_latest_version(self):
        """ Fetch the latest version number from the GitHub repo without caching. """
        url = self._get_nocache_url(f"{self.repo_url}/version.txt")
        try:
            response = requests.get(url, headers=NO_CACHE_HEADERS)
            if response.status_code == 200:
                version = response.text.strip()
                response.close()  # Socket explizit freigeben!
                return version
            else:
                print(f"Failed to fetch version info: HTTP {response.status_code}")
                response.close()
                return None
        except Exception as e:
            print(f"Error fetching version: {e}")
            return None

    def download_and_install_update(self):
        """ Download and install the latest firmware files without caching. """
        print(f"Updating to version {self.latest_version}...")
        url = self._get_nocache_url(f"{self.repo_url}/files_to_update.txt")
        try:
            response = requests.get(url, headers=NO_CACHE_HEADERS)
            if response.status_code == 200:
                self.filenames = response.text.strip().splitlines()
                response.close()  # Socket explizit freigeben!
                print(self.filenames)
                #return self.filenames
            else:
                print(f"Failed to fetch filenames info: HTTP {response.status_code}")
                response.close()
                return None
        except Exception as e:
            print(f"Error fetching version: {e}")
            return None
        
        #print(len(self.filenames))
        for filename in self.filenames:
            url = self._get_nocache_url(f"{self.repo_url}/{filename}")
            print(url)
            try:
                response = requests.get(url, headers=NO_CACHE_HEADERS)
                if response.status_code == 200:
                    with open(filename, 'w') as f:
                        f.write(response.text)
                    print(f"Updated {filename}")
                else:
                    print(f"Failed to download {filename}: HTTP {response.status_code}")
                response.close()  # Socket explizit freigeben!
            except Exception as e:
                print(f"Error downloading {filename}: {e}")
        
        # Finally, update the local version file
        with open('version.txt', 'w') as f:
            f.write(self.latest_version)
            
        print("Update complete! Ready for restart of main program...")
        # import machine
        # machine.reset() # Reboot to run the new code

    def check_for_updates(self):
        """ Check if a new version is available and perform the update if so. """
        print(f"Local version: {self.current_version}")
        self.latest_version = self.fetch_latest_version()
        
        if self.latest_version and self.latest_version != self.current_version:
            print(f"New version available: {self.latest_version}")
            self.download_and_install_update()
        else:
            print("No new update available.")