import request
import os

class OTAUpdater:
    """
    A class to handle Over-the-Air updates for a MicroPython device.
    """
    def __init__(self, repo_url, filenames):
        self.repo_url = repo_url.rstrip('/')
        self.filenames = filenames
        self.current_version = self.get_local_version()

    def get_local_version(self):
        """ Read the local version number from version.txt. """
        try:
            with open('version.txt', 'r') as f:
                return f.read().strip()
        except OSError:
            # If the file doesn't exist, assume version 0
            return "0.0"

    def fetch_latest_version(self):
        """ Fetch the latest version number from the GitHub repo. """
        url = f"{self.repo_url}/version.txt"
        try:
            
            response = request.get(url)
            
            if response.status_code == 200:
                return response.text.strip()
            else:
                print(f"Failed to fetch version info: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"Error fetching version: {e}")
            return None

    def download_and_install_update(self):
        """ Download and install the latest firmware files. """
        print(f"Updating to version {self.latest_version}...")
        
        for filename in self.filenames:
            url = f"{self.repo_url}/{filename}"
            try:
                response = request.get(url)
                if response.status_code == 200:
                    with open(filename, 'w') as f:
                        f.write(response.text)
                    print(f"Updated {filename}")
                else:
                    print(f"Failed to download {filename}: HTTP {response.status_code}")
            except Exception as e:
                print(f"Error downloading {filename}: {e}")
        
        # Finally, update the local version file
        with open('version.txt', 'w') as f:
            f.write(self.latest_version)
            
        print("Update complete! Ready for restart of main program...")
        import machine
        machine.reset() # Reboot to run the new code

    def check_for_updates(self):
        """ Check if a new version is available and perform the update if so. """
        print(f"Local version: {self.current_version}")
        self.latest_version = self.fetch_latest_version()
        
        if self.latest_version and self.latest_version > self.current_version:
            print(f"New version available: {self.latest_version}")
            self.download_and_install_update()
        else:
            print("No new update available.")

