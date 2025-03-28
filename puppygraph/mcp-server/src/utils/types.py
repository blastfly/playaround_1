from typing import Generic, TypeVar, Optional, TypedDict

T = TypeVar('T')

class QueryResultMetadata(TypedDict):
    """Metadata about the query execution"""
    execution_time: int  # Time taken to execute the query in milliseconds
    row_count: int       # Number of rows/records returned
    error: Optional[str]  # Error message if there was an error
    error_type: Optional[str]  # Type of error that occurred

class QueryResult(TypedDict, Generic[T]):
    """Represents the result of a graph database query
    
    Attributes:
        data: The data returned from the query
        metadata: Metadata about the query execution
    """
    data: list[T]
    metadata: QueryResultMetadata