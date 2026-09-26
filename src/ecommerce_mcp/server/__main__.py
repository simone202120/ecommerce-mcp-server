"""Entry point: `python -m ecommerce_mcp.server [--transport stdio|streamable-http]`."""

import argparse
import logging

from ecommerce_mcp.config import get_settings
from ecommerce_mcp.server.app import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only e-commerce MCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="stdio for Claude Desktop (default), streamable-http for the agent and Docker.",
    )
    args = parser.parse_args()
    # Logs go to stderr: with stdio, stdout carries the MCP protocol.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    create_server(get_settings()).run(transport=args.transport)


if __name__ == "__main__":
    main()
