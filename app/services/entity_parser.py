import os
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class EntityRelationship:
    def __init__(self, field_name: str, field_type: str, relationship_type: str, target_entity: str):
        self.field_name = field_name
        self.field_type = field_type
        self.relationship_type = relationship_type  # OneToMany, ManyToOne, etc.
        self.target_entity = target_entity
        
class EntityField:
    def __init__(self, name: str, type_name: str, is_relationship: bool = False):
        self.name = name
        self.type_name = type_name
        self.is_relationship = is_relationship

class EntityClass:
    def __init__(self, name: str):
        self.name = name
        self.fields: List[EntityField] = []
        self.relationships: List[EntityRelationship] = []

class EntityParser:
    """Parses Java entity classes to extract their properties and relationships."""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.entities = {}
        self.count = 0
        
        # Common database-related annotations
        self.db_annotations = [
            '@Entity', '@Table', '@Column', '@Id', '@GeneratedValue', 
            '@OneToMany', '@ManyToOne', '@OneToOne', '@ManyToMany',
            '@JoinColumn', '@JoinTable', '@Embeddable', '@Embedded'
        ]
    
    def parse_entities(self) -> Dict[str, Any]:
        """
        Parse all entities in the repository.
        
        Returns:
            Dictionary containing all entities and their details
        """
        logger.info(f"Parsing entities in repository: {self.repo_path}")
        
        # Find all Java files
        java_files = []
        for root, _, files in os.walk(self.repo_path):
            for file in files:
                if file.endswith(".java"):
                    java_files.append(os.path.join(root, file))
        
        logger.info(f"Found {len(java_files)} Java files to analyze")
        
        # Parse each Java file to find entities
        for java_file in java_files:
            try:
                self._parse_file(java_file)
            except Exception as e:
                logger.error(f"Error parsing file {java_file}: {str(e)}")
        
        logger.info(f"Found {self.count} entities")
        
        # Return the results
        return {
            "entities": self.entities,
            "count": self.count
        }
    
    def _parse_file(self, file_path: str) -> None:
        """
        Parse a Java file to extract entity information.
        
        Args:
            file_path: Path to the Java file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        
        # Check if this is an entity class
        is_entity = False
        has_db_annotations = False
        
        # Check for Entity annotation
        if re.search(r'@Entity\b', content):
            is_entity = True
        
        # If not explicitly an entity, check for other database-related annotations
        if not is_entity:
            for annotation in self.db_annotations:
                if annotation in content:
                    has_db_annotations = True
                    break
        
        # If this is not an entity or doesn't have DB annotations, skip it
        if not is_entity and not has_db_annotations:
            return
        
        # Extract class name
        class_match = re.search(r'(?:public|private|protected)?\s+(?:abstract\s+)?class\s+(\w+)', content)
        if not class_match:
            return
        
        class_name = class_match.group(1)
        
        # Extract package name
        package_match = re.search(r'package\s+([\w.]+);', content)
        package = package_match.group(1) if package_match else "unknown"
        
        # Extract annotations for the class
        class_annotations = []
        lines = content.split('\n')
        in_class_decl = False
        for line in lines:
            line = line.strip()
            
            # If we found the class declaration, stop collecting annotations
            if re.search(r'class\s+' + class_name, line):
                in_class_decl = True
                continue
            
            # If we're not in the class declaration, collect annotations
            if not in_class_decl and line.startswith('@'):
                class_annotations.append(line)
        
        # Extract fields and their annotations
        fields = self._extract_fields(content, class_name)
        
        # Extract field mappings for database columns
        column_mappings = self._extract_column_mappings(content)
        
        # Extract implemented interfaces and parent class
        implements = self._extract_implements(content)
        extends = self._extract_extends(content)
        
        # Store the entity information
        self.entities[class_name] = {
            "name": class_name,
            "package": package,
            "annotations": class_annotations,
            "fields": fields,
            "column_mappings": column_mappings,
            "implements": implements,
            "extends": extends,
            "file_path": os.path.relpath(file_path, self.repo_path)
        }
        
        self.count += 1
    
    def _extract_fields(self, content: str, class_name: str) -> List[Dict[str, Any]]:
        """
        Extract fields from a class.
        
        Args:
            content: Class content
            class_name: Name of the class
            
        Returns:
            List of fields with their types, names, and annotations
        """
        fields = []
        
        # Split the content by lines
        lines = content.split('\n')
        
        # Find the class declaration
        class_index = -1
        for i, line in enumerate(lines):
            if re.search(r'class\s+' + class_name, line):
                class_index = i
                break
        
        if class_index == -1:
            return fields
        
        # Extract fields
        current_annotations = []
        for i in range(class_index + 1, len(lines)):
            line = lines[i].strip()
            
            # Stop at the end of the class
            if line.startswith('}'):
                break
            
            # Collect annotations
            if line.startswith('@'):
                current_annotations.append(line)
                continue
            
            # Check for field declaration
            field_match = re.search(r'(?:private|public|protected)?\s+(?:final\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)', line)
            if field_match:
                field_type = field_match.group(1)
                field_name = field_match.group(2)
                
                fields.append({
                    "type": field_type,
                    "name": field_name,
                    "annotations": current_annotations.copy()
                })
                
                current_annotations = []
        
        return fields
    
    def _extract_column_mappings(self, content: str) -> Dict[str, str]:
        """
        Extract column mappings for database fields.
        
        Args:
            content: Class content
            
        Returns:
            Dictionary of field name to column name mappings
        """
        mappings = {}
        
        # Pattern to match @Column annotations
        column_pattern = r'@Column\s*\(\s*name\s*=\s*["\']([^"\']+)["\']'
        column_matches = re.finditer(column_pattern, content)
        
        for match in column_matches:
            column_name = match.group(1)
            
            # Find the field declaration that follows this annotation
            field_start = match.end()
            field_text = content[field_start:field_start + 200]  # Look ahead a bit
            field_match = re.search(r'(?:private|public|protected)?\s+(?:final\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)', field_text)
            
            if field_match:
                field_name = field_match.group(1)
                mappings[field_name] = column_name
        
        return mappings
    
    def _extract_implements(self, content: str) -> List[str]:
        """Extract interfaces implemented by the class."""
        implements_match = re.search(r'implements\s+([\w.,\s]+)(?:\{|$)', content)
        if implements_match:
            implements_str = implements_match.group(1)
            return [impl.strip() for impl in implements_str.split(',')]
        return []
    
    def _extract_extends(self, content: str) -> Optional[str]:
        """Extract parent class."""
        extends_match = re.search(r'extends\s+(\w+)', content)
        if extends_match:
            return extends_match.group(1)
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the parsed entities to a dictionary."""
        return {
            "entities": self.entities,
            "count": self.count
        } 