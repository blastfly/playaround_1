import asyncio
import logging
from typing import Dict, Any, Optional, TypedDict
from datetime import datetime
import signal
from neo4j import GraphDatabase
from gremlin_python.driver import client, driver

class QueryResultMetadata(TypedDict):
    execution_time: int
    row_count: int

class QueryResult(TypedDict):
    data: list
    metadata: QueryResultMetadata

class ConnectionStatus(TypedDict):
    connected: bool
    neo4j_connected: bool
    gremlin_connected: bool
    connection_error: Optional[str]
    fallback_mode: bool

class PuppyGraphService:
    def __init__(self):
        from clients.neo4j import Neo4jClient
        from clients.gremlin import GremlinClient
        from utils.config import load_config
        from utils.schema import fetch_schema_from_endpoint

        self.config = load_config()
        self.connection_error: Optional[str] = None
        self.logger = logging.getLogger(__name__)

        self.logger.info(f"PuppyGraph Neo4j service initialized with URL: {self.config['neo4j']['url']}")
        self.logger.info(f"PuppyGraph Gremlin service initialized with URL: {self.config['gremlin']['url']}")
        self.logger.info(f"Using database: {self.config['neo4j'].get('database', 'default')}")

        self.neo4j_client = Neo4jClient(self.config['neo4j'])
        self.gremlin_client = GremlinClient(self.config['gremlin'])

        asyncio.create_task(self.initialize())

        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        asyncio.create_task(self.close())

    async def initialize(self) -> None:
        try:
            await self.neo4j_client.connect()
        except Exception as e:
            self.logger.error(f'Neo4j connection initialization error: {str(e)}')

        try:
            await self.gremlin_client.connect()
        except Exception as e:
            self.logger.error(f'Gremlin connection initialization error: {str(e)}')

        self.update_connection_error()

        if not self.neo4j_client.is_connected() and not self.gremlin_client.is_connected():
            self.logger.error('All connection attempts failed')

    def update_connection_error(self) -> None:
        neo4j_error = self.neo4j_client.get_connection_error()
        gremlin_error = self.gremlin_client.get_connection_error()

        if neo4j_error and gremlin_error:
            self.connection_error = f"Neo4j: {neo4j_error} | Gremlin: {gremlin_error}"
        elif neo4j_error:
            self.connection_error = f"Neo4j: {neo4j_error}"
        elif gremlin_error:
            self.connection_error = f"Gremlin: {gremlin_error}"
        else:
            self.connection_error = None

    async def execute_gremlin(self, params: Dict[str, Any]) -> QueryResult:
        query = params['query']
        query_params = params.get('parameters', {})

        self.logger.info(f"Executing Gremlin query: {query}")
        self.logger.info(f"Parameters: {query_params}")

        if not self.gremlin_client.is_connected():
            self.logger.info('Not connected to Gremlin endpoint, attempting to reconnect...')
            reconnected = await self.gremlin_client.connect()
            self.update_connection_error()

            if not reconnected:
                self.logger.error('Gremlin reconnection failed')
                raise Exception(f"Cannot execute Gremlin query: Not connected to Gremlin endpoint. {self.connection_error or ''}")

        start_time = datetime.now().timestamp() * 1000  # milliseconds

        try:
            result = await self.gremlin_client.execute_query(query, query_params)
            execution_time = int(datetime.now().timestamp() * 1000 - start_time)

            self.logger.info(f"Gremlin query executed successfully, returned {len(result)} items")

            return {
                "data": result,
                "metadata": {
                    "execution_time": execution_time,
                    "row_count": len(result)
                }
            }
        except Exception as e:
            self.logger.error(f'Error executing Gremlin query: {str(e)}')
            raise Exception(f"Error executing Gremlin query: {str(e)}")

    async def execute_cypher(self, params: Dict[str, Any]) -> QueryResult:
        query = params['query']
        query_params = params.get('parameters', {})

        self.logger.info(f"Executing Cypher query: {query}")
        self.logger.info(f"Parameters: {query_params}")

        if not self.neo4j_client.is_connected():
            self.logger.info('Not connected to Neo4j endpoint, attempting to reconnect...')
            reconnected = await self.neo4j_client.connect()
            self.update_connection_error()

            if not reconnected:
                self.logger.error('Neo4j reconnection failed')
                raise Exception(f"Cannot execute Cypher query: Not connected to Neo4j endpoint. {self.connection_error or ''}")

        start_time = datetime.now().timestamp() * 1000  # milliseconds

        try:
            records = await self.neo4j_client.execute_query(query, query_params)
            execution_time = int(datetime.now().timestamp() * 1000 - start_time)

            self.logger.info(f"Cypher query executed successfully, returned {len(records)} records")

            return {
                "data": records,
                "metadata": {
                    "execution_time": execution_time,
                    "row_count": len(records)
                }
            }
        except Exception as e:
            self.logger.error(f'Error executing Cypher query: {str(e)}')
            raise Exception(f"Error executing Cypher query: {str(e)}")

    async def get_data_sources(self) -> Dict[str, Any]:
        self.logger.info("Fetching data sources information")

        try:
            from utils.schema import fetch_schema_from_endpoint
            return await fetch_schema_from_endpoint(self.config['schema'])
        except Exception as schema_error:
            self.logger.info(f'Schema endpoint failed, falling back to database queries: {str(schema_error)}')

        if not self.neo4j_client.is_connected():
            self.logger.info('Not connected to Neo4j endpoint, attempting to reconnect...')
            reconnected = await self.neo4j_client.connect()
            self.update_connection_error()

            if not reconnected:
                self.logger.info('Neo4j reconnection failed, trying Gremlin endpoint')

                if not self.gremlin_client.is_connected():
                    gremlin_connected = await self.gremlin_client.connect()
                    self.update_connection_error()

                    if not gremlin_connected:
                        self.logger.error('Both Neo4j and Gremlin connections failed')
                        raise Exception('Cannot fetch schema: Not connected to any endpoint. ' + (self.connection_error or ''))

                try:
                    return await self.gremlin_client.get_schema_data()
                except Exception as gremlin_error:
                    self.logger.error(f'Gremlin schema query failed: {str(gremlin_error)}')
                    raise Exception('Failed to fetch schema via Gremlin: ' + str(gremlin_error))

        try:
            schema_data = await self.neo4j_client.execute_query('MATCH (n) RETURN count(n) as count')
            return {
                "summary": "Graph Structure Information via Neo4j",
                "node_count": schema_data[0]['count'],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as error:
            self.logger.error('Failed to get data sources via Neo4j')
            raise Exception('Failed to fetch database schema: ' + str(error))

    def get_connection_status(self) -> ConnectionStatus:
        neo4j_connected = self.neo4j_client.is_connected()
        gremlin_connected = self.gremlin_client.is_connected()

        return {
            "connected": neo4j_connected or gremlin_connected,
            "neo4j_connected": neo4j_connected,
            "gremlin_connected": gremlin_connected,
            "connection_error": self.connection_error,
            "fallback_mode": False
        }

    async def close(self) -> None:
        await asyncio.gather(
            self.neo4j_client.close(),
            self.gremlin_client.close()
        )
        self.logger.info('PuppyGraph connections closed')

# Singleton instance
puppy_graph_service = PuppyGraphService()