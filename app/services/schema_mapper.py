import os
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

logger = logging.getLogger(__name__)

class SchemaMapper:
    """Service for mapping entity classes to database tables and analyzing their relationships."""
    
    # ORM annotations to identify table mappings
    TABLE_ANNOTATIONS = [
        r'@Table\s*\(\s*name\s*=\s*["\']([^"\']+)["\']',
        r'@Table\s*\(\s*value\s*=\s*["\']([^"\']+)["\']',
        r'@Entity\s*\(\s*name\s*=\s*["\']([^"\']+)["\']'
    ]
    
    # ORM annotations to identify relationships
    RELATIONSHIP_ANNOTATIONS = [
        r'@OneToMany',
        r'@ManyToOne',
        r'@OneToOne',
        r'@ManyToMany',
        r'@JoinColumn',
        r'@JoinTable'
    ]
    
    # Annotations to identify foreign keys
    JOIN_COLUMN_PATTERN = r'@JoinColumn\s*\(\s*name\s*=\s*["\']([^"\']+)["\']'
    
    def __init__(self):
        self.controller_entity_map = {}  # Maps controllers to entities they use
    
    def map_schema(self, repo_path: str, entities: Dict[str, Any], endpoints: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Map entities to database tables and identify their relationships.
        
        Args:
            repo_path: Path to the repository
            entities: Entity data from entity parser
            endpoints: Endpoint data from endpoint parser
            
        Returns:
            Dictionary containing table mappings and relationships
        """
        logger.info(f"Mapping schema for repository at: {repo_path}")
        
        table_mappings = {}
        
        # Process each entity
        for entity_name, entity_data in entities.get("entities", {}).items():
            # Map entity to database table
            table_name = self._extract_table_name(entity_data)
            
            # If no table annotation found, use entity name with snake_case conversion
            if not table_name:
                table_name = self._to_snake_case(entity_name)
            
            # Extract relationships
            relationships = self._extract_relationships(entity_data)
            
            # Find which endpoints use this entity
            used_by = self._find_entity_usage(entity_name, endpoints)
            
            # Store the table mapping
            table_mappings[table_name] = {
                "entity": entity_name,
                "used_by": used_by,
                "relations": relationships
            }
        
        return {
            "tables": table_mappings,
            "entities": entities.get("entities", {})
        }
    
    def _extract_table_name(self, entity_data: Dict[str, Any]) -> Optional[str]:
        """Extract table name from entity annotations."""
        annotations = entity_data.get("annotations", [])
        
        for annotation in annotations:
            for pattern in self.TABLE_ANNOTATIONS:
                match = re.search(pattern, annotation)
                if match:
                    return match.group(1)
        
        # If no explicit table name found, check if there's an Entity annotation without a name
        for annotation in annotations:
            if re.search(r'@Entity\b', annotation) and not re.search(r'@Entity\s*\(', annotation):
                return None  # Will use default naming based on entity name
        
        return None
    
    def _extract_relationships(self, entity_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract relationship information from entity fields."""
        relationships = []
        fields = entity_data.get("fields", [])
        
        for field in fields:
            field_type = field.get("type", "")
            field_name = field.get("name", "")
            annotations = field.get("annotations", [])
            
            # Check for relationship annotations
            relation_type = None
            target_entity = None
            
            for annotation in annotations:
                for rel_pattern in self.RELATIONSHIP_ANNOTATIONS:
                    if re.search(rel_pattern, annotation):
                        relation_type = rel_pattern.replace('@', '')
                        break
                
                if relation_type:
                    break
            
            # If a relationship annotation was found, extract the target entity
            if relation_type:
                # Try to extract from field type
                if "List<" in field_type:
                    # Extract from generics
                    match = re.search(r'List<([^>]+)>', field_type)
                    if match:
                        target_entity = match.group(1)
                elif "Set<" in field_type:
                    match = re.search(r'Set<([^>]+)>', field_type)
                    if match:
                        target_entity = match.group(1)
                else:
                    # Use the field type directly
                    target_entity = field_type
                
                # Extract join column if available
                join_column = None
                for annotation in annotations:
                    match = re.search(self.JOIN_COLUMN_PATTERN, annotation)
                    if match:
                        join_column = match.group(1)
                        break
                
                relationships.append({
                    "type": relation_type,
                    "field": field_name,
                    "target_entity": target_entity,
                    "join_column": join_column
                })
        
        # Convert entity names to table names
        relationship_tables = []
        for rel in relationships:
            if rel.get("target_entity"):
                target_table = self._to_snake_case(rel["target_entity"])
                relationship_tables.append(target_table)
        
        return relationship_tables
    
    def _find_entity_usage(self, entity_name: str, endpoints: List[Dict[str, Any]]) -> List[str]:
        """Find which endpoints use this entity."""
        used_by = []
        
        for endpoint in endpoints:
            path = endpoint.get("path", "")
            # Simple heuristic: check if the entity name appears in the path (lowercase)
            entity_lower = entity_name.lower()
            if entity_lower in path.lower():
                used_by.append(path)
        
        return used_by
    
    def _to_snake_case(self, camel_case: str) -> str:
        """Convert CamelCase to snake_case."""
        # Replace non-alphanumeric characters with underscore
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_case)
        # Insert underscore between lowercase and uppercase letters
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
        # Convert to lowercase
        return s2.lower() 