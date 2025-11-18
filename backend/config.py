"""
Configuration module for backend services.
Loads sensitive configuration from environment variables or .env file.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Load .env file from project root if it exists
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    # python-dotenv not installed, fall back to environment variables only
    pass


def get_nass_api_key() -> str:
    """
    Get the USDA NASS API key from environment variables.
    
    Returns:
        str: The API key, or empty string if not set
        
    Raises:
        ValueError: If API key is required but not found (optional - can be handled by caller)
    """
    api_key = os.environ.get('NASS_API_KEY', '').strip()
    return api_key


def get_database_url() -> str:
    """
    Get the database URL from environment variables.
    
    Returns:
        str: The database URL, defaults to sqlite:///mlplayground.db
    """
    return os.environ.get('DATABASE_URL', 'sqlite:///mlplayground.db')

