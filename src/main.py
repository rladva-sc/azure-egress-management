"""
Entry point for the Azure Egress Management application.
"""
import sys
from .cli import app

def main():
    """Main application entry point."""
    app()

if __name__ == "__main__":
    sys.exit(main())
