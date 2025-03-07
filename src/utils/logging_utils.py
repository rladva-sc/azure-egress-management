"""
Logging utilities for Azure Egress Management.
"""
import logging
import os
from pathlib import Path
from datetime import datetime

def setup_logging(config=None, log_to_file=True):
    """
    Set up logging with the specified configuration.
    
    Args:
        config (dict, optional): Configuration with logging settings
        log_to_file (bool): Whether to log to a file
        
    Returns:
        logging.Logger: Configured logger instance
    """
    config = config or {}
    log_level = config.get('logging', {}).get('level', 'INFO')
    log_file = config.get('logging', {}).get('file', 'egress_management.log')
    
    # Convert string log level to actual level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    
    # Create logs directory if it doesn't exist
    if log_to_file:
        log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / log_file
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            *([] if not log_to_file else [logging.FileHandler(log_path)])
        ]
    )
    
    return logging.getLogger(__name__)
