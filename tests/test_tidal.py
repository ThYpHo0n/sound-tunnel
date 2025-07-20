import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.tidalfuncs import (
    get_tidal_playlist_content,
    get_tidal_playlists,
    move_to_tidal,
    tidal_auth,
    tidal_dest_check,
)


@pytest.mark.tidal
@pytest.mark.auth
@pytest.mark.playlist
@pytest.mark.migration
class TestTidalFunctions(unittest.TestCase):
    """Test suite for Tidal streaming provider functions."""

    def setUp(self):
        """Set up test fixtures with mock data."""
        self.mock_tidal = Mock()

        # Mock user playlists
        mock_playlist1 = Mock()
        mock_playlist1.name = "My Tidal Playlist"
        mock_playlist1.id = "tidal_playlist_123"

        mock_playlist2 = Mock()
        mock_playlist2.name = "Rock Collection"
        mock_playlist2.id = "tidal_playlist_456"

        mock_playlist3 = Mock()
        mock_playlist3.name = "Jazz Essentials"
        mock_playlist3.id = "tidal_playlist_789"

        self.mock_user_playlists = [mock_playlist1, mock_playlist2, mock_playlist3]

        # Mock playlist tracks
        mock_track1 = Mock()
        mock_track1.name = "Bohemian Rhapsody"
        mock_track1.album = Mock()
        mock_track1.album.name = "A Night at the Opera"
        mock_artist1 = Mock()
        mock_artist1.name = "Queen"
        mock_track1.artists = [mock_artist1]

        mock_track2 = Mock()
        mock_track2.name = "Stairway to Heaven"
        mock_track2.album = Mock()
        mock_track2.album.name = "Led Zeppelin IV"
        mock_artist2 = Mock()
        mock_artist2.name = "Led Zeppelin"
        mock_track2.artists = [mock_artist2]

        self.mock_playlist_tracks = [mock_track1, mock_track2]

        # Mock search response
        self.mock_search_response = {
            "tracks": {
                "items": [
                    {
                        "title": "Bohemian Rhapsody",
                        "id": "track_123",
                        "album": {"title": "A Night at the Opera"},
                        "artists": [{"name": "Queen"}]
                    }
                ]
            }
        }

        # Mock folders API response
        self.mock_folders_response = {
            "items": [
                {
                    "itemType": "FOLDER",
                    "name": "Rock Music",
                    "data": {"id": "folder_123"}
                },
                {
                    "itemType": "FOLDER",
                    "name": "Classical",
                    "data": {"id": "folder_456"}
                }
            ]
        }

    @patch("src.tidalfuncs.tidalapi.Session")
    @patch("builtins.open")
    def test_tidal_auth_success_with_cached_credentials(self, mock_open, mock_session_class):
        """Test successful Tidal authentication with cached credentials."""
        # Mock cached credentials
        future_time = datetime.now() + timedelta(hours=1)
        mock_creds = [
            "Bearer",
            "access_token_123",
            "refresh_token_456",
            future_time.strftime("%m/%d/%Y, %H:%M:%S.%f")
        ]

        # Create mock file context manager
        mock_file_manager = Mock()
        mock_file_manager.__enter__ = Mock(return_value=mock_creds)
        mock_file_manager.__exit__ = Mock(return_value=None)
        mock_open.return_value = mock_file_manager

        mock_session = Mock()
        mock_session.load_oauth_session.return_value = True
        mock_session_class.return_value = mock_session

        with patch("src.tidalfuncs.message") as mock_message:
            result = tidal_auth()

            self.assertEqual(result, mock_session)
            mock_message.assert_called_with("t+", "Successfully Authenticated")

    @patch("src.tidalfuncs.tidalapi.Session")
    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_tidal_auth_success_with_oauth(self, mock_open, mock_session_class):
        """Test successful Tidal authentication with OAuth flow."""
        mock_session = Mock()
        mock_session.check_login.return_value = True
        mock_session.token_type = "Bearer"
        mock_session.access_token = "new_access_token"
        mock_session.refresh_token = "new_refresh_token"
        mock_session.expiry_time = datetime.now() + timedelta(hours=1)
        mock_session_class.return_value = mock_session

        # Mock file writing
        mock_file_write = Mock()
        mock_file_write.__enter__ = Mock(return_value=Mock())
        mock_file_write.__exit__ = Mock(return_value=None)

        with patch("builtins.open", return_value=mock_file_write), \
             patch("src.tidalfuncs.message") as mock_message:
            result = tidal_auth()

            self.assertEqual(result, mock_session)
            mock_session.login_oauth_simple.assert_called_once()
            mock_message.assert_called_with("t+", "Successfully Authenticated")

    @patch("src.tidalfuncs.tidalapi.Session")
    @patch("sys.exit")
    def test_tidal_auth_failure(self, mock_exit, mock_session_class):
        """Test Tidal authentication failure."""
        mock_session = Mock()
        mock_session.check_login.return_value = False
        mock_session_class.return_value = mock_session

        with patch("builtins.open", side_effect=FileNotFoundError), \
             patch("src.tidalfuncs.message") as mock_message:
            tidal_auth()

            mock_message.assert_called_with("t-", "Authentication failed")
            mock_exit.assert_called_with(0)

    def test_get_tidal_playlists_user_playlists_only(self):
        """Test retrieving Tidal playlists from user playlists."""
        self.mock_tidal.user.playlists.return_value = self.mock_user_playlists

        # Mock empty folders response
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 404

            result = get_tidal_playlists(self.mock_tidal)

            expected = {
                "My Tidal Playlist": "tidal_playlist_123",
                "Rock Collection": "tidal_playlist_456",
                "Jazz Essentials": "tidal_playlist_789"
            }
            self.assertEqual(result, expected)

    @patch("requests.get")
    def test_get_tidal_playlists_with_folders(self, mock_get):
        """Test retrieving Tidal playlists including those in folders."""
        self.mock_tidal.user.playlists.return_value = self.mock_user_playlists
        self.mock_tidal.access_token = "test_token"

        # Mock successful folders API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_folders_response
        mock_get.return_value = mock_response

        # Mock folder object and its playlists
        mock_folder = Mock()
        mock_folder_playlist = Mock(id="folder_playlist_123")
        mock_folder_playlist.name = "Folder Playlist"  # Set as attribute, not Mock
        mock_folder.items.return_value = [mock_folder_playlist]
        self.mock_tidal.folder.return_value = mock_folder

        result = get_tidal_playlists(self.mock_tidal)

        # Should include both user playlists and folder playlists
        self.assertIn("My Tidal Playlist", result)
        self.assertIn("Rock Music/Folder Playlist", result)

    @patch("requests.get")
    def test_get_tidal_playlists_folders_api_failure(self, mock_get):
        """Test handling folders API failure gracefully."""
        self.mock_tidal.user.playlists.return_value = self.mock_user_playlists

        # Mock failed folders API response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = get_tidal_playlists(self.mock_tidal)

        # Should still return user playlists
        expected = {
            "My Tidal Playlist": "tidal_playlist_123",
            "Rock Collection": "tidal_playlist_456",
            "Jazz Essentials": "tidal_playlist_789"
        }
        self.assertEqual(result, expected)

    def test_get_tidal_playlist_content(self):
        """Test retrieving Tidal playlist content."""
        mock_playlist = Mock()
        mock_playlist.tracks.return_value = self.mock_playlist_tracks
        self.mock_tidal.playlist.return_value = mock_playlist

        result = get_tidal_playlist_content(self.mock_tidal, "playlist_123")

        expected = [
            "A Night at the Opera&@#72Bohemian Rhapsody&@#72Queen",
            "Led Zeppelin IV&@#72Stairway to Heaven&@#72Led Zeppelin"
        ]
        self.assertEqual(result, expected)

    def test_get_tidal_playlist_content_multiple_artists(self):
        """Test playlist content with multiple artists."""
        # Create mock artists with proper name attributes
        mock_artist1 = Mock()
        mock_artist1.name = "Queen"
        mock_artist2 = Mock()
        mock_artist2.name = "David Bowie"

        # Create mock album with proper name attribute
        mock_album = Mock()
        mock_album.name = "Hot Space"

        # Create mock track with proper name attribute
        mock_track = Mock()
        mock_track.name = "Under Pressure"
        mock_track.album = mock_album
        mock_track.artists = [mock_artist1, mock_artist2]

        mock_playlist = Mock()
        mock_playlist.tracks.return_value = [mock_track]
        self.mock_tidal.playlist.return_value = mock_playlist

        result = get_tidal_playlist_content(self.mock_tidal, "playlist_123")

        expected = ["Hot Space&@#72Under Pressure&@#72Queen David Bowie"]
        self.assertEqual(result, expected)

    def test_tidal_dest_check_existing_playlist(self):
        """Test checking for existing destination playlist."""
        playlists = {"Test Playlist": "playlist_123"}

        with patch("src.tidalfuncs.message") as mock_message:
            result = tidal_dest_check(playlists, self.mock_tidal, "Test Playlist")

            self.assertEqual(result, "playlist_123")
            mock_message.assert_called_with("t+", "Playlist exists, adding missing songs")

    @patch("src.tidalfuncs.tidal_create_playlist")
    def test_tidal_dest_check_create_new_playlist(self, mock_create):
        """Test creating new playlist when it doesn't exist."""
        playlists = {}
        mock_create.return_value = "new_playlist_123"
        self.mock_tidal.access_token = "test_token"

        with patch("src.tidalfuncs.message") as mock_message:
            result = tidal_dest_check(playlists, self.mock_tidal, "New Playlist")

            self.assertEqual(result, "new_playlist_123")
            mock_create.assert_called_with("New Playlist", "Sound Tunnel playlist", "test_token")
            mock_message.assert_called_with("t+", "Playlist created")

    @patch("requests.get")
    def test_tidal_dest_check_create_with_folder_structure(self, mock_get):
        """Test creating playlist with folder structure from Apple Music."""
        playlists = {}
        apple_folders = {"rock_folder_id": "Rock"}  # Fixed key-value mapping
        self.mock_tidal.access_token = "test_token"

        # Mock existing folder found via API
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "itemType": "FOLDER",
                    "name": "Rock",
                    "data": {"id": "folder_123"}
                }
            ]
        }
        mock_get.return_value = mock_response

        # Mock playlist creation
        mock_playlist = Mock(id="new_playlist_123")
        self.mock_tidal.user.create_playlist.return_value = mock_playlist

        # Mock folder object
        mock_folder = Mock()
        self.mock_tidal.folder.return_value = mock_folder

        with patch("src.tidalfuncs.message") as mock_message:
            result = tidal_dest_check(playlists, self.mock_tidal, "Rock/New Playlist", apple_folders)

            self.assertEqual(result, "new_playlist_123")
            self.mock_tidal.user.create_playlist.assert_called_with("New Playlist", "")
            mock_folder.add_items.assert_called_with(["new_playlist_123"])

    @patch("src.tidalfuncs.get_tidal_playlist_content")
    @patch("src.tidalfuncs.what_to_move")
    @patch("src.tidalfuncs.tqdm")
    @patch("src.tidalfuncs.tidal_search_playlist")
    @patch("src.tidalfuncs.tidal_add_song_to_playlist")
    def test_move_to_tidal(self, mock_add_song, mock_search, mock_tqdm, mock_what_to_move, mock_get_content):
        """Test moving songs to Tidal playlist."""
        # Mock existing playlist content
        mock_get_content.return_value = []

        # Mock songs to move
        playlist_info = [
            "A Night at the Opera&@#72Bohemian Rhapsody&@#72Queen",
            "Imagine&@#72Imagine&@#72John Lennon"
        ]
        mock_what_to_move.return_value = playlist_info

        # Mock search results
        mock_search.return_value = self.mock_search_response

        # Mock tqdm to return the input directly
        mock_tqdm.return_value = playlist_info

        self.mock_tidal.access_token = "test_token"

        with patch("src.tidalfuncs.compare", return_value=True), \
             patch("src.tidalfuncs.sleep"):

            result = move_to_tidal(self.mock_tidal, playlist_info, "playlist_123", "Test Playlist")

            # Should call add song to playlist
            mock_add_song.assert_called()

    @patch("src.tidalfuncs.get_tidal_playlist_content")
    @patch("src.tidalfuncs.what_to_move")
    @patch("src.tidalfuncs.tqdm")
    @patch("src.tidalfuncs.tidal_search_playlist")
    def test_move_to_tidal_song_not_found(self, mock_search, mock_tqdm, mock_what_to_move, mock_get_content):
        """Test moving songs to Tidal when some songs are not found."""
        mock_get_content.return_value = []

        playlist_info = ["Unknown Album&@#72Unknown Song&@#72Unknown Artist"]
        mock_what_to_move.return_value = playlist_info
        mock_tqdm.return_value = playlist_info

        # Create a simple string that when stringified has exactly 408 characters
        error_response = "x" * 408
        mock_search.return_value = error_response

        self.mock_tidal.access_token = "test_token"

        result = move_to_tidal(self.mock_tidal, playlist_info, "playlist_123", "Test Playlist")

        # Should return the song that wasn't found (the original song name, not the modified one)
        self.assertEqual(result, ["Unknown Song Unknown Artist"])

    @patch("src.tidalfuncs.get_tidal_playlist_content")
    @patch("src.tidalfuncs.what_to_move")
    @patch("src.tidalfuncs.tqdm")
    @patch("src.tidalfuncs.tidal_search_playlist")
    def test_move_to_tidal_with_parentheses_removal(self, mock_search, mock_tqdm, mock_what_to_move, mock_get_content):
        """Test moving songs with parentheses removal fallback."""
        mock_get_content.return_value = []

        playlist_info = ["Album&@#72Song (Remix)&@#72Artist"]
        mock_what_to_move.return_value = playlist_info
        mock_tqdm.return_value = playlist_info

        # First search result has len(str()) == 408 to trigger fallback
        # Second search result has len(list()) == 408 to trigger not_found
        first_error = "x" * 408  # String with exactly 408 characters
        second_error = ["x"] * 408  # List with exactly 408 items

        mock_search.side_effect = [first_error, second_error]

        self.mock_tidal.access_token = "test_token"

        result = move_to_tidal(self.mock_tidal, playlist_info, "playlist_123", "Test Playlist")

        # Should have called search twice (with and without parentheses)
        self.assertEqual(mock_search.call_count, 2)
        # Should return the song that wasn't found (original with parentheses as stored in bk)
        self.assertEqual(result, ["Song (Remix) Artist"])

    @patch("sys.exit")
    def test_move_to_tidal_keyboard_interrupt(self, mock_exit):
        """Test handling keyboard interrupt during move operation."""
        with patch("src.tidalfuncs.get_tidal_playlist_content", return_value=[]), \
             patch("src.tidalfuncs.what_to_move", return_value=["test"]), \
             patch("src.tidalfuncs.tqdm", side_effect=KeyboardInterrupt()):

            move_to_tidal(self.mock_tidal, ["test"], "playlist_123", "Test Playlist")
            mock_exit.assert_called_with(0)

    @patch("requests.put")
    def test_tidal_create_playlist(self, mock_put):
        """Test creating a new Tidal playlist via API."""
        from src.tidalfuncs import tidal_create_playlist

        mock_response = Mock()
        mock_response.json.return_value = {"data": {"uuid": "new_playlist_123"}}
        mock_put.return_value = mock_response

        result = tidal_create_playlist("Test Playlist", "Test Description", "test_token")

        self.assertEqual(result, "new_playlist_123")
        mock_put.assert_called_once()

    @patch("requests.get")
    def test_tidal_search_playlist(self, mock_get):
        """Test searching for songs in Tidal."""
        from src.tidalfuncs import tidal_search_playlist

        mock_response = Mock()
        mock_response.json.return_value = self.mock_search_response
        mock_get.return_value = mock_response

        result = tidal_search_playlist("Bohemian Rhapsody", "test_token")

        self.assertEqual(result, self.mock_search_response)
        mock_get.assert_called_once()

    @patch("requests.get")
    @patch("requests.post")
    def test_tidal_add_song_to_playlist(self, mock_post, mock_get):
        """Test adding a song to a Tidal playlist."""
        from src.tidalfuncs import tidal_add_song_to_playlist

        # Mock the GET request for ETag
        mock_get_response = Mock()
        mock_get_response.headers = {"Etag": "test_etag"}
        mock_get.return_value = mock_get_response

        # Mock the POST request
        mock_post_response = Mock()
        mock_post.return_value = mock_post_response

        tidal_add_song_to_playlist("playlist_123", "track_123", "test_token")

        mock_get.assert_called_once()
        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
