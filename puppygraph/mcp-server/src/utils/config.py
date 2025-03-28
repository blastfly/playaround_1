import os
from typing import TypedDict, Optional

class Neo4jConfig(TypedDict):
    url: str
    username: str
    password: str
    database: str

class GremlinConfig(TypedDict):
    url: str
    username: str
    password: str
    traversal_source: str

class SchemaConfig(TypedDict):
    url: str
    username: str
    password: str

class PuppyGraphConfig(TypedDict):
    """Complete configuration for the PuppyGraph MCP server"""
    neo4j: Neo4jConfig
    gremlin: GremlinConfig
    schema: SchemaConfig

def load_config() -> PuppyGraphConfig:
    """Loads configuration from environment variables with fallbacks to defaults
    
    Environment variables:
    - PUPPYGRAPH_URL: Neo4j Bolt URL
    - PUPPYGRAPH_USERNAME: Neo4j username
    - PUPPYGRAPH_PASSWORD: Neo4j password
    - PUPPYGRAPH_DATABASE: Neo4j database name
    - PUPPYGRAPH_GREMLIN_URL: Gremlin WebSocket URL
    - PUPPYGRAPH_GREMLIN_USERNAME: Gremlin username
    - PUPPYGRAPH_GREMLIN_PASSWORD: Gremlin password
    - PUPPYGRAPH_GREMLIN_TRAVERSAL_SOURCE: Gremlin traversal source
    - PUPPYGRAPH_SCHEMA_URL: Schema API URL
    - PUPPYGRAPH_SCHEMA_USERNAME: Schema API username
    - PUPPYGRAPH_SCHEMA_PASSWORD: Schema API password
    
    Returns:
        Complete PuppyGraph configuration
    """
    return {
        "neo4j": {
            "url": os.getenv("PUPPYGRAPH_URL", "bolt://localhost:7687"),
            "username": os.getenv("PUPPYGRAPH_USERNAME", "neo4j"),
            "password": os.getenv("PUPPYGRAPH_PASSWORD", "password"),
            "database": os.getenv("PUPPYGRAPH_DATABASE", "")
        },
        "gremlin": {
            "url": os.getenv("PUPPYGRAPH_GREMLIN_URL", "ws://localhost:8182/gremlin"),
            "username": os.getenv("PUPPYGRAPH_GREMLIN_USERNAME", "puppygraph"),
            "password": os.getenv("PUPPYGRAPH_GREMLIN_PASSWORD", "puppygraph123"),
            "traversal_source": os.getenv("PUPPYGRAPH_GREMLIN_TRAVERSAL_SOURCE", "g")
        },
        "schema": {
            "url": os.getenv("PUPPYGRAPH_SCHEMA_URL", "http://localhost:8081/schemajson"),
            "username": os.getenv("PUPPYGRAPH_SCHEMA_USERNAME", "puppygraph"),
            "password": os.getenv("PUPPYGRAPH_SCHEMA_PASSWORD", "puppygraph123")
        }
    }