import os
import sys
import unittest
from unittest.mock import Mock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ytfuncs import (
    change_name,
    get_youtube_playlists,
    get_yt_playlist_content,
    move_to_ytmusic,
    yt_dest_check,
    ytmusic_auth,
)


@pytest.mark.youtube
@pytest.mark.auth
@pytest.mark.playlist
@pytest.mark.migration
class TestYoutubeFunctions(unittest.TestCase):
    """Test suite for YouTube Music streaming provider functions."""

    def setUp(self):
        """Set up test fixtures with mock data."""
        self.mock_ytmusic = Mock()

        # Mock playlist data
        self.mock_playlists_response = [
            {
                "title": "My Rock Playlist",
                "playlistId": "PLrAUCsHkE_rock123",
            },
            {
                "title": "Chill Music",
                "playlistId": "PLrAUCsHkE_chill456",
            },
            {
                "title": "spfy2yt Old Playlist",
                "playlistId": "PLrAUCsHkE_old789",
            },
        ]

        # Mock playlist content
        self.mock_playlist_content = {
            "tracks": [
                {
                    "title": "Bohemian Rhapsody",
                    "album": {"name": "A Night at the Opera"},
                    "artists": [{"name": "Queen"}],
                },
                {
                    "title": "Stairway to Heaven",
                    "album": {"name": "Led Zeppelin IV"},
                    "artists": [{"name": "Led Zeppelin"}],
                },
                {
                    "title": "Song Without Album",
                    "artists": [{"name": "Unknown Artist"}],
                },
            ]
        }

        # Mock search results
        self.mock_search_response = [
            {
                "title": "Bohemian Rhapsody",
                "videoId": "dQw4w9WgXcQ",
                "album": {"name": "A Night at the Opera"},
                "artists": [{"name": "Queen"}],
            }
        ]

    @patch("src.ytfuncs.YTMusic")
    def test_ytmusic_auth_success(self, mock_ytmusic_class):
        """Test successful YouTube Music authentication."""
        mock_ytmusic_instance = Mock()
        mock_ytmusic_class.return_value = mock_ytmusic_instance

        with patch("src.ytfuncs.message") as mock_message:
            result = ytmusic_auth()

            assert result == mock_ytmusic_instance
            mock_message.assert_called_with("y+", "Successfully Authenticated")

    @patch("src.ytfuncs.YTMusic")
    @patch("sys.exit")
    def test_ytmusic_auth_failure(self, mock_exit, mock_ytmusic_class):
        """Test YouTube Music authentication failure."""
        mock_ytmusic_class.side_effect = Exception("Auth failed")

        with patch("src.ytfuncs.message") as mock_message:
            ytmusic_auth()

            mock_message.assert_called_with("y+", "Authentication failed")
            mock_exit.assert_called_with(0)

    def test_get_youtube_playlists(self):
        """Test retrieving YouTube Music playlists."""
        self.mock_ytmusic.get_library_playlists.return_value = (
            self.mock_playlists_response
        )

        result = get_youtube_playlists(self.mock_ytmusic)

        expected = {
            "My Rock Playlist": "PLrAUCsHkE_rock123",
            "Chill Music": "PLrAUCsHkE_chill456",
            "spfy2yt Old Playlist": "PLrAUCsHkE_old789",
        }
        assert result == expected
        self.mock_ytmusic.get_library_playlists.assert_called_once_with(1000)

    def test_get_youtube_playlists_empty(self):
        """Test retrieving YouTube Music playlists when no playlists exist."""
        self.mock_ytmusic.get_library_playlists.return_value = []

        result = get_youtube_playlists(self.mock_ytmusic)

        assert result == {}

    def test_change_name_success(self):
        """Test changing old spfy2yt playlist names to sound-tunnel."""
        yt_lists = {
            "spfy2yt Old Playlist": "PLrAUCsHkE_old789",
            "Normal Playlist": "PLrAUCsHkE_normal123",
        }

        self.mock_ytmusic.edit_playlist.return_value = "STATUS_SUCCEEDED"

        with patch("src.ytfuncs.message") as mock_message:
            change_name(self.mock_ytmusic, yt_lists)

            self.mock_ytmusic.edit_playlist.assert_called_once_with(
                "PLrAUCsHkE_old789", "sound-tunnel Old Playlist"
            )
            mock_message.assert_called_with(
                "y+",
                "Renamed spfy2yt Old Playlist to sound-tunnel Old Playlist to fit new script",
            )

    def test_change_name_no_spfy2yt_playlists(self):
        """Test change_name when no spfy2yt playlists exist."""
        yt_lists = {
            "Normal Playlist": "PLrAUCsHkE_normal123",
            "Another Playlist": "PLrAUCsHkE_another456",
        }

        change_name(self.mock_ytmusic, yt_lists)

        self.mock_ytmusic.edit_playlist.assert_not_called()

    def test_get_yt_playlist_content(self):
        """Test retrieving YouTube Music playlist content."""
        self.mock_ytmusic.get_playlist.return_value = self.mock_playlist_content

        result = get_yt_playlist_content(self.mock_ytmusic, "PLrAUCsHkE_test123")

        expected = [
            "A Night at the Opera&Bohemian Rhapsody&Queen",
            "Led Zeppelin IV&Stairway to Heaven&Led Zeppelin",
            "&Song Without Album&Unknown Artist",
        ]
        assert result == expected
        self.mock_ytmusic.get_playlist.assert_called_once_with("PLrAUCsHkE_test123")

    def test_get_yt_playlist_content_multiple_artists(self):
        """Test playlist content with multiple artists."""
        mock_content = {
            "tracks": [
                {
                    "title": "Under Pressure",
                    "album": {"name": "Hot Space"},
                    "artists": [{"name": "Queen"}, {"name": "David Bowie"}],
                }
            ]
        }
        self.mock_ytmusic.get_playlist.return_value = mock_content

        result = get_yt_playlist_content(self.mock_ytmusic, "PLrAUCsHkE_test123")

        expected = ["Hot Space&Under Pressure&Queen David Bowie"]
        assert result == expected

    def test_yt_dest_check_existing_playlist(self):
        """Test checking for existing destination playlist."""
        yt_lists = {"Test Playlist": "PLrAUCsHkE_test123"}

        with patch("src.ytfuncs.message") as mock_message:
            result = yt_dest_check(self.mock_ytmusic, yt_lists, "Test Playlist")

            assert result == "PLrAUCsHkE_test123"
            mock_message.assert_called_with(
                "y+", "Playlist exists, adding missing songs"
            )

    def test_yt_dest_check_create_new_playlist(self):
        """Test creating new playlist when it doesn't exist."""
        yt_lists = {}
        self.mock_ytmusic.create_playlist.return_value = "PLrAUCsHkE_new123"

        with patch("src.ytfuncs.message") as mock_message:
            result = yt_dest_check(self.mock_ytmusic, yt_lists, "New Playlist")

            assert result == "PLrAUCsHkE_new123"
            self.mock_ytmusic.create_playlist.assert_called_with(
                "New Playlist", "Sound Tunnel playlist"
            )
            mock_message.assert_called_with("y+", "Playlist created")

    @patch("src.ytfuncs.get_yt_playlist_content")
    @patch("src.ytfuncs.what_to_move")
    @patch("src.ytfuncs.tqdm")
    def test_move_to_ytmusic(self, mock_tqdm, mock_what_to_move, mock_get_content):
        """Test moving songs to YouTube Music playlist."""
        # Mock existing playlist content
        mock_get_content.return_value = []

        # Mock songs to move
        playlist_info = [
            "A Night at the Opera&Bohemian Rhapsody&Queen",
            "Imagine&Imagine&John Lennon",
        ]
        mock_what_to_move.return_value = playlist_info

        # Mock search results
        self.mock_ytmusic.search.return_value = self.mock_search_response

        # Mock tqdm to return the input directly
        mock_tqdm.return_value = playlist_info

        # Mock successful add result
        self.mock_ytmusic.add_playlist_items.return_value = "STATUS_SUCCEEDED"

        with patch("src.ytfuncs.sleep"):
            move_to_ytmusic(
                self.mock_ytmusic, playlist_info, "PLrAUCsHkE_test123", "Test Playlist"
            )

            # Should call add_playlist_items
            self.mock_ytmusic.add_playlist_items.assert_called()

    @patch("src.ytfuncs.get_yt_playlist_content")
    @patch("src.ytfuncs.what_to_move")
    @patch("src.ytfuncs.tqdm")
    def test_move_to_ytmusic_song_not_found(
        self, mock_tqdm, mock_what_to_move, mock_get_content
    ):
        """Test moving songs to YouTube Music when some songs are not found."""
        mock_get_content.return_value = []

        playlist_info = ["Unknown Album&Unknown Song&Unknown Artist"]
        mock_what_to_move.return_value = playlist_info
        mock_tqdm.return_value = playlist_info

        # Mock search that returns empty results (will cause IndexError)
        self.mock_ytmusic.search.return_value = []

        result = move_to_ytmusic(
            self.mock_ytmusic, playlist_info, "PLrAUCsHkE_test123", "Test Playlist"
        )

        # Should return not_found list due to exception handling
        assert result == []

    @patch("src.ytfuncs.get_yt_playlist_content")
    @patch("src.ytfuncs.what_to_move")
    @patch("src.ytfuncs.tqdm")
    def test_move_to_ytmusic_add_failure(
        self, mock_tqdm, mock_what_to_move, mock_get_content
    ):
        """Test moving songs when add operation fails."""
        mock_get_content.return_value = []

        playlist_info = ["Album&Song&Artist"]
        mock_what_to_move.return_value = playlist_info
        mock_tqdm.return_value = playlist_info

        # Mock search returns results but add fails
        self.mock_ytmusic.search.return_value = self.mock_search_response
        self.mock_ytmusic.add_playlist_items.return_value = "FAILED"

        with patch("src.ytfuncs.sleep"):
            result = move_to_ytmusic(
                self.mock_ytmusic, playlist_info, "PLrAUCsHkE_test123", "Test Playlist"
            )

            # Should return the song that failed to add
            assert result == ["Album Song Artist"]

    @patch("sys.exit")
    def test_move_to_ytmusic_keyboard_interrupt(self, mock_exit):
        """Test handling keyboard interrupt during move operation."""
        with (
            patch("src.ytfuncs.get_yt_playlist_content", return_value=[]),
            patch("src.ytfuncs.what_to_move", return_value=["test"]),
            patch("src.ytfuncs.tqdm", side_effect=KeyboardInterrupt()),
        ):
            move_to_ytmusic(
                self.mock_ytmusic, ["test"], "PLrAUCsHkE_test123", "Test Playlist"
            )
            mock_exit.assert_called_with(0)


if __name__ == "__main__":
    unittest.main()
