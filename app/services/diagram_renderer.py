import logging
from typing import Dict, List, Any, Optional
import os
import re

logger = logging.getLogger(__name__)

class DiagramRenderer:
    """Renders various types of diagrams including use-case and interaction diagrams."""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
    
    @staticmethod
    def generate_use_case_diagram(features_data: Dict[str, Any]) -> str:
        """Generate a PlantUML use-case diagram from feature files or endpoint data."""
        
        puml = ["@startuml", "left to right direction", "skinparam packageStyle rectangle"]
        
        # Add actors
        actors = set(["User", "Admin", "System"])  # Default actors
        
        # Add more actors from feature files if available
        for feature in features_data.get("features", []):
            for scenario in feature.get("scenarios", []):
                # Extract actor from scenario title if format is "Actor does something"
                scenario_title = scenario.get("title", "")
                actor_match = re.match(r"^([A-Za-z]+)\s+(can|should|must|will)\s+", scenario_title)
                if actor_match:
                    actors.add(actor_match.group(1))

        # Add actor definitions
        for actor in sorted(actors):
            puml.append(f"actor {actor}")
        
        # Add rectangles for each feature group
        for feature in features_data.get("features", []):
            feature_name = feature.get("title", "Feature").replace(" ", "_")
            
            puml.append(f'rectangle "{feature.get("title", "Feature")}" {{')
            
            # Add use cases for each scenario
            for scenario in feature.get("scenarios", []):
                use_case_name = scenario.get("title", "").replace('"', "'")
                use_case_id = re.sub(r'[^A-Za-z0-9_]', '_', scenario.get("title", "")).lower()
                
                puml.append(f'  usecase "{use_case_name}" as {use_case_id}')
                
                # Try to determine which actor is involved
                for actor in actors:
                    if actor.lower() in scenario.get("title", "").lower():
                        puml.append(f'  {actor} -- {use_case_id}')
                        break
                else:
                    # Default to User if no specific actor identified
                    puml.append(f'  User -- {use_case_id}')
            
            puml.append('}')
        
        puml.append("@enduml")
        return "\n".join(puml)
    
    @staticmethod
    def generate_comprehensive_use_case_diagram(architecture_data: Dict[str, Any]) -> str:
        """Generate a comprehensive PlantUML use-case diagram showing controllers, endpoints, and actors with complete flow."""
        
        puml = [
            "@startuml",
            "skinparam usecase {",
            "  BackgroundColor LightBlue",
            "  BorderColor DarkBlue",
            "  ArrowColor Navy",
            "  ActorBorderColor black",
            "  ActorBackgroundColor white",
            "}",
            "skinparam packageStyle rectangle",
            "skinparam linetype ortho",
            "skinparam arrowThickness 1.5",
            "skinparam packageBackgroundColor AliceBlue",
            "left to right direction",
            ""
        ]
        
        # Extract all endpoints
        endpoints = architecture_data.get("endpoints", [])
        services = architecture_data.get("services", {})
        repositories = architecture_data.get("repositories", {}) 
        entities = architecture_data.get("entities", {})
        controller_service_mappings = architecture_data.get("architecture", {}).get("controller_service", {})
        service_repo_mappings = architecture_data.get("architecture", {}).get("service_repository", {})
        
        if not endpoints:
            return "@startuml\nnote \"No endpoints found in the repository.\"\n@enduml"
        
        # Identify all controllers and organize by layer
        controllers = {}
        for endpoint in endpoints:
            controller = endpoint.get("controller", "Unknown")
            if controller not in controllers:
                controllers[controller] = []
            controllers[controller].append(endpoint)

        # Draw actors
        puml.append('actor "Client" as Client')
        puml.append('actor "Administrator" as Admin')
        puml.append('actor "System" as System')
        puml.append("")
        
        # Draw the system boundary
        puml.append('rectangle "Application System" {')
        
        # 1. CONTROLLER LAYER - API ENDPOINTS
        puml.append('  package "API Layer" {')
        # Group endpoints by controller
        for controller, controller_endpoints in controllers.items():
            puml.append(f'    package "{controller}" {{')
            
            # Add all use cases for this controller
            for endpoint in controller_endpoints:
                method = endpoint.get("method", "")
                path = endpoint.get("path", "")
                http_method = endpoint.get("http_method", "")
                
                # Create unique IDs for use cases
                use_case_id = f"{controller}_{method}"
                
                # Create descriptive labels
                use_case_desc = f"{method}\\n<size:9>{http_method} {path}</size>"
                
                puml.append(f'      usecase "{use_case_desc}" as {use_case_id}')
            
            puml.append('    }')
        puml.append('  }')
        
        # 2. SERVICE LAYER
        puml.append('  package "Business Layer" {')
        for service_name, service_methods in services.items():
            service_safe_name = service_name.replace('.', '_')
            # Create a package for each service
            puml.append(f'    package "{service_name}" {{')
            
            # Add use cases for service methods
            methods = service_methods.get("methods", [])
            if methods:
                for method in methods:
                    method_name = method.get("name", "unknown")
                    use_case_id = f"{service_safe_name}_{method_name}"
                    puml.append(f'      usecase "{method_name}" as {use_case_id}')
            else:
                # If no methods were extracted, add placeholder based on endpoint service calls
                for endpoint in endpoints:
                    for service_call in endpoint.get("service_calls", []):
                        if service_call.get("service") == service_name:
                            method_name = service_call.get("method", "unknown")
                            use_case_id = f"{service_safe_name}_{method_name}"
                            puml.append(f'      usecase "{method_name}" as {use_case_id}')
            
            puml.append('    }')
        puml.append('  }')
        
        # 3. REPOSITORY LAYER
        puml.append('  package "Data Access Layer" {')
        for repo_name in repositories:
            repo_safe_name = repo_name.replace('.', '_')
            # Create a package for each repository
            puml.append(f'    package "{repo_name}" {{')
            
            # Add common repository operations
            for operation in ["save", "find", "update", "delete"]:
                use_case_id = f"{repo_safe_name}_{operation}"
                puml.append(f'      usecase "{operation}" as {use_case_id}')
            
            puml.append('    }')
        puml.append('  }')
        
        puml.append('}')
        
        # Add database outside the system
        puml.append('database "Database" {')
        for entity_name in entities:
            safe_entity_name = entity_name.replace('.', '_')
            puml.append(f'  usecase "{entity_name}" as Entity_{safe_entity_name}')
        puml.append('}')
        puml.append("")
        
        # Connect actors to controller endpoints
        for controller, controller_endpoints in controllers.items():
            for endpoint in controller_endpoints:
                method = endpoint.get("method", "")
                http_method = endpoint.get("http_method", "").upper()
                use_case_id = f"{controller}_{method}"
                
                # Determine which actor should connect to this endpoint
                if "admin" in controller.lower() or "manage" in method.lower():
                    puml.append(f'Admin --> {use_case_id}')
                elif "schedule" in method.lower() or "batch" in method.lower() or "job" in method.lower():
                    puml.append(f'System --> {use_case_id}')
                else:
                    puml.append(f'Client --> {use_case_id}')
        
        # Connect controller endpoints to service methods
        for endpoint in endpoints:
            controller = endpoint.get("controller", "")
            method = endpoint.get("method", "")
            controller_use_case_id = f"{controller}_{method}"
            
            # Connect to services via service calls
            for service_call in endpoint.get("service_calls", []):
                service_name = service_call.get("service", "")
                service_method = service_call.get("method", "")
                if service_name and service_method:
                    service_safe_name = service_name.replace('.', '_')
                    service_use_case_id = f"{service_safe_name}_{service_method}"
                    puml.append(f'{controller_use_case_id} ..> {service_use_case_id} : <<calls>>')
        
        # Connect service methods to repository methods
        for service_name, repos in service_repo_mappings.items():
            service_safe_name = service_name.replace('.', '_')
            
            # For each service, connect its methods to appropriate repository methods
            for repo in repos:
                repo_safe_name = repo.replace('.', '_')
                
                # Connect service methods to repository methods
                for endpoint in endpoints:
                    for service_call in endpoint.get("service_calls", []):
                        if service_call.get("service") == service_name:
                            service_method = service_call.get("method", "")
                            service_use_case_id = f"{service_safe_name}_{service_method}"
                            
                            # Determine appropriate repository method based on service method name
                            repo_method = ""
                            if service_method.startswith("get") or service_method.startswith("find"):
                                repo_method = "find"
                            elif service_method.startswith("save") or service_method.startswith("create"):
                                repo_method = "save"
                            elif service_method.startswith("update"):
                                repo_method = "update"
                            elif service_method.startswith("delete") or service_method.startswith("remove"):
                                repo_method = "delete"
                            else:
                                # Default to find if we can't determine
                                repo_method = "find"
                            
                            repo_use_case_id = f"{repo_safe_name}_{repo_method}"
                            puml.append(f'{service_use_case_id} ..> {repo_use_case_id} : <<uses>>')
        
        # Connect repositories to database entities
        for repo_name in repositories:
            repo_safe_name = repo_name.replace('.', '_')
            
            # Find matching entity for this repository
            for entity_name in entities:
                entity_simple_name = entity_name.split('.')[-1] if '.' in entity_name else entity_name
                repo_simple_name = repo_name.split('.')[-1] if '.' in repo_name else repo_name
                
                # Check if repository name matches entity name pattern (e.g., UserRepository -> User)
                if entity_simple_name.lower() in repo_simple_name.lower().replace("repository", ""):
                    safe_entity_name = entity_name.replace('.', '_')
                    
                    # Connect all repository operations to the entity
                    for operation in ["save", "find", "update", "delete"]:
                        repo_use_case_id = f"{repo_safe_name}_{operation}"
                        puml.append(f'{repo_use_case_id} ..> Entity_{safe_entity_name} : <<accesses>>')
        
        # Add a legend explaining the different levels and relationships
        puml.append("")
        puml.append('legend right')
        puml.append('  Multi-Level Flow Diagram')
        puml.append('  ======================')
        puml.append('  Level 1: Client/User → API Endpoints')
        puml.append('  Level 2: API Endpoints → Service Methods')
        puml.append('  Level 3: Service Methods → Repository Methods')
        puml.append('  Level 4: Repository Methods → Database Entities')
        puml.append('  ')
        puml.append('  Relationship Types:')
        puml.append('  → : Actor initiates action')
        puml.append('  ..> : Component uses another component')
        puml.append('endlegend')
        
        puml.append("@enduml")
        
        return "\n".join(puml)
    
    @staticmethod
    def generate_interaction_diagram(endpoints_data: List[Dict[str, Any]]) -> str:
        """Generate a PlantUML sequence diagram showing controller-service-repo interactions."""
        
        puml = ["@startuml", "skinparam sequenceArrowThickness 2", "skinparam roundcorner 5"]
        
        # Add participants
        participants = set(["Client"])
        
        # Group endpoints by controller
        controllers = {}
        for endpoint in endpoints_data:
            controller = endpoint.get("controller", "UnknownController")
            if controller not in controllers:
                controllers[controller] = []
            controllers[controller].append(endpoint)
            
            # Add controller to participants
            participants.add(f"{controller}")
            
            # Extract service and repo names based on conventions if implementation available
            if endpoint.get("implementation"):
                impl = endpoint.get("implementation", "")
                if "service" in impl.lower():
                    service_match = re.search(r'(\w+)Service\.', impl)
                    if service_match:
                        participants.add(f"{service_match.group(1)}Service")
                        
                        # Assume repository follows naming convention
                        participants.add(f"{service_match.group(1)}Repository")
            
            # Add services and repositories from endpoint data
            if "services" in endpoint:
                for service in endpoint["services"]:
                    participants.add(service)
            
            if "repositories" in endpoint:
                for repo in endpoint["repositories"]:
                    participants.add(repo)
            
            # Add service calls from implementation analysis
            for service_call in endpoint.get("service_calls", []):
                if "service" in service_call:
                    participants.add(service_call["service"])
        
        # Add participant definitions
        puml.append("participant Client")
        for participant in sorted(list(participants - {"Client"})):
            puml.append(f"participant {participant}")
        
        # Add interactions for each endpoint
        for controller_name, controller_endpoints in controllers.items():
            for endpoint in controller_endpoints:
                method = endpoint.get("http_method", "GET")
                path = endpoint.get("path", "/")
                
                # Start the interaction
                puml.append("\n== " + method + " " + path + " ==")
                puml.append(f"Client -> {controller_name}: {method} {path}")
                
                # If we have service calls from implementation analysis, use them
                if endpoint.get("service_calls"):
                    for service_call in endpoint.get("service_calls", []):
                        service_name = service_call.get("service")
                        method_name = service_call.get("method")
                        
                        if service_name and method_name:
                            puml.append(f"{controller_name} -> {service_name}: {method_name}()")
                            
                            # Look for repository calls related to this service
                            if "repositories" in endpoint:
                                for repo in endpoint["repositories"]:
                                    # Assume a repository method based on the service method
                                    repo_method = "findBy" + method_name[0].upper() + method_name[1:] if method_name.startswith("get") else method_name
                                    puml.append(f"{service_name} -> {repo}: {repo_method}()")
                                    puml.append(f"{repo} --> {service_name}: returns data")
                            
                            puml.append(f"{service_name} --> {controller_name}: returns result")
                
                # If no specific service calls, but we know about services, use those
                elif "services" in endpoint and not endpoint.get("service_calls"):
                    for service in endpoint["services"]:
                        # Infer a service method from the endpoint method
                        endpoint_method = endpoint.get("method", "process")
                        puml.append(f"{controller_name} -> {service}: {endpoint_method}()")
                        
                        # Look for repository calls
                        if "repositories" in endpoint:
                            for repo in endpoint["repositories"]:
                                puml.append(f"{service} -> {repo}: findData()")
                                puml.append(f"{repo} --> {service}: returns data")
                        
                        puml.append(f"{service} --> {controller_name}: returns result")
                
                puml.append(f"{controller_name} --> Client: HTTP Response")
        
        puml.append("@enduml")
        return "\n".join(puml)
    
    @staticmethod
    def generate_comprehensive_interaction_diagram(architecture_data: Dict[str, Any]) -> str:
        """Generate a comprehensive PlantUML sequence diagram showing the full system architecture."""
        
        puml = ["@startuml", "skinparam sequenceArrowThickness 2", "skinparam roundcorner 5", 
                "skinparam maxMessageSize 200", "skinparam sequenceGroupBorderColor #888888", ""]
        
        endpoints = architecture_data.get("endpoints", [])
        services = architecture_data.get("services", {})
        repositories = architecture_data.get("repositories", {})
        entities = architecture_data.get("entities", {})
        controller_service_mappings = architecture_data.get("architecture", {}).get("controller_service", {})
        service_repo_mappings = architecture_data.get("architecture", {}).get("service_repository", {})
        
        # Define participant order: Client -> Controllers -> Services -> Repositories -> Database
        participants = ["Client"]
        
        # Add controllers
        controllers = set()
        for endpoint in endpoints:
            controllers.add(endpoint.get("controller"))
        
        # Add services
        service_names = list(services.keys())
        
        # Add repositories
        repo_names = list(repositories.keys())
        
        # Define participant order: Client -> Controllers -> Services -> Repositories -> Database
        participants.extend(sorted(controllers))
        participants.extend(sorted(service_names))
        participants.extend(sorted(repo_names))
        participants.append("Database")
        
        # Add participant definitions with color coding
        for participant in participants:
            if participant == "Client":
                puml.append("actor Client")
            elif participant == "Database":
                puml.append("database Database")
            elif participant in service_names:
                puml.append(f"participant \"{participant}\" as {participant} #LightBlue")
            elif participant in repo_names:
                puml.append(f"participant \"{participant}\" as {participant} #LightGreen")
            else:
                puml.append(f"participant \"{participant}\" as {participant} #LightYellow")
        
        puml.append("")
        
        # Group endpoints by domain for better organization
        domains = {
            "Account Management": ["account", "customer", "card"],
            "Transaction Processing": ["transaction", "deposit", "withdraw", "transfer"],
            "Branch Operations": ["branch", "employee"],
            "Customer Service": ["issue", "complaint", "pending-issues", "issue-fix"],
            "Loan Services": ["loan", "payment-loan", "approve-loan", "bank-loan", "p2p-loan"],
        }
        
        domain_endpoints = {}
        for domain, keywords in domains.items():
            domain_endpoints[domain] = []
            for endpoint in endpoints:
                path = endpoint.get("path", "").lower()
                method = endpoint.get("method", "").lower()
                    
                # Check if this endpoint belongs to this domain
                if any(keyword.lower() in path or keyword.lower() in method for keyword in keywords):
                    domain_endpoints[domain].append(endpoint)
        
        # Get representative endpoints from each domain for a comprehensive view
        shown_endpoints = []
        for domain, domain_eps in domain_endpoints.items():
            if domain_eps:
                # Take up to 2 endpoints from each domain
                shown_endpoints.extend(domain_eps[:min(2, len(domain_eps))])
                
        # If we have too few, add more from any domain
        if len(shown_endpoints) < 5:
            remaining = 5 - len(shown_endpoints)
            for domain, domain_eps in domain_endpoints.items():
                if domain_eps and len(domain_eps) > 1:  # Already took some
                    additional = domain_eps[1:min(1+remaining, len(domain_eps))]
                    shown_endpoints.extend(additional)
                    remaining -= len(additional)
                    if remaining <= 0:
                        break
        
        # Add interactions for each endpoint in each domain
        for domain, domain_eps in domain_endpoints.items():
            if not domain_eps:
                continue
                
            # Add a group for the domain
            puml.append(f"\ngroup {domain}")
            
            # Add 1-2 representative interactions from this domain
            for endpoint in domain_eps[:min(2, len(domain_eps))]:
                controller = endpoint.get("controller")
                method = endpoint.get("http_method", "GET")
                path = endpoint.get("path", "/")
                endpoint_method = endpoint.get("method", "process")
                
                # Start the interaction
                puml.append(f"\n== {method} {path} ==")
                puml.append(f"Client -> {controller}: {endpoint_method}()")
                
                # Get service calls from the endpoint data
                service_calls = endpoint.get("service_calls", [])
                
                if service_calls:
                    # Use actual service calls from the code analysis
                    for service_call in service_calls:
                        service_name = service_call.get("service")
                        method_name = service_call.get("method")
                        
                        if service_name and method_name:
                            puml.append(f"{controller} -> {service_name}: {method_name}()")
                            
                            # If we know about repos used by this service, show them
                            if service_name in service_repo_mappings:
                                for repo in service_repo_mappings[service_name]:
                                    # Identify entity managed by this repo if available
                                    entity_type = None
                                    for entity_name, entity_info in entities.items():
                                        if entity_name.lower() in repo.lower():
                                            entity_type = entity_name
                                            break
                                            
                                    # Generate a plausible repository method name
                                    if method_name.startswith("get") or method_name.startswith("find"):
                                        repo_method = method_name
                                    elif method_name.startswith("create") or method_name.startswith("add"):
                                        repo_method = f"save"
                                    elif method_name.startswith("update"):
                                        repo_method = f"update"
                                    elif method_name.startswith("delete") or method_name.startswith("remove"):
                                        repo_method = f"delete"
                                    else:
                                        repo_method = f"{method_name}Data"
                                        
                                    # Show repository interaction
                                    puml.append(f"{service_name} -> {repo}: {repo_method}()")
                                    
                                    # Show database interaction with entity if known
                                    if entity_type:
                                        puml.append(f"{repo} -> Database: SQL [entity: {entity_type}]")
                                    else:
                                        puml.append(f"{repo} -> Database: SQL operation")
                                        
                                    puml.append(f"Database --> {repo}: data")
                                    puml.append(f"{repo} --> {service_name}: returns data")
                            
                            puml.append(f"{service_name} --> {controller}: returns result")
                
                # If no specific service calls, check controller-service mappings
                elif controller in controller_service_mappings and not service_calls:
                    for service in controller_service_mappings[controller]:
                        # Infer a service method based on the endpoint method/path
                        if "get" in endpoint_method.lower() or method == "GET":
                            service_method = "retrieve" + endpoint_method[3:] if endpoint_method.startswith("get") else f"get{endpoint_method}"
                        elif "create" in endpoint_method.lower() or method == "POST":
                            service_method = "create" + endpoint_method[6:] if endpoint_method.startswith("create") else f"create{endpoint_method}"
                        elif "update" in endpoint_method.lower() or method == "PUT":
                            service_method = "update" + endpoint_method[6:] if endpoint_method.startswith("update") else f"update{endpoint_method}"
                        elif "delete" in endpoint_method.lower() or method == "DELETE":
                            service_method = "delete" + endpoint_method[6:] if endpoint_method.startswith("delete") else f"delete{endpoint_method}"
                        else:
                            service_method = endpoint_method
                            
                        puml.append(f"{controller} -> {service}: {service_method}()")
                        
                        # Check service-repo mappings
                        if service in service_repo_mappings:
                            for repo in service_repo_mappings[service]:
                                # Generate plausible repo method
                                if "get" in service_method.lower():
                                    repo_method = f"findBy{service_method[3:]}" if service_method.startswith("get") else f"findBy{service_method}"
                                elif "create" in service_method.lower():
                                    repo_method = "save"
                                elif "update" in service_method.lower():
                                    repo_method = "save"  # JPA typically uses save for update too
                                elif "delete" in service_method.lower():
                                    repo_method = f"deleteBy{service_method[6:]}" if service_method.startswith("delete") else f"delete"
                                else:
                                    repo_method = f"process{service_method}"
                                    
                                puml.append(f"{service} -> {repo}: {repo_method}()")
                                puml.append(f"{repo} -> Database: execute SQL")
                                puml.append(f"Database --> {repo}: result")
                                puml.append(f"{repo} --> {service}: data")
                        
                        puml.append(f"{service} --> {controller}: result")
                
                # Fallback for cases with no service information
                else:
                    # For controllers with no explicit service calls, show a generic flow
                    puml.append(f"{controller} -> {controller}: process request")
                    
                    # Suggest possible service based on controller name
                    suggested_service = controller.replace("Controller", "Service")
                    if suggested_service in service_names:
                        puml.append(f"{controller} -> {suggested_service}: process{endpoint_method}()")
                        puml.append(f"{suggested_service} --> {controller}: returns result")
                
                puml.append(f"{controller} --> Client: HTTP {method} Response")
            
            puml.append("end")  # End of domain group
        
        puml.append("\n@enduml")
        return "\n".join(puml)
    
    @staticmethod
    def generate_class_diagram(architecture_data: Dict[str, Any]) -> str:
        """Generate a PlantUML class diagram showing entities, repositories, services, and controllers."""
        
        puml = [
            "@startuml",
            "skinparam classAttributeIconSize 0",
            "skinparam classFontSize 12",
            "skinparam classFontName Arial",
            "skinparam classBackgroundColor LightCyan",
            "skinparam stereotypeCBackgroundColor Yellow",
            "skinparam packageBackgroundColor WhiteSmoke",
            "skinparam arrowColor Navy",
            "skinparam arrowThickness 1.5",
            "skinparam linetype ortho",
            ""
        ]
        
        entities = architecture_data.get("entities", {})
        repositories = architecture_data.get("repositories", {})
        services = architecture_data.get("services", {})
        endpoints = architecture_data.get("endpoints", [])
        
        # Extract controllers from endpoints
        controllers = {}
        for endpoint in endpoints:
            controller = endpoint.get("controller")
            if controller and controller not in controllers:
                controllers[controller] = {"endpoints": []}
            if controller:
                controllers[controller]["endpoints"].append({
                    "method": endpoint.get("method"),
                    "http_method": endpoint.get("http_method"),
                    "path": endpoint.get("path")
                })
        
        # Organize components by domains/packages
        domains = {
            "Models": [],
            "Repositories": [],
            "Services": [],
            "Controllers": []
        }
        
        # Assign entities to domains
        for entity_name in entities:
            domains["Models"].append(entity_name)
        
        # Assign repositories to domains
        for repo_name in repositories:
            domains["Repositories"].append(repo_name)
        
        # Assign services to domains
        for service_name in services:
            domains["Services"].append(service_name)
        
        # Assign controllers to domains
        for controller_name in controllers:
            domains["Controllers"].append(controller_name)
        
        # Add packages for each domain
        for domain, components in domains.items():
            if components:
                puml.append(f'package "{domain}" {{')
                
                if domain == "Models":
                    # Add entities
                    for entity_name in components:
                        entity_data = entities.get(entity_name, {})
                        puml.append(f'  class {entity_name} <<Entity>> {{')
                        
                        # Add fields
                        for field in entity_data.get("fields", []):
                            field_name = field.get("name", "")
                            field_type = field.get("type", "")
                            puml.append(f"    {field_type} {field_name}")
                        
                        puml.append("  }")
                        
                        # Add table annotation if available
                        if "table_name" in entity_data:
                            puml.append(f'  note bottom of {entity_name} : @Table(name="{entity_data["table_name"]}")')
                
                elif domain == "Repositories":
                    # Add repositories
                    for repo_name in components:
                        repo_data = repositories.get(repo_name, {})
                        puml.append(f'  interface {repo_name} <<Repository>> {{')
                        
                        # Add methods
                        for method in repo_data.get("methods", []):
                            method_name = method.get("name", "")
                            entity_type = method.get("entity_type", "Object")
                            puml.append(f"    {entity_type} {method_name}()")
                        
                        puml.append("  }")
                
                elif domain == "Services":
                    # Add services
                    for service_name in components:
                        service_data = services.get(service_name, {})
                        puml.append(f'  class {service_name} <<Service>> {{')
                        
                        # Add methods
                        for method in service_data.get("methods", []):
                            method_name = method.get("name", "")
                            return_type = method.get("return_type", "void")
                            puml.append(f"    {return_type} {method_name}()")
                        
                        puml.append("  }")
                
                elif domain == "Controllers":
                    # Add controllers
                    for controller_name in components:
                        controller_data = controllers.get(controller_name, {})
                        puml.append(f'  class {controller_name} <<Controller>> {{')
                        
                        # Add endpoints as methods
                        for endpoint in controller_data.get("endpoints", []):
                            method_name = endpoint.get("method", "")
                            http_method = endpoint.get("http_method", "")
                            path = endpoint.get("path", "")
                            puml.append(f"    @{http_method}(\"{path}\") {method_name}()")
                        
                        puml.append("  }")
                
                puml.append('}')
                puml.append('')
        
        # Add relationships between entities based on field types
        puml.append("' Entity relationships")
        for entity_name, entity_data in entities.items():
            for field in entity_data.get("fields", []):
                field_type = field.get("type", "")
                # Check if the field type refers to another entity
                if field_type in entities:
                    puml.append(f"{entity_name} --o {field_type} : contains >")
        
        # Add relationships between repositories and entities
        puml.append("' Repository-Entity relationships")
        for repo_name in repositories:
            # Try to determine the entity from repository name
            for entity_name in entities:
                if entity_name in repo_name:
                    puml.append(f"{repo_name} ..> {entity_name} : manages >")
        
        # Add relationships between services and repositories
        puml.append("' Service-Repository relationships")
        service_repo_mappings = architecture_data.get("architecture", {}).get("service_repository", {})
        for service, repos in service_repo_mappings.items():
            for repo in repos:
                puml.append(f"{service} --> {repo} : uses >")
                
        # For services without explicit mappings, try to infer based on names
        for service_name in services:
            if service_name not in service_repo_mappings:
                for repo_name in repositories:
                    if repo_name.replace("Repository", "") in service_name:
                        puml.append(f"{service_name} --> {repo_name} : likely uses >")
        
        # Add relationships between controllers and services
        puml.append("' Controller-Service relationships")
        controller_service_mappings = architecture_data.get("architecture", {}).get("controller_service", {})
        for controller, service_list in controller_service_mappings.items():
            for service in service_list:
                puml.append(f"{controller} --> {service} : calls >")
                
        # For controllers without explicit mappings, infer based on names or endpoint data
        for controller_name, controller_data in controllers.items():
            if controller_name not in controller_service_mappings:
                # Try to find related services from the endpoints' service calls
                service_called = set()
                for endpoint in endpoints:
                    if endpoint.get("controller") == controller_name:
                        for service_call in endpoint.get("service_calls", []):
                            service = service_call.get("service", "")
                            if service and service in services:
                                service_called.add(service)
                                
                # Add the relationships
                for service in service_called:
                    puml.append(f"{controller_name} --> {service} : calls >")
                    
                # If no service calls found, try to infer based on name
                if not service_called:
                    service_suffix = controller_name.replace("Controller", "Service")
                    if service_suffix in services:
                        puml.append(f"{controller_name} --> {service_suffix} : likely calls >")
        
        # Add legend
        puml.append("legend right")
        puml.append("  Entity: Database entity/model class")
        puml.append("  Repository: Data access interface")
        puml.append("  Service: Business logic component")
        puml.append("  Controller: REST endpoint handler")
        puml.append("  ")
        puml.append("  Relationship types:")
        puml.append("  --o : Entity contains/references another entity")
        puml.append("  ..> : Repository manages an entity")
        puml.append("  --> : Service uses repository / Controller calls service")
        puml.append("endlegend")
        
        puml.append("@enduml")
        return "\n".join(puml)
    
    def generate_diagram(self, diagram_type: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate diagram of the specified type using PlantUML."""
        
        # Get appropriate data based on the diagram type if not provided
        if data is None:
            if diagram_type == "use-case":
                from ..services.feature_builder import FeatureBuilder
                feature_builder = FeatureBuilder()
                data = feature_builder.extract_feature_files(self.repo_path)
                
            elif diagram_type in ["interaction", "comprehensive-interaction", "class", "comprehensive-use-case"]:
                from ..services.endpoint_parser import EndpointParser
                endpoint_parser = EndpointParser()
                data = endpoint_parser.parse_endpoints(self.repo_path)
                
                # Log the structure of the data to help with debugging
                logger.debug(f"Data structure for {diagram_type} diagram: {type(data)}")
                if isinstance(data, dict):
                    logger.debug(f"Keys in data: {list(data.keys())}")
        
        # Generate appropriate diagram
        puml_source = ""
        if diagram_type == "use-case":
            puml_source = self.generate_use_case_diagram(data)
        elif diagram_type == "comprehensive-use-case":
            puml_source = self.generate_comprehensive_use_case_diagram(data)
        elif diagram_type == "interaction":
            # Ensure we're passing a list of endpoints
            if isinstance(data, dict) and "endpoints" in data:
                puml_source = self.generate_interaction_diagram(data.get("endpoints", []))
            else:
                logger.warning(f"Expected data to contain 'endpoints' key for interaction diagram, got: {type(data)}")
                puml_source = self.generate_interaction_diagram([])
        elif diagram_type == "comprehensive-interaction":
            puml_source = self.generate_comprehensive_interaction_diagram(data)
        elif diagram_type == "class":
            puml_source = self.generate_class_diagram(data)
        else:
            return {
                "status": "error",
                "message": f"Unsupported diagram type: {diagram_type}",
                "puml_source": "",
                "diagram_url": None
            }
        
        try:
            # Try to import plantuml
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