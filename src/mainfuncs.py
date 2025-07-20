import json
from difflib import SequenceMatcher


def message(bit, msg):
   code = bit[1]
   plat = bit[0]
   output = f"[{code}] "
   if plat.lower() == "s":
      output = output + "Spotify: "
   elif plat.lower() == "y":
      output = output + "Youtube: "
   elif plat.lower() == "t":
      output = output + "Tidal: "
   elif plat.lower() == "a":
      output = output + "Apple: "
   output = output + msg
   print(output)

def display_playlists(lists):
   # Display user playlists for selected platform
   for name in lists:
      print(name)

def confirm_playlist_exist(source_playlist_name, plat_list, platform=""):
   # First try exact match
   if source_playlist_name in plat_list:
      source_playlist_id = plat_list[source_playlist_name]
      return source_playlist_id

   # Try with trailing space
   if source_playlist_name + " " in plat_list:
      source_playlist_id = plat_list[source_playlist_name + " "]
      print(f"[DEBUG] Found playlist with trailing space: '{source_playlist_name + ' '}'")
      return source_playlist_id

   # Try without trailing space
   if source_playlist_name.rstrip() in plat_list:
      source_playlist_id = plat_list[source_playlist_name.rstrip()]
      print(f"[DEBUG] Found playlist without trailing space: '{source_playlist_name.rstrip()}'")
      return source_playlist_id

   # Get platform code for error message
   platform_code = platform[:1].lower() + "+" if platform else "s+"
   message(platform_code, f"Selected {source_playlist_name} Playlist does not exist")
   return None

def what_to_move(old, new):
   new = list(set(new) - set(old))
   return new

def compare(first, second):
   # Compare 2 song info to make sure it's the same song
   match = SequenceMatcher(None, first, second).ratio()
   #if match is less than 45%, not a match
   if match > 0.45:
      return True
   return False

def write_to_file(play_name, songs, source, dest):
   # Write not found songs to file
   key = f"{source}->{dest} '{play_name}'"
   content = {key: songs}
   with open("notfound.txt", "a") as file:
      file.write(json.dumps(content))
      file.write("\n")

def report_sync_summary(total_not_found):
   # Report sync summary at the end
   if total_not_found == 0:
      print("\n[+] Sync completed successfully! All tracks were found and transferred.")
   else:
      print(f"\n[!] Sync completed. {total_not_found} track(s) could not be found.")
      print("[i] Check 'notfound.txt' for details about tracks that couldn't be transferred.")
