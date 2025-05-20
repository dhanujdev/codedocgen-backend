import os
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple

logger = logging.getLogger(__name__)

class EndpointParser:
    """Service for parsing REST controllers and endpoint methods in Spring Boot projects."""
    
    # Annotation patterns for controller and mapping methods
    CONTROLLER_ANNOTATIONS = [
        r'@RestController\b',
        r'@Controller\b'
    ]
    
    MAPPING_ANNOTATIONS = [
        r'@RequestMapping\b',
        r'@GetMapping\b',
        r'@PostMapping\b',
        r'@PutMapping\b',
        r'@DeleteMapping\b',
        r'@PatchMapping\b'
    ]
    
    # Pattern to extract path from annotations
    PATH_PATTERN = r'(?:value\s*=\s*|\(|\s+)["\'](.*?)["\']\)?'
    
    # Pattern to extract class name
    CLASS_PATTERN = r'(?:public\s+|private\s+|protected\s+)?(?:abstract\s+)?class\s+(\w+)'
    
    # Pattern to extract method name
    METHOD_PATTERN = r'(?:public\s+|private\s+|protected\s+)?(?:\w+\s+)+(\w+)\s*\([^)]*\)'
    
    # Annotation patterns for services and repositories
    SERVICE_ANNOTATIONS = [
        r'@Service\b',
        r'@Component\b'
    ]
    
    REPOSITORY_ANNOTATIONS = [
        r'@Repository\b',
        r'extends\s+(?:JpaRepository|CrudRepository|MongoRepository)'
    ]
    
    # Entity annotations
    ENTITY_ANNOTATIONS = [
        r'@Entity\b',
        r'@Document\b',
        r'@Table\b'
    ]
    
    def __init__(self):
        self.services = {}
        self.repositories = {}
        self.entities = {}
        self.service_repo_mappings = {}
        self.controller_service_mappings = {}
    
    def parse_endpoints(self, repo_path: str) -> Dict[str, Any]:
        """
        Parse all Java files in the repository to identify REST controllers, services, repositories, and entities.
        
        Args:
            repo_path: Path to the repository directory
            
        Returns:
            A dictionary containing the parsed architecture information:
            {
                "endpoints": List of endpoint dictionaries,
                "services": Dictionary of service names to their methods,
                "repositories": Dictionary of repository names to their methods,
                "entities": Dictionary of entity names to their fields,
                "architecture": Relationships between components
            }
        """
        logger.info(f"Parsing endpoints in project at: {repo_path}")
        
        if not os.path.isdir(repo_path):
            logger.error(f"Repository path does not exist: {repo_path}")
            return {"endpoints": []}
        
        # Find all Java files
        java_files = self._find_java_files(repo_path)
        logger.info(f"Found {len(java_files)} Java files to analyze")
        
        # Reset collections
        self.services = {}
        self.repositories = {}
        self.entities = {}
        self.service_repo_mappings = {}
        self.controller_service_mappings = {}
        
        endpoints = []
        
        # First pass: identify all classes and their types
        for file_path in java_files:
            self._identify_class_type(file_path)
        
        # Second pass: parse controllers, services, repositories, and entities
        for file_path in java_files:
            # Parse controllers and endpoints
            file_endpoints = self._parse_file(file_path)
            endpoints.extend(file_endpoints)
            
            # Parse services
            self._parse_service_file(file_path)
            
            # Parse repositories 
            self._parse_repository_file(file_path)
            
            # Parse entities
            self._parse_entity_file(file_path)
        
        # Third pass: identify relationships between components
        for file_path in java_files:
            self._identify_relationships(file_path)
        
        # Log the discovered endpoints
        for endpoint in endpoints:
            logger.info(f"Found endpoint: {endpoint}")
        
        logger.info(f"Parsed {len(endpoints)} endpoints from {len(java_files)} Java files")
        
        # Add service and repository info to endpoints where possible
        self._enrich_endpoints_with_dependencies(endpoints)
        
        return {
            "endpoints": endpoints,
            "services": self.services,
            "repositories": self.repositories,
            "entities": self.entities,
            "architecture": {
                "controller_service": self.controller_service_mappings,
                "service_repository": self.service_repo_mappings
            }
        }
    
    def _find_java_files(self, repo_path: str) -> List[Path]:
        """Find all Java files in the repository."""
        java_files = []
        main_java_dir = os.path.join(repo_path, "src", "main", "java")
        
        # If the standard Java directory structure exists, search only there
        if os.path.isdir(main_java_dir):
            logger.info(f"Searching for Java files in standard directory: {main_java_dir}")
            try:
                for root, _, files in os.walk(main_java_dir):
                    for file in files:
                        if file.endswith(".java"):
                            java_files.append(Path(os.path.join(root, file)))
            except Exception as e:
                logger.error(f"Error finding Java files in main directory: {e}")
        
        # If no Java files found or standard directory doesn't exist, search the entire repository
        if not java_files:
            logger.info(f"Searching for Java files in entire repository: {repo_path}")
            try:
                for root, _, files in os.walk(repo_path):
                    for file in files:
                        if file.endswith(".java"):
                            java_files.append(Path(os.path.join(root, file)))
            except Exception as e:
                logger.error(f"Error finding Java files: {e}")
        
        return java_files
    
    def _identify_class_type(self, file_path: Path) -> None:
        """Identify the type of class in the file: controller, service, repository, or entity."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return
        
        class_name = self._extract_class_name(file_path)
        if not class_name:
            return
        
        # Check if controller
        for pattern in self.CONTROLLER_ANNOTATIONS:
            if re.search(pattern, content):
                logger.info(f"Identified controller: {class_name}")
                return
        
        # Check if service
        for pattern in self.SERVICE_ANNOTATIONS:
            if re.search(pattern, content):
                logger.info(f"Identified service: {class_name}")
                self.services[class_name] = {"methods": [], "file_path": str(file_path)}
                return
        
        # Check if repository
        for pattern in self.REPOSITORY_ANNOTATIONS:
            if re.search(pattern, content):
                logger.info(f"Identified repository: {class_name}")
                self.repositories[class_name] = {"methods": [], "file_path": str(file_path)}
                return
        
        # Check if entity
        for pattern in self.ENTITY_ANNOTATIONS:
            if re.search(pattern, content):
                logger.info(f"Identified entity: {class_name}")
                self.entities[class_name] = {"fields": [], "file_path": str(file_path)}
                return
    
    def _parse_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse a Java file to extract controller and endpoint information."""
        logger.info(f"Parsing file: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            logger.warning(f"UnicodeDecodeError with utf-8, trying latin-1 for file: {file_path}")
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return []
        
        # Check if this file contains a REST controller
        is_controller = False
        for pattern in self.CONTROLLER_ANNOTATIONS:
            if re.search(pattern, content):
                is_controller = True
                controller_name = self._extract_class_name(file_path)
                logger.info(f"Found controller: {controller_name}")
                break
                
        if not is_controller:
            return []
            
        # Find controller base path if it exists
        base_path = ""
        request_mapping_match = re.search(r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?"([^"]*)"', content)
        if request_mapping_match:
            base_path = request_mapping_match.group(1).strip('/')
            logger.info(f"Controller base path: {base_path}")
            
        # Look for endpoints using Spring mapping annotations combined with method declarations
        endpoints = []
        
        # Define mapping patterns to search for
        mapping_patterns = [
            (r'@GetMapping\s*\(\s*(?:value\s*=\s*)?"([^"]*)"[^)]*\)[^{]*?public\s+(?:ResponseEntity|[\w<>]+)\s+(\w+)\s*\(', 'GET'),
            (r'@PostMapping\s*\(\s*(?:value\s*=\s*)?"([^"]*)"[^)]*\)[^{]*?public\s+(?:ResponseEntity|[\w<>]+)\s+(\w+)\s*\(', 'POST'),
            (r'@PutMapping\s*\(\s*(?:value\s*=\s*)?"([^"]*)"[^)]*\)[^{]*?public\s+(?:ResponseEntity|[\w<>]+)\s+(\w+)\s*\(', 'PUT'),
            (r'@DeleteMapping\s*\(\s*(?:value\s*=\s*)?"([^"]*)"[^)]*\)[^{]*?public\s+(?:ResponseEntity|[\w<>]+)\s+(\w+)\s*\(', 'DELETE'),
            (r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?"([^"]*)"[^)]*method\s*=\s*RequestMethod\.GET[^)]*\)[^{]*?public\s+(?:ResponseEntity|[\w<>]+)\s+(\w+)\s*\(', 'GET'),
            (r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?"([^"]*)"[^)]*method\s*=\s*RequestMethod\.POST[^)]*\)[^{]*?public\s+(?:ResponseEntity|[\w<>]+)\s+(\w+)\s*\(', 'POST'),
            (r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?"([^"]*)"[^)]*method\s*=\s*RequestMethod\.PUT[^)]*\)[^{]*?public\s+(?:ResponseEntity|[\w<>]+)\s+(\w+)\s*\(', 'PUT'),
            (r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?"([^"]*)"[^)]*method\s*=\s*RequestMethod\.DELETE[^)]*\)[^{]*?public\s+(?:ResponseEntity|[\w<>]+)\s+(\w+)\s*\(', 'DELETE'),
        ]
        
        # Fallback pattern for methods with no specific return type or with generics
        fallback_mapping_patterns = [
            (r'@GetMapping\s*\(\s*(?:value\s*=\s*)?"([^"]*)"[^)]*\)[^{]*?public\s+\w+(?:<[^>]*>)?\s+(\w+)\s*\(', 'GET'),
            (r'@PostMapping\s*\(\s*(?:value\s*=\s*)?"([^"]*)"[^)]*\)[^{]*?public\s+\w+(?:<[^>]*>)?\s+(\w+)\s*\(', 'POST'),
            (r'@PutMapping\s*\(\s*(?:value\s*=\s*)?"([^"]*)"[^)]*\)[^{]*?public\s+\w+(?:<[^>]*>)?\s+(\w+)\s*\(', 'PUT'),
            (r'@DeleteMapping\s*\(\s*(?:value\s*=\s*)?"([^"]*)"[^)]*\)[^{]*?public\s+\w+(?:<[^>]*>)?\s+(\w+)\s*\(', 'DELETE'),
        ]
        
        # Extract endpoint methods
        for pattern, http_method in mapping_patterns:
            for match in re.finditer(pattern, content, re.DOTALL):
                path = match.group(1)
                method_name = match.group(2)
                
                # Skip if method name is same as class name (constructor)
                if method_name == controller_name:
                    continue
                
                # Construct full path with base path
                if base_path:
                    if path.startswith("/"):
                        full_path = f"/{base_path}{path}"
                    else:
                        full_path = f"/{base_path}/{path}"
                else:
                    if not path.startswith("/"):
                        full_path = f"/{path}"
                    else:
                        full_path = path
                
                # Extract method implementation to find service calls
                method_start = match.end()
                method_block = self._extract_method_block(content, method_start)
                service_calls = self._extract_service_calls(method_block)
                
                endpoint = {
                    "controller": controller_name,
                    "method": method_name,
                    "http_method": http_method,
                    "path": full_path,
                    "implementation": method_block,
                    "service_calls": service_calls
                }
                
                logger.info(f"Found endpoint: {endpoint}")
                endpoints.append(endpoint)
        
        # Try fallback patterns if no endpoints found
        if not endpoints:
            for pattern, http_method in fallback_mapping_patterns:
                for match in re.finditer(pattern, content, re.DOTALL):
                    path = match.group(1)
                    method_name = match.group(2)
                    
                    # Construct full path with base path
                    if base_path:
                        if path.startswith("/"):
                            full_path = f"/{base_path}{path}"
                        else:
                            full_path = f"/{base_path}/{path}"
                    else:
                        if not path.startswith("/"):
                            full_path = f"/{path}"
                        else:
                            full_path = path
                    
                    # Extract method implementation to find service calls
                    method_start = match.end()
                    method_block = self._extract_method_block(content, method_start)
                    service_calls = self._extract_service_calls(method_block)
                    
                    endpoint = {
                        "controller": controller_name,
                        "method": method_name,
                        "http_method": http_method,
                        "path": full_path,
                        "implementation": method_block,
                        "service_calls": service_calls
                    }
                    
                    logger.info(f"Found endpoint with fallback pattern: {endpoint}")
                    endpoints.append(endpoint)
        
        return endpoints
    
    def _parse_service_file(self, file_path: Path) -> None:
        """Parse a service file to extract methods and repository dependencies."""
        class_name = self._extract_class_name(file_path)
        if not class_name or class_name not in self.services:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return
        
        # Extract methods
        method_pattern = r'(?:public|private|protected)\s+(?:[\w<>[\],\s]+)\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+\s*)?\{'
        for match in re.finditer(method_pattern, content, re.DOTALL):
            method_name = match.group(1)
            method_start = match.end()
            method_block = self._extract_method_block(content, method_start)
            
            # Extract repository calls
            repo_calls = self._extract_repository_calls(method_block)
            
            self.services[class_name]["methods"].append({
                "name": method_name,
                "implementation": method_block,
                "repository_calls": repo_calls
            })
        
        # Extract repository dependencies from fields
        field_pattern = r'@Autowired\s+(?:private|protected|public)?\s+(\w+)\s+(\w+);'
        for match in re.finditer(field_pattern, content):
            field_type = match.group(1)
            field_name = match.group(2)
            
            # Check if field is a repository
            if field_type in self.repositories or field_type.endswith("Repository"):
                if class_name not in self.service_repo_mappings:
                    self.service_repo_mappings[class_name] = []
                self.service_repo_mappings[class_name].append(field_type)
    
    def _parse_repository_file(self, file_path: Path) -> None:
        """Parse a repository file to extract methods and entity dependencies."""
        class_name = self._extract_class_name(file_path)
        if not class_name or class_name not in self.repositories:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return
        
        # Extract entity types from interface/class declaration
        entity_pattern = r'(?:interface|class)\s+\w+\s+extends\s+\w+Repository<(\w+),'
        entity_match = re.search(entity_pattern, content)
        entity_type = None
        if entity_match:
            entity_type = entity_match.group(1)
            self.repositories[class_name]["entity_type"] = entity_type
        
        # Extract methods
        method_pattern = r'(?:public|private|protected)?\s+(?:[\w<>[\],\s]+)\s+(\w+)\s*\([^)]*\)'
        for match in re.finditer(method_pattern, content, re.DOTALL):
            method_name = match.group(1)
            self.repositories[class_name]["methods"].append({
                "name": method_name,
                "entity_type": entity_type
            })
    
    def _parse_entity_file(self, file_path: Path) -> None:
        """Parse an entity file to extract fields and relationships with other entities."""
        class_name = self._extract_class_name(file_path)
        if not class_name or class_name not in self.entities:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return
        
        # Extract table name if available
        table_pattern = r'@Table\s*\(\s*name\s*=\s*"([^"]+)"'
        table_match = re.search(table_pattern, content)
        if table_match:
            self.entities[class_name]["table_name"] = table_match.group(1)
        
        # Extract fields
        field_pattern = r'(?:@Column\s*\([^)]*\)\s*)?(?:private|protected|public)\s+([\w<>[\],\s]+)\s+(\w+);'
        for match in re.finditer(field_pattern, content):
            field_type = match.group(1).strip()
            field_name = match.group(2)
            
            self.entities[class_name]["fields"].append({
                "name": field_name,
                "type": field_type
            })
        
        # Extract relationships
        relationship_patterns = [
            (r'@OneToMany\s*\([^)]*\)\s*(?:private|protected|public)\s+(\w+)<(\w+)>', 'OneToMany'),
            (r'@ManyToOne\s*\([^)]*\)\s*(?:private|protected|public)\s+(\w+)', 'ManyToOne'),
            (r'@OneToOne\s*\([^)]*\)\s*(?:private|protected|public)\s+(\w+)', 'OneToOne'),
            (r'@ManyToMany\s*\([^)]*\)\s*(?:private|protected|public)\s+\w+<(\w+)>', 'ManyToMany')
        ]
        
        if "relationships" not in self.entities[class_name]:
            self.entities[class_name]["relationships"] = []
        
        for pattern, rel_type in relationship_patterns:
            for match in re.finditer(pattern, content, re.DOTALL):
                if rel_type in ['OneToMany', 'ManyToMany']:
                    target_entity = match.group(2)
                else:
                    target_entity = match.group(1)
                
                self.entities[class_name]["relationships"].append({
                    "type": rel_type,
                    "target_entity": target_entity
                })
    
    def _identify_relationships(self, file_path: Path) -> None:
        """Identify relationships between controllers, services, repositories, and entities."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return
        
        class_name = self._extract_class_name(file_path)
        if not class_name:
            return
        
        # Check for controller-service relationships
        for pattern in self.CONTROLLER_ANNOTATIONS:
            if re.search(pattern, content):
                # Extract service dependencies from fields
                field_pattern = r'@Autowired\s+(?:private|protected|public)?\s+(\w+)\s+(\w+);'
                for match in re.finditer(field_pattern, content):
                    field_type = match.group(1)
                    field_name = match.group(2)
                    
                    # Check if field is a service
                    if field_type in self.services or field_type.endswith("Service"):
                        if class_name not in self.controller_service_mappings:
                            self.controller_service_mappings[class_name] = []
                        self.controller_service_mappings[class_name].append(field_type)
    
    def _extract_method_block(self, content: str, method_start: int) -> str:
        """Extract the complete method implementation block starting from the opening brace."""
        brace_count = 0
        method_end = method_start
        
        for i in range(method_start, len(content)):
            if content[i] == '{':
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    method_end = i + 1
                    break
        
        return content[method_start:method_end]
    
    def _extract_service_calls(self, method_block: str) -> List[Dict[str, str]]:
        """Extract service method calls from a method implementation."""
        service_calls = []
        
        # Pattern to match service method calls like "userService.findById(123)"
        service_call_pattern = r'(\w+)Service\.(\w+)\('
        
        for match in re.finditer(service_call_pattern, method_block):
            service_prefix = match.group(1)
            method_name = match.group(2)
            
            service_name = f"{service_prefix}Service"
            service_calls.append({
                "service": service_name,
                "method": method_name
            })
        
        return service_calls
    
    def _extract_repository_calls(self, method_block: str) -> List[Dict[str, str]]:
        """Extract repository method calls from a method implementation."""
        repo_calls = []
        
        # Pattern to match repository method calls like "userRepository.findById(123)"
        repo_call_pattern = r'(\w+)Repository\.(\w+)\('
        
        for match in re.finditer(repo_call_pattern, method_block):
            repo_prefix = match.group(1)
            method_name = match.group(2)
            
            repo_name = f"{repo_prefix}Repository"
            repo_calls.append({
                "repository": repo_name,
                "method": method_name
            })
        
        return repo_calls

    def _enrich_endpoints_with_dependencies(self, endpoints: List[Dict[str, Any]]) -> None:
        """Add service and repository information to endpoints based on discovered relationships."""
        for endpoint in endpoints:
            controller = endpoint.get("controller")
            
            # Add service dependencies
            if controller in self.controller_service_mappings:
                endpoint["services"] = self.controller_service_mappings[controller]
                
                # Add repository dependencies for each service
                repositories = []
                for service in endpoint.get("services", []):
                    if service in self.service_repo_mappings:
                        repositories.extend(self.service_repo_mappings[service])
                
                if repositories:
                    endpoint["repositories"] = repositories
    
    def _extract_class_name(self, file_path: Path) -> Optional[str]:
        """
        Extract the primary class name from a Java file.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        
        # Extract class name using regex
        class_match = re.search(r'(?:public\s+|private\s+|protected\s+)?(?:abstract\s+)?class\s+(\w+)', content)
        if class_match:
            return class_match.group(1)
        
        # Try to extract interface name
        interface_match = re.search(r'(?:public\s+|private\s+|protected\s+)?interface\s+(\w+)', content)
        if interface_match:
            return interface_match.group(1)
        
        return None 