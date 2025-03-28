import json
import base64
import logging
from typing import Any, TypedDict
from datetime import datetime
import aiohttp

class SchemaConfig(TypedDict):
    """Configuration for connecting to a schema API endpoint"""
    url: str
    username: str
    password: str

class SchemaResult(TypedDict):
    """Schema information returned from the API"""
    summary: str
    source: str
    schema: Any
    schema_endpoint: str
    timestamp: str

async def fetch_schema_from_endpoint(config: SchemaConfig) -> SchemaResult:
    """Fetches schema information from a remote endpoint
    
    Args:
        config: Configuration for the schema endpoint
        
    Returns:
        Schema information
        
    Raises:
        aiohttp.ClientError: If there's an error fetching the schema
        ValueError: If the response is not valid JSON
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Fetching schema from endpoint: {config['url']}")
    
    try:
        # Create basic auth credentials
        credentials = f"{config['username']}:{config['password']}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Accept': 'application/json'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(config['url'], headers=headers) as response:
                if response.status != 200:
                    raise aiohttp.ClientError(
                        f"HTTP error! Status: {response.status}"
                    )
                
                schema_data = await response.json()
                logger.info("Successfully fetched schema from endpoint")
                
                return {
                    "summary": "PuppyGraph Schema Information",
                    "source": "Schema API",
                    "schema": schema_data,
                    "schema_endpoint": config['url'],
                    "timestamp": datetime.now().isoformat()
                }
                
    except Exception as e:
        logger.error(f"Error fetching schema from endpoint: {str(e)}")
        raise

# Example usage:
# config = {
#     'url': 'http://localhost:8081/schemajson',
#     'username': 'puppygraph',
#     'password': 'puppygraph123'
# }
# schema = await fetch_schema_from_endpoint(config)