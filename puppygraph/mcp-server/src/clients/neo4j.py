import logging
from typing import Dict, Any, Optional, List
from neo4j import GraphDatabase, Driver, Session, basic_auth
from neo4j.data import Record, Node, Relationship, Path
from neo4j.exceptions import Neo4jError

class Neo4jConfig(TypedDict):
    url: str
    username: str
    password: str
    database: str

class Neo4jClient:
    def __init__(self, config: Neo4jConfig):
        self.config = config
        self.driver: Optional[Driver] = None
        self.connected = False
        self.connection_error: Optional[str] = None
        self.logger = logging.getLogger(__name__)

    async def connect(self) -> bool:
        try:
            self.logger.info('Initializing connection to Neo4j endpoint...')
            
            self.driver = GraphDatabase.driver(
                self.config['url'],
                auth=basic_auth(
                    self.config['username'],
                    self.config['password']
                ),
                # Disable lossless integers to convert to Python int automatically
                integer_conversion=True
            )
            
            await self.verify_connection()
            self.connected = True
            self.logger.info('Successfully connected to Neo4j endpoint')
            return True
        except Exception as e:
            self.connection_error = str(e)
            self.logger.error(f'Failed to initialize Neo4j connection: {str(e)}')
            self.connected = False
            return False

    async def verify_connection(self) -> None:
        if not self.driver:
            raise Exception('Neo4j driver not initialized')
        
        session = None
        try:
            self.logger.info('Testing Neo4j connection with basic query...')
            session = self.get_session()
            await session.run('RETURN 1 as result')
            self.logger.info('Neo4j connection verified')
        except Exception as e:
            self.logger.error(f'Neo4j connection verification failed: {str(e)}')
            raise
        finally:
            if session:
                await session.close()

    def get_session(self) -> Session:
        if not self.driver:
            raise Exception('Neo4j driver not initialized')
        
        if 'database' in self.config and self.config['database']:
            return self.driver.session(database=self.config['database'])
        return self.driver.session()

    def is_connected(self) -> bool:
        return self.connected

    def get_connection_error(self) -> Optional[str]:
        return self.connection_error

    async def execute_query(self, cypher: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if not self.connected or not self.driver:
            raise Exception('Not connected to Neo4j endpoint')
        
        parameters = parameters or {}
        session = None
        try:
            session = self.get_session()
            result = await session.run(cypher, parameters)
            records = await result.list()
            return [self.convert_record(record) for record in records]
        finally:
            if session:
                await session.close()

    def convert_record(self, record: Record) -> Dict[str, Any]:
        obj: Dict[str, Any] = {}
        for key in record.keys():
            obj[key] = self.convert_value(record[key])
        return obj

    def convert_value(self, value: Any) -> Any:
        if value is None:
            return value
        
        if isinstance(value, (Node, Relationship, Path)):
            return self.convert_neo4j_entity(value)
        
        if isinstance(value, list):
            return [self.convert_value(item) for item in value]
        
        if isinstance(value, dict):
            return self.convert_properties(value)
        
        return value

    def convert_neo4j_entity(self, entity: Any) -> Dict[str, Any]:
        if isinstance(entity, Node):
            return {
                'id': self.convert_value(entity.id),
                'labels': list(entity.labels),
                'properties': self.convert_properties(dict(entity))
            }
        
        if isinstance(entity, Relationship):
            return {
                'id': self.convert_value(entity.id),
                'type': entity.type,
                'startNodeId': self.convert_value(entity.start_node.id),
                'endNodeId': self.convert_value(entity.end_node.id),
                'properties': self.convert_properties(dict(entity))
            }
        
        if isinstance(entity, Path):
            return {
                'segments': [{
                    'start': self.convert_value(segment.start_node),
                    'relationship': self.convert_value(segment.relationship),
                    'end': self.convert_value(segment.end_node)
                } for segment in entity]
            }
        
        return self.convert_value(entity)

    def convert_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        return {key: self.convert_value(value) for key, value in properties.items()}

    async def close(self) -> None:
        if self.driver:
            await self.driver.close()
            self.driver = None
            self.connected = False
            self.logger.info('Neo4j connection closed')