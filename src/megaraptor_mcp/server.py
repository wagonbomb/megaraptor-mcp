"""
Megaraptor MCP Server - Main entry point.

An MCP server that provides access to Velociraptor DFIR capabilities.
"""

import asyncio
import logging
import sys
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server

from . import __version__
from .tools import (
    register_client_tools,
    register_artifact_tools,
    register_hunt_tools,
    register_flow_tools,
    register_vql_tools,
)
from .resources import register_resources
from .prompts import register_prompts

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("megaraptor-mcp")


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("megaraptor-mcp")

    # Register all tools
    logger.info("Registering client management tools...")
    register_client_tools(server)

    logger.info("Registering artifact tools...")
    register_artifact_tools(server)

    logger.info("Registering hunt tools...")
    register_hunt_tools(server)

    logger.info("Registering flow tools...")
    register_flow_tools(server)

    logger.info("Registering VQL tools...")
    register_vql_tools(server)

    # Register resources
    logger.info("Registering resources...")
    register_resources(server)

    # Register prompts
    logger.info("Registering prompts...")
    register_prompts(server)

    return server


async def run_server() -> None:
    """Run the MCP server."""
    logger.info(f"Starting Megaraptor MCP Server v{__version__}")

    server = create_server()

    # Run with stdio transport
    async with stdio_server() as (read_stream, write_stream):
        logger.info("Server started, waiting for connections...")
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Main entry point."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
