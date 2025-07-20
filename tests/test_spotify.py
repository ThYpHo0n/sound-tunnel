import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.spfyfuncs import spotify_auth, get_spotify_playlists, get_spfy_likes, spfy_dest_check, move_to_spfy
from src.mainfuncs import message


@pytest.mark.spotify
@pytest.mark.auth
@pytest.mark.playlist
@pytest.mark.migration
class TestSpotifyFunctions(unittest.TestCase):
    """Test suite for Spotify streaming provider functions."""

    def setUp(self):
        """Set up test fixtures with mock data."""
        self.mock_spotify = Mock()
        self.mock_user_id = "test_user_123"

        # Mock playlist data
        self.mock_playlists_response = {
            'items': [
                {
                    'name': 'My Awesome Playlist',
                    'id': 'playlist_123',
                    'owner': {'id': self.mock_user_id}
                },
                {
                    'name': 'Rock Collection',
                    'id': 'playlist_456',
                    'owner': {'id': self.mock_user_id}
                },
                {
                    'name': 'Chill Vibes',
                    'id': 'playlist_789',
                    'owner': {'id': self.mock_user_id}
                }
            ]
        }

        # Mock liked songs data
        self.mock_likes_response = {
            'total': 3,
            'items': [
                {
                    'track': {
                        'name': 'Bohemian Rhapsody',
                        'album': {'name': 'A Night at the Opera'},
                        'artists': [{'name': 'Queen'}]
                    }
                },
                {
                    'track': {
                        'name': 'Imagine',
                        'album': {'name': 'Imagine'},
                        'artists': [{'name': 'John Lennon'}]
                    }
                },
                {
                    'track': {
                        'name': 'Hotel California',
                        'album': {'name': 'Hotel California'},
                        'artists': [{'name': 'Eagles'}]
                    }
                }
            ]
        }

        # Mock playlist content
        self.mock_playlist_tracks = {
            'items': [
                {
                    'track': {
                        'name': 'Sweet Child O\' Mine',
                        'album': {'name': 'Appetite for Destruction'},
                        'artists': [{'name': 'Guns N\' Roses'}]
                    }
                },
                {
                    'track': {
                        'name': 'Stairway to Heaven',
                        'album': {'name': 'Led Zeppelin IV'},
                        'artists': [{'name': 'Led Zeppelin'}]
                    }
                }
            ]
        }

        # Mock search results
        self.mock_search_response = {
            'tracks': {
                'items': [
                    {
                        'name': 'Bohemian Rhapsody',
                        'id': 'track_123',
                        'album': {'name': 'A Night at the Opera'},
                        'artists': [{'name': 'Queen'}]
                    }
                ]
            }
        }

    @patch('src.spfyfuncs.spotipy.Spotify')
    @patch('src.spfyfuncs.spotipy.oauth2.SpotifyOAuth')
    def test_spotify_auth_success(self, mock_oauth, mock_spotify_class):
        """Test successful Spotify authentication."""
        mock_spotify_instance = Mock()
        mock_spotify_class.return_value = mock_spotify_instance

        with patch('src.spfyfuncs.message') as mock_message:
            result = spotify_auth()

            self.assertEqual(result, mock_spotify_instance)
            mock_message.assert_called_with("s+", "Successfully Authenticated")

    @patch('src.spfyfuncs.spotipy.Spotify')
    @patch('src.spfyfuncs.spotipy.oauth2.SpotifyOAuth')
    @patch('sys.exit')
    def test_spotify_auth_failure(self, mock_exit, mock_oauth, mock_spotify_class):
        """Test Spotify authentication failure."""
        mock_spotify_class.side_effect = Exception("Auth failed")

        with patch('src.spfyfuncs.message') as mock_message:
            spotify_auth()

            mock_message.assert_called_with("s+", "Authentication failed")
            mock_exit.assert_called_with(0)

    def test_get_spotify_playlists(self):
        """Test retrieving Spotify playlists."""
        self.mock_spotify.current_user_playlists.return_value = self.mock_playlists_response

        result = get_spotify_playlists(self.mock_spotify)

        expected = {
            'My Awesome Playlist': 'playlist_123',
            'Rock Collection': 'playlist_456',
            'Chill Vibes': 'playlist_789'
        }
        self.assertEqual(result, expected)
        self.mock_spotify.current_user_playlists.assert_called_once()

    def test_get_spotify_playlists_empty(self):
        """Test retrieving Spotify playlists when no playlists exist."""
        self.mock_spotify.current_user_playlists.return_value = {'items': []}

        result = get_spotify_playlists(self.mock_spotify)

        self.assertEqual(result, {})

    def test_get_spotify_playlists_malformed_response(self):
        """Test handling malformed response when retrieving playlists."""
        # The exception handling is only for the loop, not the API call
        self.mock_spotify.current_user_playlists.return_value = {'items': [{'invalid': 'data'}]}

        # The function has a try/except around the loop that catches key errors
        result = get_spotify_playlists(self.mock_spotify)

        # Should return empty dict when items don't have expected keys
        self.assertEqual(result, {})

    def test_get_spfy_likes(self):
        """Test retrieving Spotify liked songs."""
        self.mock_spotify.current_user_saved_tracks.return_value = self.mock_likes_response

        result = get_spfy_likes(self.mock_spotify)

        expected = [
            'A Night at the Opera&@#72Bohemian Rhapsody&@#72Queen',
            'Imagine&@#72Imagine&@#72John Lennon',
            'Hotel California&@#72Hotel California&@#72Eagles'
        ]
        self.assertEqual(result, expected)

    def test_get_spfy_likes_multiple_artists(self):
        """Test liked songs with multiple artists."""
        mock_response = {
            'total': 1,
            'items': [
                {
                    'track': {
                        'name': 'Under Pressure',
                        'album': {'name': 'Hot Space'},
                        'artists': [{'name': 'Queen'}, {'name': 'David Bowie'}]
                    }
                }
            ]
        }
        self.mock_spotify.current_user_saved_tracks.return_value = mock_response

        result = get_spfy_likes(self.mock_spotify)

        expected = ['Hot Space&@#72Under Pressure&@#72Queen David Bowie']
        self.assertEqual(result, expected)

    def test_spfy_dest_check_existing_playlist(self):
        """Test checking for existing destination playlist."""
        playlists = {'Test Playlist': 'playlist_123'}

        with patch('src.spfyfuncs.message') as mock_message:
            result = spfy_dest_check(playlists, self.mock_spotify, self.mock_user_id, 'Test Playlist')

            self.assertEqual(result, 'playlist_123')
            mock_message.assert_called_with("s+", "Playlist exists, adding missing songs")

    def test_spfy_dest_check_create_new_playlist(self):
        """Test creating new playlist when it doesn't exist."""
        playlists = {}
        mock_new_playlist = {'id': 'new_playlist_123'}
        self.mock_spotify.user_playlist_create.return_value = mock_new_playlist

        with patch('src.spfyfuncs.message') as mock_message:
            result = spfy_dest_check(playlists, self.mock_spotify, self.mock_user_id, 'New Playlist')

            self.assertEqual(result, 'new_playlist_123')
            self.mock_spotify.user_playlist_create.assert_called_with(
                self.mock_user_id, 'New Playlist', public=False,
                collaborative=False, description='Sound Tunnel Playlist'
            )
            mock_message.assert_called_with("s+", "Playlist created")

    @patch('src.spfyfuncs.get_spfy_playlist_content')
    @patch('src.spfyfuncs.what_to_move')
    @patch('src.spfyfuncs.tqdm')
    def test_move_to_spfy(self, mock_tqdm, mock_what_to_move, mock_get_content):
        """Test moving songs to Spotify playlist."""
        # Mock existing playlist content
        mock_get_content.return_value = []

        # Mock songs to move
        playlist_info = [
            'A Night at the Opera&@#72Bohemian Rhapsody&@#72Queen',
            'Imagine&@#72Imagine&@#72John Lennon'
        ]
        mock_what_to_move.return_value = playlist_info

        # Mock search results
        self.mock_spotify.search.return_value = self.mock_search_response

        # Mock tqdm to return the input directly
        mock_tqdm.return_value = playlist_info

        with patch('src.spfyfuncs.compare', return_value=True), \
             patch('src.spfyfuncs.sleep'):

            result = move_to_spfy(self.mock_spotify, playlist_info, 'playlist_123', 'Test Playlist')

            # Should call playlist_add_items
            self.mock_spotify.playlist_add_items.assert_called()

    @patch('src.spfyfuncs.get_spfy_playlist_content')
    @patch('src.spfyfuncs.what_to_move')
    @patch('src.spfyfuncs.tqdm')
    def test_move_to_spfy_song_not_found(self, mock_tqdm, mock_what_to_move, mock_get_content):
        """Test moving songs to Spotify when some songs are not found."""
        mock_get_content.return_value = []

        playlist_info = ['Unknown Album&@#72Unknown Song&@#72Unknown Artist']
        mock_what_to_move.return_value = playlist_info
        mock_tqdm.return_value = playlist_info

        # Mock empty search results
        self.mock_spotify.search.return_value = {'tracks': {'items': []}}

        result = move_to_spfy(self.mock_spotify, playlist_info, 'playlist_123', 'Test Playlist')

        # Should return the song that wasn't found
        self.assertEqual(result, ['Unknown Album Unknown Song Unknown Artist'])

    @patch('sys.exit')
    def test_move_to_spfy_keyboard_interrupt(self, mock_exit):
        """Test handling keyboard interrupt during move operation."""
        with patch('src.spfyfuncs.get_spfy_playlist_content', return_value=[]), \
             patch('src.spfyfuncs.what_to_move', return_value=['test']), \
             patch('src.spfyfuncs.tqdm', side_effect=KeyboardInterrupt()):

            move_to_spfy(self.mock_spotify, ['test'], 'playlist_123', 'Test Playlist')
            mock_exit.assert_called_with(0)


if __name__ == '__main__':
    unittest.main()
