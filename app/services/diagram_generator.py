import logging
from typing import Dict, List, Any
import os
import tempfile

logger = logging.getLogger(__name__)

class PlantUMLGenerator:
    """Generate PlantUML diagrams from parsed entities."""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
    
    @staticmethod
    def generate_class_diagram(entities_data: Dict[str, Any]) -> str:
        """Generate a PlantUML class diagram from entity data."""
        
        puml = ["@startuml", "skinparam classAttributeIconSize 0"]
        
        # Process all entities - entities_data structure is {entities: {entity_name: entity_data}}
        for entity_name, entity in entities_data.get("entities", {}).items():
            # Add class definition
            puml.append(f"class {entity_name} {{")
            
            # Add fields
            for field in entity.get("fields", []):
                field_type = field["type"].replace("java.util.", "").replace("java.lang.", "")
                puml.append(f"  {field['name']}: {field_type}")
            
            puml.append("}")
            
        # Process relationships after all classes are defined
        for entity_name, entity in entities_data.get("entities", {}).items():
            # Add relationships
            for relationship in entity.get("relationships", []):
                target_entity = relationship["target"]
                rel_type = relationship["type"]
                
                # Map JPA relationship types to PlantUML syntax
                if rel_type == "OneToMany":
                    arrow = f"{entity_name} \"1\" -- \"*\" {target_entity}"
                elif rel_type == "ManyToOne":
                    arrow = f"{entity_name} \"*\" -- \"1\" {target_entity}"
                elif rel_type == "OneToOne":
                    arrow = f"{entity_name} \"1\" -- \"1\" {target_entity}"
                elif rel_type == "ManyToMany":
                    arrow = f"{entity_name} \"*\" -- \"*\" {target_entity}"
                else:
                    arrow = f"{entity_name} -- {target_entity}"
                
                # Add relationship label if needed
                field_name = relationship.get("field")
                if field_name:
                    arrow += f" : {field_name}"
                
                puml.append(arrow)
        
        puml.append("@enduml")
        return "\n".join(puml)
    
    @staticmethod
    def generate_er_diagram(entities_data: Dict[str, Any]) -> str:
        """Generate a PlantUML ER diagram from entity data."""
        
        puml = ["@startuml", "!define table(x) entity x << (T,#FFAAAA) >>"]
        
        # Process all entities - entities_data structure is {entities: {entity_name: entity_data}}
        for entity_name, entity in entities_data.get("entities", {}).items():
            # Add entity definition
            puml.append(f"table({entity_name}) {{")
            
            # Add primary key placeholder (assuming "id")
            puml.append("  *id : Long <<PK>>")
            
            # Add fields
            for field in entity.get("fields", []):
                if field["name"] != "id" and not field.get("is_relationship", False):
                    field_type = field["type"].replace("java.util.", "").replace("java.lang.", "")
                    puml.append(f"  {field['name']}: {field_type}")
            
            puml.append("}")
            
        # Process relationships
        for entity_name, entity in entities_data.get("entities", {}).items():
            # Add relationships
            for relationship in entity.get("relationships", []):
                target_entity = relationship["target"]
                rel_type = relationship["type"]
                
                if rel_type == "OneToMany":
                    puml.append(f"{entity_name} ||--o{{ {target_entity}")
                elif rel_type == "ManyToOne":
                    puml.append(f"{entity_name} }}o--|| {target_entity}")
                elif rel_type == "OneToOne":
                    puml.append(f"{entity_name} ||--|| {target_entity}")
                elif rel_type == "ManyToMany":
                    puml.append(f"{entity_name} }}o--o{{ {target_entity}")
                
        puml.append("@enduml")
        return "\n".join(puml)
        
    def generate_puml_source(self, diagram_type: str = "class") -> str:
        """Generate PlantUML source code based on entity data."""
        from ..services.entity_parser import EntityParser
        
        # Parse entities
        parser = EntityParser(self.repo_path)
        entities_data = parser.parse_entities()
        
        # Generate diagram source based on type
        if diagram_type == "er":
            return self.generate_er_diagram(entities_data)
        else:
            return self.generate_class_diagram(entities_data)
            
    def generate_diagram(self, diagram_type: str = "class") -> Dict[str, Any]:
        """Generate diagram using PlantUML."""
        puml_source = self.generate_puml_source(diagram_type)
        
        try:
            # Try to import plantuml (will fail if not installed)
            import plantuml
            
            # Create a PlantUML server instance
            server = plantuml.PlantUML(url='http://www.plantuml.com/plantuml/img/')
            
            # Generate the diagram
            diagram_url = server.get_url(puml_source)
            
            return {
                "status": "success",
                "message": f"Generated {diagram_type} diagram successfully",
                "puml_source": puml_source,
                "diagram_url": diagram_url
            }
            
        except ImportError as e:
            # Handle missing plantuml package
            logger.warning(f"PlantUML package not installed: {str(e)}")
            return {
                "status": "warning",
                "message": f"PlantUML package not installed: {str(e)}. Install with: pip install plantuml six",
                "puml_source": puml_source,
                "diagram_url": None
            }
        except Exception as e:
            # Handle other errors
            logger.error(f"Error generating diagram: {str(e)}")
            return {
                "status": "error",
                "message": f"Error generating diagram: {str(e)}",
                "puml_source": puml_source,
                "diagram_url": None
            } 