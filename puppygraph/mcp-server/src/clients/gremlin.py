import asyncio
from typing import Dict, Any, Optional, List
import logging
from gremlin_python.driver import client, protocol, serializer
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import GraphTraversalSource
from gremlin_python.structure.graph import Graph

class GremlinConfig(TypedDict):
    url: str
    username: str
    password: str
    traversal_source: str

class GremlinClient:
    def __init__(self, config: GremlinConfig):
        self.config = config
        self.client = None
        self.connection = None
        self.g: Optional[GraphTraversalSource] = None
        self.connected = False
        self.connection_error: Optional[str] = None
        self.logger = logging.getLogger(__name__)

    async def connect(self) -> bool:
        try:
            self.logger.info('Initializing connection to Gremlin endpoint...')
            self.logger.info(f"URL: {self.config['url']}, TraversalSource: {self.config['traversal_source']}")
            
            url = self.config['url']
            if not url.startswith('ws://') and not url.startswith('wss://'):
                self.logger.warning('Gremlin URL should typically start with ws:// or wss:// for WebSocket connections')
                self.logger.warning(f'Current URL: {url}')
            
            options = {
                'traversal_source': self.config['traversal_source']
            }
            
            if self.config.get('username') and self.config.get('password'):
                options.update({
                    'username': self.config['username'],
                    'password': self.config['password']
                })
                self.logger.info('Using username/password for authentication')
            else:
                self.logger.info('No Gremlin credentials provided, attempting connection without authentication')
            
            # Try standard approach with Graph and traversal
            try:
                self.logger.info('Attempting standard Graph traversal approach')
                graph = Graph()
                self.connection = DriverRemoteConnection(
                    url,
                    self.config['traversal_source'],
                    username=self.config.get('username'),
                    password=self.config.get('password')
                )
                self.g = graph.traversal().withRemote(self.connection)
                
                # Test connection
                self.logger.info('Testing connection with a simple query...')
                result = await self.g.V().limit(1).count().next()
                self.logger.info(f'Connection test successful, result: {result}')
                
                self.connected = True
                self.logger.info('Successfully initialized Gremlin connection using standard approach')
                return True
            except Exception as e:
                self.logger.warning(f'Standard approach failed: {str(e)}')
            
            # Fallback to direct client approach
            try:
                self.logger.info('Falling back to direct client approach')
                self.client = client.Client(
                    url,
                    'g',
                    username=self.config.get('username'),
                    password=self.config.get('password'),
                    message_serializer=serializer.GraphSONSerializersV2d0()
                )
                
                # Test connection
                test_result = await self.client.submit('g.V().limit(1).count()')
                count = test_result.all().result()[0]
                self.logger.info(f'Connection test successful with direct client, result: {count}')
                
                self.connected = True
                self.logger.info('Successfully initialized Gremlin client using fallback approach')
                return True
            except Exception as e:
                self.logger.warning(f'Direct client approach failed: {str(e)}')
            
            raise Exception(f"Could not establish connection to Gremlin server at {url}. Please verify the server is running and the URL is correct.")
            
        except Exception as e:
            self.connection_error = str(e)
            self.logger.error(f'Failed to initialize Gremlin connection: {str(e)}')
            self.connected = False
            return False

    def is_connected(self) -> bool:
        return self.connected

    def get_connection_error(self) -> Optional[str]:
        return self.connection_error

    async def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Any]:
        if not self.connected or (self.client is None and self.g is None):
            raise Exception('Not connected to Gremlin endpoint')
        
        parameters = parameters or {}
        result = None
        
        # Standard approach with graph traversal
        if self.g is not None:
            self.logger.info('Executing query via graph.traversal')
            
            if query.strip().startswith('g.'):
                # Security check
                if any(term in query for term in ['System.', 'java.', 'eval(', 'constructor']):
                    raise Exception('Potentially unsafe Gremlin query rejected')
                
                # Create a function that executes the query
                def execute_traversal(g):
                    return eval(query)  # Note: eval is dangerous, but we've done security checks
                
                traversal = execute_traversal(self.g)
                result = await traversal.toList()
            else:
                raise Exception('Query does not start with g. - cannot execute as traversal')
        
        # Direct client approach
        elif self.client is not None:
            self.logger.info('Executing query via client.submit')
            result = await self.client.submit(query, parameters)
            result = result.all().result()
        
        else:
            raise Exception('No valid Gremlin execution method available')
        
        return result

    async def get_schema_data(self) -> Dict[str, Any]:
        if not self.connected or (self.client is None and self.g is None):
            raise Exception('Gremlin client not initialized')
        
        result = None
        
        # Standard approach with graph traversal
        if self.g is not None:
            self.logger.info('Getting schema data via graph.traversal')
            
            node_count = await self.g.V().count().next()
            edge_count = await self.g.E().count().next()
            label_results = await self.g.V().label().groupCount().next()
            edge_results = await self.g.E().label().groupCount().next()
            
            node_labels = [{'label': label, 'count': int(count)} 
                          for label, count in label_results.value.items()]
            
            edge_labels = [{'type': label, 'count': int(count)} 
                          for label, count in edge_results.value.items()]
            
            result = {
                'summary': "Graph Structure Information",
                'source': "Gremlin Database Queries",
                'totalNodes': node_count.value,
                'totalRelationships': edge_count.value,
                'nodeLabels': node_labels,
                'relationshipTypes': edge_labels,
                'graphType': "PuppyGraph SQL-to-Graph Bridge"
            }
        
        # Direct client approach
        elif self.client is not None:
            self.logger.info('Getting schema data via client.submit')
            
            node_count = await self.client.submit('g.V().count()')
            node_count_value = (await node_count.all().result())[0]
            
            edge_count = await self.client.submit('g.E().count()')
            edge_count_value = (await edge_count.all().result())[0]
            
            label_query = await self.client.submit('g.V().groupCount().by(label)')
            label_results = (await label_query.all().result())[0]
            
            edge_query = await self.client.submit('g.E().groupCount().by(label)')
            edge_results = (await edge_query.all().result())[0]
            
            node_labels = [{'label': label, 'count': int(count)} 
                          for label, count in label_results.items()]
            
            edge_labels = [{'type': label, 'count': int(count)} 
                          for label, count in edge_results.items()]
            
            result = {
                'summary': "Graph Structure Information",
                'source': "Gremlin Database Queries",
                'totalNodes': node_count_value,
                'totalRelationships': edge_count_value,
                'nodeLabels': node_labels,
                'relationshipTypes': edge_labels,
                'graphType': "PuppyGraph SQL-to-Graph Bridge"
            }
        
        else:
            raise Exception('No valid Gremlin execution method available for schema queries')
        
        return result

    async def close(self) -> None:
        if self.connection is not None:
            try:
                await self.connection.close()
                self.logger.info('Gremlin connection closed')
            except Exception as e:
                self.logger.error(f'Error closing Gremlin connection: {str(e)}')
            self.connection = None
        
        if self.client is not None:
            try:
                await self.client.close()
                self.logger.info('Gremlin client closed')
            except Exception as e:
                self.logger.error(f'Error closing Gremlin client: {str(e)}')
            self.client = None
        
        self.g = None
        self.connected = False