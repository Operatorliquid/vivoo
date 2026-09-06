#!/usr/bin/env python3
"""Development wrapper for the packaged MediaMTX supervisor."""

from pathlib import Path
import sys

from runtime.relay import (  # noqa: E402,F401
    StreamProgress,
    camera_url,
    desired_relay_sources,
    relay_sample,
    sample_has_reader,
    supervise,
)


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: run_mediamtx.py AGENT_CONFIG MEDIAMTX_BIN MEDIAMTX_CONFIG")
    agent_config, binary, relay_config = map(Path, sys.argv[1:])
    raise SystemExit(supervise(agent_config, binary, relay_config))


if __name__ == "__main__":
    main()
