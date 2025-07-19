import sys
import re
import requests
import tidalapi
from time import sleep
from datetime import datetime
from tqdm import tqdm
from src.mainfuncs import message, what_to_move, compare
from config.config import tidalfile

def tidal_auth():
   # Attempt to authenticate Tidal
   try:
      tidal = tidalapi.Session()
      try:
         with open(tidalfile, 'r') as file:
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
         with open(tidalfile, 'w') as file:
            file.write('\n'.join(creds))
         return tidal
      else:
         message("t-","Authentication Failed")
         raise TimeoutError()
   except:
      message("t-","Authentication failed")
      sys.exit(0)

def get_tidal_playlists(session):
    """Returns a dictionary of playlist names and their IDs, including those in folders."""
    playlists = {}

    # Get all playlists using the tidalapi library
    user_playlists = session.user.playlists()
    for playlist in user_playlists:
        playlists[playlist.name] = playlist.id

    # Get folders and their playlists using direct API calls
    try:
        headers = {
            'Authorization': f'Bearer {session.access_token}',
            'Accept': 'application/json',
            'User-Agent': 'TIDAL_ANDROID/1039 okhttp/3.13.1'
        }

        # Get playlist folders from Tidal API
        folders_response = requests.get(
            'https://listen.tidal.com/v2/my-collection/playlists/folders',
            headers=headers,
            params={'countryCode': 'US', 'locale': 'en_US', 'deviceType': 'BROWSER'}
        )

        if folders_response.status_code == 200:
            folders_data = folders_response.json()
            for folder in folders_data.get('folders', []):
                folder_name = folder.get('name')
                folder_id = folder.get('id')
                if folder_name and folder_id:
                    # Get playlists in this folder
                    playlists_response = requests.get(
                        f'https://listen.tidal.com/v2/my-collection/playlists/folders/{folder_id}/playlists',
                        headers=headers,
                        params={'countryCode': 'US', 'locale': 'en_US', 'deviceType': 'BROWSER'}
                    )
                    if playlists_response.status_code == 200:
                        playlists_data = playlists_response.json()
                        for playlist_item in playlists_data.get('data', []):
                            playlist_name = playlist_item.get('name')
                            playlist_id = playlist_item.get('uuid')
                            if playlist_name and playlist_id:
                                playlists[f"{folder_name}/{playlist_name}"] = playlist_id
        else:
            print(f"[t!] Could not fetch folders from Tidal API: {folders_response.status_code}")

    except Exception as e:
        print(f"[t!] Note: Could not fetch folder playlists via API: {e}")

    return playlists

def tidal_dest_check(playlists, session, playlist_name):
    """Check if a playlist exists. If not, create it, including in a folder if specified."""
    if playlist_name in playlists:
        return playlists[playlist_name]

    folder_name, new_playlist_name = playlist_name.split('/', 1) if '/' in playlist_name else (None, playlist_name)

    if folder_name:
        # Check if the folder already exists using direct API calls
        try:
            headers = {
                'Authorization': f'Bearer {session.access_token}',
                'Accept': 'application/json',
                'User-Agent': 'TIDAL_ANDROID/1039 okhttp/3.13.1'
            }

            # Get existing folders
            folders_response = requests.get(
                'https://listen.tidal.com/v2/my-collection/playlists/folders',
                headers=headers,
                params={'countryCode': 'US', 'locale': 'en_US', 'deviceType': 'BROWSER'}
            )

            folder_id = None
            if folders_response.status_code == 200:
                folders_data = folders_response.json()
                for folder in folders_data.get('folders', []):
                    if folder.get('name') == folder_name:
                        folder_id = folder.get('id')
                        break

            if folder_id:
                # Folder exists, create playlist in it
                message("t+", f"Creating new playlist: {new_playlist_name} in existing folder {folder_name}")
                # Create playlist using tidalapi
                playlist = session.user.create_playlist(new_playlist_name, '')

                # Try to add playlist to folder using various methods
                try:
                    # First try to get the folder object and use tidalapi methods
                    try:
                        folder_obj = session.folder(folder_id)
                        # Use the correct tidalapi method: add_items
                        folder_obj.add_items([playlist.id])
                        message("t+", f"Successfully added playlist to folder using tidalapi")
                        return playlist.id
                    except Exception as e:
                        message("t!", f"tidalapi method failed: {e}, trying direct API")
                        # Fall through to API methods

                    # Try direct API call with proper headers
                    headers['Content-Type'] = 'application/json'
                    add_to_folder_response = requests.post(
                        f'https://listen.tidal.com/v2/my-collection/playlists/folders/{folder_id}/playlists',
                        headers=headers,
                        params={'countryCode': 'US', 'locale': 'en_US', 'deviceType': 'BROWSER'},
                        json={'playlistUuids': [playlist.id]}
                    )

                    if add_to_folder_response.status_code in [200, 201]:
                        message("t+", f"Successfully added playlist to folder via API")
                    else:
                        message("t!", f"Warning: Created playlist but failed to add to folder: {add_to_folder_response.status_code}")
                except Exception as e:
                    message("t!", f"Warning: Created playlist but failed to add to folder: {e}")

                return playlist.id
            else:
                # Try to create folder using tidalapi
                try:
                    message("t+", f"Creating new folder: {folder_name}")
                    # Create folder using tidalapi
                    folder_obj = session.user.create_folder(title=folder_name)
                    folder_id = folder_obj.id

                    # Create playlist in the new folder
                    message("t+", f"Creating new playlist: {new_playlist_name} in new folder {folder_name}")
                    playlist = session.user.create_playlist(new_playlist_name, '')

                    # Try to add playlist to folder using tidalapi folder methods
                    try:
                        # Use the correct tidalapi method: add_items
                        folder_obj.add_items([playlist.id])
                        message("t+", f"Successfully created folder and added playlist using tidalapi")
                    except Exception as e:
                        message("t!", f"Warning: Created folder and playlist but failed to link them using tidalapi: {e}")
                        # Fallback to direct API calls if tidalapi fails
                        try:
                            headers['Content-Type'] = 'application/json'
                            add_to_folder_response = requests.post(
                                f'https://listen.tidal.com/v2/my-collection/playlists/folders/{folder_id}/playlists',
                                headers=headers,
                                params={'countryCode': 'US', 'locale': 'en_US', 'deviceType': 'BROWSER'},
                                json={'playlistUuids': [playlist.id]}
                            )

                            if add_to_folder_response.status_code in [200, 201]:
                                message("t+", f"Successfully created folder and added playlist via API")
                            else:
                                message("t!", f"Warning: Created folder and playlist but failed to link them via API: {add_to_folder_response.status_code}")
                        except Exception:
                            message("t!", f"Both tidalapi and API methods failed - playlist created in root")

                    return playlist.id
                except Exception as e:
                    # Folder creation failed
                    message("t!", f"Note: Cannot create folder '{folder_name}' using tidalapi ({e}). Creating playlist '{new_playlist_name}' in root.")
                    playlist_name = new_playlist_name

        except Exception as e:
            message("t!", f"Note: Folder operations failed ({e}). Creating playlist '{new_playlist_name}' in root.")
            playlist_name = new_playlist_name

    # Create playlist in root using tidalapi library
    message("t+", f"Creating new playlist: {playlist_name}")
    playlist = session.user.create_playlist(playlist_name, '')
    return playlist.id

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
      artist = ' '.join(artist_name)
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
         i = ' '.join(i.split("&@#72")[1:])
         search = tidal_search_playlist(i, tidal.access_token)
         if len(str(search)) == 408:
            bk = i
            i = re.sub(r"\(.*?\)","",i)
            search = tidal_search_playlist(i, tidal.access_token)
            if len(list(search)) == 408:
               not_found.append(bk)
               continue
         for song in search['tracks']['items']:
            album_name = song['album']['title']
            song_name = song['title']
            artist_name = []
            for j in song['artists']:
               artist = j['name']
               artist_name.append(artist)
            artist = ' '.join(artist_name)
            found = album_name+" "+song_name+" "+artist
            songid = song['id']
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
   tidal_create_playlist_url = 'https://listen.tidal.com/v2/my-collection/playlists/folders/create-playlist?description={}&folderId=root&name={}&countryCode=NG&locale=en_US&deviceType=BROWSER'.format(playlist_desc, playlist_name)
   headers = {'authority': 'listen.tidal.com', 'authorization': 'Bearer {}'.format(access_token), 'origin': 'https://listen.tidal.com', 'referer': 'https://listen.tidal.com/my-collection/playlists'}
   r = requests.put(tidal_create_playlist_url, headers = headers)
   playlist_id = r.json()['data']['uuid']
   return playlist_id

def tidal_search_playlist(search_query, access_token):
   tidal_search_playlist_url = 'https://listen.tidal.com/v1/search/top-hits?query={}&limit=5&offset=0&types=TRACKS&includeContributors=true&countryCode=NG&locale=en_US&deviceType=BROWSER'.format(search_query)
   headers = {'authority': 'listen.tidal.com', 'authorization': 'Bearer {}'.format(access_token), 'origin': 'https://listen.tidal.com', 'referer': 'https://listen.tidal.com/my-collection/playlists'}
   r = requests.get(tidal_search_playlist_url, headers = headers)
   return r.json()

def tidal_add_song_to_playlist(playlist_id, song_id, access_token):
   tidal_get_request = "https://listen.tidal.com/v1/playlists/{}?countryCode=NG&locale=en_US&deviceType=BROWSER".format(playlist_id)
   get_headers = {'Host': 'listen.tidal.com','User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0' ,'Accept':'*/*','Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding':'gzip,deflate','Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors','Sec-Fetch-Site': 'same-origin','authorization': 'Bearer {}'.format(access_token), 'origin': 'https://listen.tidal.com', 'referer': 'https://listen.tidal.com/my-collection/playlists'}
   rasd = requests.get(tidal_get_request, headers=get_headers)
   etag = rasd.headers['Etag']
   tidal_add_song_url = "https://listen.tidal.com/v1/playlists/{}/items?countryCode=NG&locale=en_US&deviceType=BROWSER".format(playlist_id)
   headers = {'authority': 'listen.tidal.com', 'authorization': 'Bearer {}'.format(access_token), 'origin': 'https://listen.tidal.com', 'referer': 'https://listen.tidal.com/playlist/{}'.format(playlist_id),'dnt':'1', 'if-none-match':etag}
   data = {'onArtifactNotFound':'FAIL','onDupes':'FAIL','trackIds':'{}'.format(song_id)}
   r = requests.post(tidal_add_song_url, headers = headers, data=data)
