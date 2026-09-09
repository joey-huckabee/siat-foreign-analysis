"""Process exit codes.

Distinct codes so a caller driving this from a shell can tell a bad
configuration from unreadable input without parsing the log.
"""

from typing import Final

EXIT_OK: Final = 0
"""Every discovered input was scored and every report was written."""

EXIT_CONFIG_ERROR: Final = 2
"""The country configuration was missing, malformed, or incomplete."""

EXIT_INPUT_ERROR: Final = 3
"""An input document could not be read, decoded, or was missing a field."""

EXIT_OUTPUT_ERROR: Final = 4
"""The output directory or one of the four reports could not be written."""
