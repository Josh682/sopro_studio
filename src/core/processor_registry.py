"""Registry for discovering and instantiating processors."""

from typing import Type

from src.core.processors.base_processor import BaseProcessor, ProcessorMetadata

class ProcessorRegistry:
    """Singleton registry for discovering and instantiating processors."""
    
    _instance = None
    _processors: dict[str, Type[BaseProcessor]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, processor_class: Type[BaseProcessor]) -> None:
        """Register a processor class."""
        cls._processors[processor_class.metadata.id] = processor_class

    @classmethod
    def get_processor_class(cls, processor_id: str) -> Type[BaseProcessor]:
        """Retrieve a processor class by ID."""
        if processor_id not in cls._processors:
            raise KeyError(f"Processor '{processor_id}' not found in registry.")
        return cls._processors[processor_id]

    @classmethod
    def get_processor(cls, processor_id: str, *args, **kwargs) -> BaseProcessor:
        """Instantiate a processor by ID."""
        return cls.get_processor_class(processor_id)(*args, **kwargs)
        
    @classmethod
    def list_processors(cls) -> list[ProcessorMetadata]:
        """List metadata for all registered processors."""
        return [p.metadata for p in cls._processors.values()]
