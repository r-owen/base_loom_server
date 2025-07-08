from base_loom_server.example_mock_loom import ExampleMockLoom
from base_loom_server.main import app
from base_loom_server.testutils import BaseTestLoomServer

# Speed up tests
ExampleMockLoom.motion_duration = 0.1


class TestLoomServer(BaseTestLoomServer):
    """Run the standard loom server unit tests."""

    app = app
