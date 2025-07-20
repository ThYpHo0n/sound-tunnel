import re
import sys
from datetime import datetime
from time import sleep

import requests
import tidalapi
from tqdm import tqdm

from config.config import tidalfile
from src.mainfuncs import compare, message, what_to_move

# Cache for folders created/found in this session
_session_folders_cache = {}

def tidal_auth():
   # Attempt to authenticate Tidal
   try:
      tidal = tidalapi.Session()
      try:
         with open(tidalfile) as file:
            cred = [line.rstrip() for line in file]
         expiry_time: datetime = datetime.strptime(cred[3], "%m/%d/%Y, %H:%M:%S.%f")
         if expiry_time > datetime.now() and tidal.load_oauth_session(cred[0], cred[1], cred[2], expiry_time):
            message("t+","Successfully Authenticated")
            return tidal
      except:
         pass
      tidal.login_oauth_simple()
      if tidal.check_login():
         message("t+","Successfully Authenticated")
         creds = [tidal.token_type, tidal.access_token, tidal.refresh_token, tidal.expiry_time.strftime("%m/%d/%Y, %H:%M:%S.%f")]
         with open(tidalfile, "w") as file:
            file.write("\n".join(creds))
         return tidal
      message("t-","Authentication Failed")
      raise TimeoutError
   except:
      message("t-","Authentication failed")
      sys.exit(0)

def get_tidal_playlists(session):
    """Returns a dictionary of playlist names and their IDs, including those in folders."""
    user_playlists = session.user.playlists()
    playlists = {}
    for playlist in user_playlists:
        playlists[playlist.name] = playlist.id

    # Try to get playlists from folders using direct API calls (more reliable)
    try:
        headers = {
            "Authorization": f"Bearer {session.access_token}",
            "Accept": "application/json",
            "User-Agent": "TIDAL_ANDROID/1039 okhttp/3.13.1"
        }

        # Get existing folders from API
        folders_response = requests.get(
            "https://listen.tidal.com/v2/my-collection/playlists/folders",
            headers=headers,
            params={"countryCode": "NG", "locale": "en_US", "deviceType": "BROWSER"}
        )

        if folders_response.status_code == 200:
            folders_data = folders_response.json()
            # Look for folders in the items array, not a separate folders array
            items = folders_data.get("items", [])
            folders = [item for item in items if item.get("itemType") == "FOLDER"]

            for folder in folders:
                folder_name = folder.get("name")
                folder_id = folder.get("data", {}).get("id")  # ID is in the data subobject

                # Cache this folder for future use
                if folder_name:
                    try:
                        folder_obj = session.folder(folder_id)
                        _session_folders_cache[folder_name] = folder_obj
                    except Exception:
                        pass

                # Get playlists in this folder
                try:
                    folder_obj = session.folder(folder_id)
                    folder_playlists = folder_obj.items()
                    for item in folder_playlists:
                        if hasattr(item, "name"):  # Check if it's a playlist
                            folder_playlist_key = f"{folder_name}/{item.name}"
                            playlists[folder_playlist_key] = item.id
                except Exception:
                    pass
        else:
            pass
    except Exception:
        pass

    # Fallback: Try using tidalapi library methods
    try:
        user_folders = session.user.folders()
        for folder in user_folders:
            folder_name = folder.name
            # Cache this folder for future use
            _session_folders_cache[folder_name] = folder
    except AttributeError:
        pass
    except Exception:
        pass

    return playlists

def tidal_dest_check(playlists, session, playlist_name, apple_folders=None):
    """Check if a playlist exists. If not, create it, including in a folder if specified."""
    if playlist_name in playlists:
        dest_playlist_id = playlists[playlist_name]
        message("t+", "Playlist exists, adding missing songs")
        return dest_playlist_id

    # Check if this is a folder/playlist structure from Apple Music
    if apple_folders and "/" in playlist_name:
        folder_name, new_playlist_name = playlist_name.split("/", 1)

        # If the folder name exists in Apple Music folders, treat it as folder structure
        if folder_name in apple_folders.values():
            # Check if we already created this folder in this session
            if folder_name in _session_folders_cache:
                folder_obj = _session_folders_cache[folder_name]
                message("t+", f"Creating new playlist: {new_playlist_name}")
                playlist = session.user.create_playlist(new_playlist_name, "")
                message("t+", f"Adding playlist to existing folder: {folder_name} (from session cache)")
                try:
                    folder_obj.add_items([playlist.id])
                    message("t+", "Successfully added playlist to existing folder")
                    # Update the playlists cache
                    playlists[playlist_name] = playlist.id
                    return playlist.id
                except Exception as e:
                    message("t!", f"Failed to add playlist to cached folder: {e}")
                    # Continue to try other methods below

            # Check if the folder already exists using direct API calls
            try:
                headers = {
                    "Authorization": f"Bearer {session.access_token}",
                    "Accept": "application/json",
                    "User-Agent": "TIDAL_ANDROID/1039 okhttp/3.13.1"
                }

                # Get existing folders from API
                folders_response = requests.get(
                    "https://listen.tidal.com/v2/my-collection/playlists/folders",
                    headers=headers,
                    params={"countryCode": "NG", "locale": "en_US", "deviceType": "BROWSER"}
                )

                folder_id = None
                if folders_response.status_code == 200:
                    folders_data = folders_response.json()
                    # Look for folders in the items array, not a separate folders array
                    items = folders_data.get("items", [])
                    folders = [item for item in items if item.get("itemType") == "FOLDER"]
                    for folder in folders:
                        if folder.get("name") == folder_name:
                            folder_id = folder.get("data", {}).get("id")  # ID is in the data subobject
                            message("t+", f"Found existing folder via API: {folder_name}")
                            break

                # Create playlist first
                message("t+", f"Creating new playlist: {new_playlist_name}")
                playlist = session.user.create_playlist(new_playlist_name, "")

                if folder_id:
                    # Folder exists in API, try to use it
                    try:
                        folder_obj = session.folder(folder_id)
                        # Cache this folder for future use
                        _session_folders_cache[folder_name] = folder_obj
                        message("t+", f"Adding playlist to existing folder: {folder_name}")
                        folder_obj.add_items([playlist.id])
                        message("t+", "Successfully added playlist to existing folder")
                        # Update the playlists cache
                        playlists[playlist_name] = playlist.id
                        return playlist.id
                    except Exception as e:
                        message("t!", f"Failed to add playlist to existing folder: {e}")
                        # Continue to create new folder

                # Create new folder and add playlist to it
                message("t+", f"Creating new folder: {folder_name}")
                folder_obj = session.user.create_folder(title=folder_name)
                # Cache this folder for future use
                _session_folders_cache[folder_name] = folder_obj
                folder_obj.add_items([playlist.id])
                message("t+", "Successfully created folder and added playlist")

                # Update the playlists cache
                playlists[playlist_name] = playlist.id
                return playlist.id

            except Exception as e:
                message("t!", f"Warning: Folder operation failed, creating playlist in root: {e}")
                # Fallback to creating in root
                dest_playlist_id = tidal_create_playlist(new_playlist_name, "Sound Tunnel playlist", session.access_token)
                message("t+", "Playlist created in root")
                playlists[playlist_name] = dest_playlist_id
                return dest_playlist_id

    # For playlists not in Apple Music folders, check if it has a slash
    if "/" in playlist_name:
        folder_name, new_playlist_name = playlist_name.split("/", 1)

        # Check if we already created this folder in this session
        if folder_name in _session_folders_cache:
            folder_obj = _session_folders_cache[folder_name]
            message("t+", f"Creating new playlist: {new_playlist_name}")
            playlist = session.user.create_playlist(new_playlist_name, "")
            message("t+", f"Adding playlist to existing folder: {folder_name} (from session cache)")
            try:
                folder_obj.add_items([playlist.id])
                message("t+", "Successfully added playlist to existing folder")
                # Update the playlists cache
                playlists[playlist_name] = playlist.id
                return playlist.id
            except Exception as e:
                message("t!", f"Failed to add playlist to cached folder: {e}")
                # Fall through to create as literal name

    # Otherwise, treat it as a literal playlist name (including any slashes)
    dest_playlist_id = tidal_create_playlist(playlist_name, "Sound Tunnel playlist", session.access_token)
    message("t+", "Playlist created")
    # Update the playlists cache
    playlists[playlist_name] = dest_playlist_id
    return dest_playlist_id

def get_tidal_playlist_content(session, playlist_id):
   playlist = session.playlist(playlist_id)
   playlist_content = playlist.tracks()
   result = []
   for song in playlist_content:
      song_name = song.name
      album_name = song.album.name
      artist_name = []
      for i in song.artists:
         artist = i.name
         artist_name.append(artist)
      artist = " ".join(artist_name)
      result.append(album_name+"&@#72"+song_name+"&@#72"+artist)
   return result

def move_to_tidal(tidal, playlist_info, dest_id, playlist_name):
   not_found = []
   present_song = get_tidal_playlist_content(tidal,dest_id)
   playlist_info = what_to_move(present_song, playlist_info)
   not_found = []
   try:
      for i in tqdm(playlist_info, desc=f"Moving {playlist_name} to Tidal"):
         op = i.replace("&@#72", " ")
         i = " ".join(i.split("&@#72")[1:])
         search = tidal_search_playlist(i, tidal.access_token)
         if len(str(search)) == 408:
            bk = i
            i = re.sub(r"\(.*?\)","",i)
            search = tidal_search_playlist(i, tidal.access_token)
            if len(list(search)) == 408:
               not_found.append(bk)
               continue
         for song in search["tracks"]["items"]:
            album_name = song["album"]["title"]
            song_name = song["title"]
            artist_name = []
            for j in song["artists"]:
               artist = j["name"]
               artist_name.append(artist)
            artist = " ".join(artist_name)
            found = album_name+" "+song_name+" "+artist
            songid = song["id"]
            if compare(found, op):
               sleep(0.5)
               tidal_add_song_to_playlist(dest_id, songid, tidal.access_token)
               break
         else:
            not_found.append(i)
      return not_found
   except KeyboardInterrupt:
      print("\n[!] Operation cancelled by user.")
      sys.exit(0)
   except Exception:
      return not_found



def tidal_create_playlist(playlist_name, playlist_desc, access_token):
   tidal_create_playlist_url = f"https://listen.tidal.com/v2/my-collection/playlists/folders/create-playlist?description={playlist_desc}&folderId=root&name={playlist_name}&countryCode=NG&locale=en_US&deviceType=BROWSER"
   headers = {"authority": "listen.tidal.com", "authorization": f"Bearer {access_token}", "origin": "https://listen.tidal.com", "referer": "https://listen.tidal.com/my-collection/playlists"}
   r = requests.put(tidal_create_playlist_url, headers = headers)
   playlist_id = r.json()["data"]["uuid"]
   return playlist_id

def tidal_search_playlist(search_query, access_token):
   tidal_search_playlist_url = f"https://listen.tidal.com/v1/search/top-hits?query={search_query}&limit=5&offset=0&types=TRACKS&includeContributors=true&countryCode=NG&locale=en_US&deviceType=BROWSER"
   headers = {"authority": "listen.tidal.com", "authorization": f"Bearer {access_token}", "origin": "https://listen.tidal.com", "referer": "https://listen.tidal.com/my-collection/playlists"}
   r = requests.get(tidal_search_playlist_url, headers = headers)
   return r.json()

def tidal_add_song_to_playlist(playlist_id, song_id, access_token):
   tidal_get_request = f"https://listen.tidal.com/v1/playlists/{playlist_id}?countryCode=NG&locale=en_US&deviceType=BROWSER"
   get_headers = {"Host": "listen.tidal.com","User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0" ,"Accept":"*/*","Accept-Language": "en-US,en;q=0.5", "Accept-Encoding":"gzip,deflate","Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors","Sec-Fetch-Site": "same-origin","authorization": f"Bearer {access_token}", "origin": "https://listen.tidal.com", "referer": "https://listen.tidal.com/my-collection/playlists"}
   rasd = requests.get(tidal_get_request, headers=get_headers)
   etag = rasd.headers["Etag"]
   tidal_add_song_url = f"https://listen.tidal.com/v1/playlists/{playlist_id}/items?countryCode=NG&locale=en_US&deviceType=BROWSER"
   headers = {"authority": "listen.tidal.com", "authorization": f"Bearer {access_token}", "origin": "https://listen.tidal.com", "referer": f"https://listen.tidal.com/playlist/{playlist_id}","dnt":"1", "if-none-match":etag}
   data = {"onArtifactNotFound":"FAIL","onDupes":"FAIL","trackIds":f"{song_id}"}
   r = requests.post(tidal_add_song_url, headers = headers, data=data)
