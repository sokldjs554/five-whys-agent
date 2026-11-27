"""Compatibility entry point for the existing OpenAI workflow."""
import asyncio
import sys
from pathlib import Path

from record_desk_provider import main


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), "openai"))
