import os
import sys
import unittest
from unittest.mock import Mock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.applefuncs import (
    apple_auth,
    apple_dest_check,
    apple_is_logged_in,
    get_apple_playlist_content,
    get_apple_playlists,
    move_to_apple,
)


@pytest.mark.apple
@pytest.mark.auth
@pytest.mark.playlist
@pytest.mark.migration
class TestAppleFunctions(unittest.TestCase):
    """Test suite for Apple Music streaming provider functions."""

    def setUp(self):
        """Set up test fixtures with mock data."""
        self.mock_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0",
            "Authorization": "Bearer test_bearer_token",
            "Media-User-Token": "test_media_token",
        }

        # Mock playlists API response
        self.mock_playlists_response = {
            "data": [
                {
                    "id": "p.123",
                    "attributes": {
                        "name": "My Rock Playlist",
                        "description": {"standard": "Rock music collection"},
                    },
                    "relationships": {},
                },
                {
                    "id": "p.456",
                    "attributes": {
                        "name": "Chill Vibes",
                        "description": {"standard": "Relaxing music"},
                    },
                    "relationships": {"parent": {"data": [{"id": "f.789"}]}},
                },
                {
                    "id": "f.789",
                    "attributes": {"name": "Electronic Music", "folder": True},
                },
            ]
        }

        # Mock playlist content
        self.mock_playlist_content = {
            "meta": {"total": 2},
            "data": [
                {
                    "attributes": {
                        "name": "Bohemian Rhapsody",
                        "albumName": "A Night at the Opera",
                        "artistName": "Queen",
                    }
                },
                {
                    "attributes": {
                        "name": "Stairway to Heaven",
                        "albumName": "Led Zeppelin IV",
                        "artistName": "Led Zeppelin",
                    }
                },
            ],
        }

        # Mock search results
        self.mock_search_response = {
            "results": {
                "songs": {
                    "data": [
                        {
                            "id": "song_123",
                            "attributes": {
                                "name": "Bohemian Rhapsody",
                                "albumName": "A Night at the Opera",
                                "artistName": "Queen",
                            },
                        }
                    ]
                }
            }
        }

    @patch("builtins.open")
    @patch("src.applefuncs.apple_is_logged_in")
    def test_apple_auth_success(self, mock_is_logged_in, mock_open):
        """Test successful Apple Music authentication."""
        mock_credentials = {
            "authorization": "Bearer test_token",
            "media-user-token": "test_media_token",
        }

        mock_file = Mock()
        mock_file.__enter__ = Mock(return_value=Mock())
        mock_file.__exit__ = Mock(return_value=None)
        mock_open.return_value = mock_file

        mock_is_logged_in.return_value = self.mock_headers

        with (
            patch("json.load", return_value=mock_credentials),
            patch("src.applefuncs.message") as mock_message,
        ):
            result = apple_auth()

            assert result == self.mock_headers
            mock_message.assert_called_with("a+", "Successfully Authenticated")

    @patch("builtins.open", side_effect=FileNotFoundError)
    @patch("sys.exit")
    def test_apple_auth_failure_no_file(self, mock_exit, mock_open):
        """Test Apple Music authentication failure when credentials file doesn't exist."""
        with patch("src.applefuncs.message") as mock_message:
            apple_auth()

            mock_message.assert_called_with("a-", "Authentication failed")
            mock_exit.assert_called_with(0)

    @patch("builtins.open")
    @patch("src.applefuncs.apple_is_logged_in")
    @patch("sys.exit")
    def test_apple_auth_failure_invalid_credentials(
        self, mock_exit, mock_is_logged_in, mock_open
    ):
        """Test Apple Music authentication failure with invalid credentials."""
        mock_credentials = {
            "authorization": "Bearer invalid_token",
            "media-user-token": "invalid_media_token",
        }

        mock_file = Mock()
        mock_file.__enter__ = Mock(return_value=Mock())
        mock_file.__exit__ = Mock(return_value=None)
        mock_open.return_value = mock_file

        mock_is_logged_in.return_value = False

        with (
            patch("json.load", return_value=mock_credentials),
            patch("src.applefuncs.message") as mock_message,
        ):
            apple_auth()

            mock_message.assert_called_with("a-", "Authentication failed")
            mock_exit.assert_called_with(0)

    @patch("requests.get")
    def test_apple_is_logged_in_success(self, mock_get):
        """Test checking if Apple Music credentials are valid."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = apple_is_logged_in("Bearer test_token", "test_media_token")

        assert result is not None
        assert isinstance(result, dict)
        assert "Authorization" in result
        assert "Media-User-Token" in result

    @patch("requests.get")
    def test_apple_is_logged_in_failure(self, mock_get):
        """Test checking Apple Music credentials when they're invalid."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = apple_is_logged_in("Bearer invalid_token", "invalid_media_token")

        assert not result

    @patch("requests.get")
    def test_get_apple_playlists(self, mock_get):
        """Test retrieving Apple Music playlists."""

        # Mock folder info response for f.789
        mock_folder_response = Mock()
        mock_folder_response.status_code = 200
        mock_folder_response.json.return_value = {
            "data": [
                {
                    "id": "f.789",
                    "attributes": {"name": "Electronic Music", "folder": True},
                }
            ]
        }

        # Mock playlists response
        mock_playlists_response = Mock()
        mock_playlists_response.status_code = 200
        mock_playlists_response.json.return_value = self.mock_playlists_response

        # Configure mock_get to return different responses based on URL
        def mock_get_side_effect(url, **kwargs):
            if "f.789" in url:
                return mock_folder_response
            return mock_playlists_response

        mock_get.side_effect = mock_get_side_effect

        playlists, folders = get_apple_playlists(self.mock_headers)

        expected_playlists = {
            "My Rock Playlist": "p.123",
            "Electronic Music/Chill Vibes": "p.456",
        }
        expected_folders = {"f.789": "Electronic Music"}

        assert playlists == expected_playlists
        assert folders == expected_folders

    @patch("requests.get")
    def test_get_apple_playlists_no_folders(self, mock_get):
        """Test retrieving Apple Music playlists when no folders exist."""
        mock_response_data = {
            "data": [
                {
                    "id": "p.123",
                    "attributes": {
                        "name": "My Rock Playlist",
                        "description": {"standard": "Rock music collection"},
                    },
                    "relationships": {},
                }
            ]
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response

        playlists, folders = get_apple_playlists(self.mock_headers)

        expected_playlists = {"My Rock Playlist": "p.123"}
        expected_folders = {}

        assert playlists == expected_playlists
        assert folders == expected_folders

    @patch("requests.get")
    def test_get_apple_playlists_api_failure(self, mock_get):
        """Test handling API failure when retrieving playlists."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        playlists, folders = get_apple_playlists(self.mock_headers)

        assert playlists == {}
        assert folders == {}

    def test_apple_dest_check_existing_playlist(self):
        """Test checking for existing destination playlist."""
        playlists = {"Test Playlist": "p.123"}

        with patch("src.applefuncs.message") as mock_message:
            result = apple_dest_check(playlists, self.mock_headers, "Test Playlist")

            assert result == "p.123"
            mock_message.assert_called_with(
                "a+", "Playlist exists, adding missing songs"
            )

    @patch("src.applefuncs.appleapi_create_playlist")
    def test_apple_dest_check_create_new_playlist(self, mock_create):
        """Test creating new playlist when it doesn't exist."""
        playlists = {}
        mock_create.return_value = "p.new123"

        with patch("src.applefuncs.message") as mock_message:
            result = apple_dest_check(playlists, self.mock_headers, "New Playlist")

            assert result == "p.new123"
            mock_create.assert_called_with("New Playlist", self.mock_headers)
            mock_message.assert_called_with("a+", "Playlist created")

    @patch("requests.get")
    def test_get_apple_playlist_content(self, mock_get):
        """Test retrieving Apple Music playlist content."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_playlist_content
        mock_get.return_value = mock_response

        result = get_apple_playlist_content(self.mock_headers, "p.123")

        expected = [
            "A Night at the Opera&@#72Bohemian Rhapsody&@#72Queen",
            "Led Zeppelin IV&@#72Stairway to Heaven&@#72Led Zeppelin",
        ]
        assert result == expected

    @patch("requests.get")
    def test_get_apple_playlist_content_empty(self, mock_get):
        """Test retrieving content from empty playlist."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"meta": {"total": 0}, "data": []}
        mock_get.return_value = mock_response

        result = get_apple_playlist_content(self.mock_headers, "p.123")

        assert result == []

    @patch("requests.get")
    def test_get_apple_playlist_content_api_failure(self, mock_get):
        """Test handling API failure when retrieving playlist content."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "errors": [{"status": "404", "title": "Not Found"}]
        }
        mock_get.return_value = mock_response

        result = get_apple_playlist_content(self.mock_headers, "p.123")

        assert result == []

    @patch("src.applefuncs.get_apple_playlist_content")
    @patch("src.applefuncs.what_to_move")
    @patch("src.applefuncs.tqdm")
    @patch("src.applefuncs.appleapi_music_search")
    @patch("src.applefuncs.appleapi_add_playlist_item")
    def test_move_to_apple(
        self, mock_add_song, mock_search, mock_tqdm, mock_what_to_move, mock_get_content
    ):
        """Test moving songs to Apple Music playlist."""
        # Mock existing playlist content
        mock_get_content.return_value = []

        # Mock songs to move
        playlist_info = [
            "A Night at the Opera&@#72Bohemian Rhapsody&@#72Queen",
            "Imagine&@#72Imagine&@#72John Lennon",
        ]
        mock_what_to_move.return_value = playlist_info

        # Mock search results
        mock_search.return_value = {
            "results": {
                "song": {
                    "data": [
                        {
                            "id": "song_123",
                            "attributes": {
                                "name": "Bohemian Rhapsody",
                                "albumName": "A Night at the Opera",
                                "artistName": "Queen",
                            },
                        }
                    ]
                }
            }
        }

        # Mock tqdm to return the input directly
        mock_tqdm.return_value = playlist_info

        with (
            patch("src.applefuncs.compare", return_value=True),
            patch("src.applefuncs.sleep"),
        ):
            move_to_apple(
                self.mock_headers, playlist_info, "p.123", "Test Playlist"
            )

            # Should call add song to playlist
            mock_add_song.assert_called()

    @patch("src.applefuncs.get_apple_playlist_content")
    @patch("src.applefuncs.what_to_move")
    @patch("src.applefuncs.tqdm")
    @patch("src.applefuncs.appleapi_music_search")
    def test_move_to_apple_song_not_found(
        self, mock_search, mock_tqdm, mock_what_to_move, mock_get_content
    ):
        """Test moving songs to Apple Music when some songs are not found."""
        mock_get_content.return_value = []

        playlist_info = ["Unknown Album&@#72Unknown Song&@#72Unknown Artist"]
        mock_what_to_move.return_value = playlist_info
        mock_tqdm.return_value = playlist_info

        # Mock empty search results
        mock_search.return_value = {"results": {}}

        result = move_to_apple(
            self.mock_headers, playlist_info, "p.123", "Test Playlist"
        )

        # Should return the song that wasn't found
        assert result == ["Unknown Album Unknown Song Unknown Artist"]

    @patch("src.applefuncs.get_apple_playlist_content")
    @patch("src.applefuncs.what_to_move")
    @patch("src.applefuncs.tqdm")
    @patch("src.applefuncs.appleapi_music_search")
    def test_move_to_apple_with_parentheses_removal(
        self, mock_search, mock_tqdm, mock_what_to_move, mock_get_content
    ):
        """Test moving songs with parentheses removal fallback."""
        mock_get_content.return_value = []

        playlist_info = ["Album&@#72Song (Remix)&@#72Artist"]
        mock_what_to_move.return_value = playlist_info
        mock_tqdm.return_value = playlist_info

        # First search returns empty, second search returns results
        empty_result = {"results": {}}
        success_result = {
            "results": {
                "song": {
                    "data": [
                        {
                            "id": "song_123",
                            "attributes": {
                                "name": "Song",
                                "albumName": "Album",
                                "artistName": "Artist",
                            },
                        }
                    ]
                }
            }
        }
        mock_search.side_effect = [empty_result, success_result]

        with (
            patch("src.applefuncs.compare", return_value=True),
            patch("src.applefuncs.sleep"),
            patch("src.applefuncs.appleapi_add_playlist_item"),
        ):
            move_to_apple(
                self.mock_headers, playlist_info, "p.123", "Test Playlist"
            )

            # Should have called search twice (with and without parentheses)
            assert mock_search.call_count == 2

    @patch("sys.exit")
    def test_move_to_apple_keyboard_interrupt(self, mock_exit):
        """Test handling keyboard interrupt during move operation."""
        with (
            patch("src.applefuncs.get_apple_playlist_content", return_value=[]),
            patch("src.applefuncs.what_to_move", return_value=["test"]),
            patch("src.applefuncs.tqdm", side_effect=KeyboardInterrupt()),
        ):
            move_to_apple(self.mock_headers, ["test"], "p.123", "Test Playlist")
            mock_exit.assert_called_with(0)

    @patch("requests.post")
    def test_appleapi_create_playlist(self, mock_post):
        """Test creating a new Apple Music playlist via API."""
        from src.applefuncs import appleapi_create_playlist

        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"data": [{"id": "p.new123"}]}
        mock_post.return_value = mock_response

        result = appleapi_create_playlist(
            "Test Playlist", "Test Description", self.mock_headers
        )

        assert result == "p.new123"
        mock_post.assert_called_once()

    @patch("requests.get")
    def test_appleapi_music_search(self, mock_get):
        """Test searching for songs in Apple Music."""
        from src.applefuncs import appleapi_music_search

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_search_response
        mock_get.return_value = mock_response

        result = appleapi_music_search("Bohemian Rhapsody", self.mock_headers)

        assert result == self.mock_search_response
        mock_get.assert_called_once()

    @patch("requests.post")
    def test_appleapi_add_playlist_item(self, mock_post):
        """Test adding a song to an Apple Music playlist."""
        from src.applefuncs import appleapi_add_playlist_item

        mock_response = Mock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        appleapi_add_playlist_item("p.123", "song_123", self.mock_headers)

        mock_post.assert_called_once()

    @patch("requests.get")
    def test_appleapi_get_folder_info(self, mock_get):
        """Test retrieving folder information by ID."""
        from src.applefuncs import appleapi_get_folder_info

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"attributes": {"name": "Test Folder"}}]
        }
        mock_get.return_value = mock_response

        result = appleapi_get_folder_info("f.123", self.mock_headers)

        assert result == "Test Folder"

    @patch("requests.get")
    def test_appleapi_get_folder_info_not_found(self, mock_get):
        """Test handling case when folder is not found."""
        from src.applefuncs import appleapi_get_folder_info

        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = appleapi_get_folder_info("f.nonexistent", self.mock_headers)

        assert result is None


if __name__ == "__main__":
    unittest.main()
