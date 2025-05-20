import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class RoleFilter:
    """Service for filtering documentation content based on user roles."""
    
    # Define roles and their view priorities
    ROLES = {
        "developer": {
            "priorities": {
                "endpoints": 1,
                "flows": 1,
                "swagger": 1,
                "entities": 2,
                "features": 3,
                "diagrams": 2
            }
        },
        "architect": {
            "priorities": {
                "diagrams": 1,
                "flows": 1,
                "entities": 1,
                "endpoints": 2,
                "swagger": 3,
                "features": 4
            }
        },
        "product_owner": {
            "priorities": {
                "features": 1,
                "endpoints": 2,
                "swagger": 3,
                "diagrams": 2,
                "entities": 4,
                "flows": 4
            }
        },
        "qa": {
            "priorities": {
                "features": 1,
                "endpoints": 1,
                "swagger": 2,
                "flows": 3,
                "entities": 4,
                "diagrams": 3
            }
        }
    }
    
    def __init__(self):
        pass
    
    def filter_content(self, content: Dict[str, Any], role: str) -> Dict[str, Any]:
        """
        Filter documentation content based on the user role.
        
        Args:
            content: Dictionary containing documentation content
            role: User role (developer, architect, product_owner, qa)
            
        Returns:
            Filtered content with priority markers added
        """
        if role not in self.ROLES:
            logger.warning(f"Unknown role: {role}, defaulting to developer")
            role = "developer"
        
        logger.info(f"Filtering content for role: {role}")
        
        priorities = self.ROLES[role]["priorities"]
        filtered_content = content.copy()
        
        # Add priority markers to each section
        for section in priorities:
            if section in filtered_content:
                filtered_content[f"{section}_priority"] = priorities[section]
        
        # Add role metadata
        filtered_content["role"] = role
        filtered_content["view_priorities"] = priorities
        
        return filtered_content
    
    def filter_endpoints(self, endpoints: List[Dict[str, Any]], role: str) -> List[Dict[str, Any]]:
        """
        Filter endpoint data based on the user role.
        
        Args:
            endpoints: List of endpoint data
            role: User role
            
        Returns:
            Filtered endpoint data
        """
        if role not in self.ROLES:
            logger.warning(f"Unknown role: {role}, defaulting to developer")
            role = "developer"
        
        # For now, we don't actually filter out endpoints, just mark them with additional data
        # In a real application, you might want to filter based on authorization, etc.
        filtered_endpoints = []
        
        for endpoint in endpoints:
            endpoint_copy = endpoint.copy()
            
            # Add role-specific metadata
            if role == "developer":
                endpoint_copy["show_details"] = True
                endpoint_copy["show_params"] = True
                endpoint_copy["show_flows"] = True
            elif role == "architect":
                endpoint_copy["show_details"] = True
                endpoint_copy["show_params"] = False
                endpoint_copy["show_flows"] = True
            elif role == "product_owner":
                endpoint_copy["show_details"] = False
                endpoint_copy["show_params"] = False
                endpoint_copy["show_flows"] = False
                # Product owners might want to see a more user-friendly description
                if "description" in endpoint_copy:
                    endpoint_copy["business_description"] = self._convert_to_business_language(endpoint_copy["description"])
            elif role == "qa":
                endpoint_copy["show_details"] = True
                endpoint_copy["show_params"] = True
                endpoint_copy["show_flows"] = False
                endpoint_copy["link_to_test_cases"] = True
            
            filtered_endpoints.append(endpoint_copy)
        
        return filtered_endpoints
    
    def filter_entities(self, entities: Dict[str, Any], role: str) -> Dict[str, Any]:
        """
        Filter entity data based on the user role.
        
        Args:
            entities: Entity data
            role: User role
            
        Returns:
            Filtered entity data
        """
        if role not in self.ROLES:
            logger.warning(f"Unknown role: {role}, defaulting to developer")
            role = "developer"
        
        filtered_entities = entities.copy()
        
        # Add role-specific flags
        if role == "developer":
            filtered_entities["show_field_details"] = True
            filtered_entities["show_annotations"] = True
            filtered_entities["show_relationships"] = True
        elif role == "architect":
            filtered_entities["show_field_details"] = False
            filtered_entities["show_annotations"] = False
            filtered_entities["show_relationships"] = True
        elif role == "product_owner":
            filtered_entities["show_field_details"] = False
            filtered_entities["show_annotations"] = False
            filtered_entities["show_relationships"] = False
            # Simplify entity names to be more business-friendly
            simplified_entities = {}
            for entity_name, entity_data in filtered_entities.get("entities", {}).items():
                business_name = self._convert_to_business_entity_name(entity_name)
                entity_data["business_name"] = business_name
                simplified_entities[entity_name] = entity_data
            filtered_entities["entities"] = simplified_entities
        elif role == "qa":
            filtered_entities["show_field_details"] = True
            filtered_entities["show_annotations"] = False
            filtered_entities["show_relationships"] = True
        
        return filtered_entities
    
    def _convert_to_business_language(self, technical_description: str) -> str:
        """Convert technical descriptions to business language."""
        # This is just a placeholder - in a real application, you might want
        # to use more sophisticated NLP techniques or predefined mappings
        business_terms = {
            "endpoint": "feature",
            "API": "service",
            "database": "data store",
            "entity": "business object",
            "authentication": "login",
            "authorization": "access control"
        }
        
        result = technical_description
        for tech_term, business_term in business_terms.items():
            result = result.replace(tech_term, business_term)
        
        return result
    
    def _convert_to_business_entity_name(self, entity_name: str) -> str:
        """Convert technical entity names to business-friendly names."""
        # Just adds spaces before capital letters
        result = ""
        for i, char in enumerate(entity_name):
            if char.isupper() and i > 0:
                result += " " + char
            else:
                result += char
        return result 