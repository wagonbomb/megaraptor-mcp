"""
Megaraptor MCP Server - Main entry point.

An MCP server that provides access to Velociraptor DFIR capabilities.
"""

import asyncio
import logging
import sys

from mcp.server.fastmcp import FastMCP

from . import __version__

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("megaraptor-mcp")

# Create module-level FastMCP instance
# Tools, resources, and prompts register via decorators on import
mcp = FastMCP("megaraptor-mcp")


def _register_all() -> None:
    """Import all tool/resource/prompt modules to trigger registration."""
    # Import tools - this registers them via @mcp.tool() decorators
    from . import tools  # noqa: F401

    # Import resources - this registers them via @mcp.resource() decorators
    from . import resources  # noqa: F401

    # Import prompts - this registers them via @mcp.prompt() decorators
    from . import prompts  # noqa: F401

    logger.info("All tools, resources, and prompts registered")


async def run_server() -> None:
    """Run the MCP server."""
    logger.info(f"Starting Megaraptor MCP Server v{__version__}")

    # Register all tools/resources/prompts
    _register_all()

    # Run with stdio transport
    await mcp.run_stdio_async()


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
