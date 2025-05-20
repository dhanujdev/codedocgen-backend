import os
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import ast
import javalang
import javalang.tree

logger = logging.getLogger(__name__)

class FlowAnalyzer:
    """Service for analyzing method call flows from controllers through services to repositories."""
    
    # Patterns to identify service and repository classes
    SERVICE_PATTERNS = [
        r'@Service\b',
        r'Service$',
        r'ServiceImpl$'
    ]
    
    REPOSITORY_PATTERNS = [
        r'@Repository\b',
        r'Repository$',
        r'Dao$',
        r'JpaRepository\b',
        r'CrudRepository\b',
        r'MongoRepository\b'
    ]
    
    def __init__(self):
        self.java_files_map = {}  # Map of class names to file paths
        self.class_method_map = {}  # Map of class+method to their call graph
        self.parsed_classes = {}  # Cache of parsed class information
    
    def analyze_flows(self, repo_path: str) -> List[Dict[str, Any]]:
        """
        Analyze API endpoint flows in a repository.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            List of flow data for each endpoint
        """
        # First, scan for controller classes and endpoints
        from app.services.endpoint_parser import EndpointParser
        endpoint_parser = EndpointParser()
        architecture_data = endpoint_parser.parse_endpoints(repo_path)
        
        # Extract endpoints list from architecture_data if it's a dictionary
        if isinstance(architecture_data, dict) and "endpoints" in architecture_data:
            endpoints = architecture_data.get("endpoints", [])
        else:
            # If architecture_data is already a list (old format), use it directly
            endpoints = architecture_data
        
        # Scan all Java files
        java_files = self._find_java_files(repo_path)
        self.java_files_map = self._map_classes_to_files(java_files)
        
        # Parse all classes
        self.parsed_classes = {}
        for class_name, file_path in self.java_files_map.items():
            class_info = self._parse_class(file_path)
            # Add a determined class type
            class_info['class_type'] = self._determine_class_type(class_info)
            self.parsed_classes[class_name] = class_info
        
        # Analyze flows for each endpoint
        flows = []
        for endpoint in endpoints:
            try:
                # Check if endpoint is a string, which indicates an issue with format
                if isinstance(endpoint, str):
                    logger.warning(f"Received endpoint as string instead of dictionary: {endpoint}")
                    continue
                
                # Directly use the _analyze_endpoint_flow method
                flow_data = self._analyze_endpoint_flow(endpoint)
                
                # Apply flattening and hierarchy information to the flow items
                self._flatten_flow(flow_data['flow'])
                
                flows.append(flow_data)
            except Exception as e:
                logger.error(f"Error analyzing flow for endpoint: {e}")
                # Continue processing other endpoints even if one fails
                continue
            
        return flows
        
    def _flatten_flow(self, flow_items: List[Dict[str, Any]]) -> None:
        """
        Flatten nested flows to make them more consumable by the frontend.
        Preserves the hierarchical structure but adds indentation information.
        
        Args:
            flow_items: List of flow items to flatten
        """
        def process_item(item, level=0, path=None):
            if path is None:
                path = []
                
            # Add level information for UI rendering
            item['level'] = level
            item['path'] = path + [f"{item.get('class_name', '')}.{item.get('method', '')}"]
                
            # Add proper type information for better UI rendering
            if 'class_type' not in item:
                item['class_type'] = self._determine_class_type_from_name(item.get('class_name', ''))
            
            # Ensure return_type is present
            if 'return_type' not in item:
                item['return_type'] = 'void'  # Default if not specified
                
            # Process nested calls recursively while maintaining hierarchy
            if 'calls' in item and item['calls']:
                for call in item['calls']:
                    process_item(call, level + 1, item['path'])
                    
        # Start processing from root items
        for item in flow_items:
            process_item(item)
            
        # If we need to present a completely flat list for some views, 
        # we can implement that here while still keeping the hierarchy information
    
    def _determine_class_type_from_name(self, class_name: str) -> str:
        """Determine the type of a class based on its name when detailed info is not available."""
        if 'Controller' in class_name:
            return 'controller'
        elif 'Service' in class_name or 'Manager' in class_name:
            return 'service'
        elif 'Repository' in class_name or 'Dao' in class_name or 'Repo' in class_name:
            return 'repository'
        elif 'Validator' in class_name:
            return 'validator'
        else:
            return 'unknown'
    
    def _build_java_files_map(self, repo_path: str) -> None:
        """
        Build a map of class names to file paths for Java files in the repository.
        """
        logger.info(f"Building Java files map for repository: {repo_path}")
        
        for root, _, files in os.walk(repo_path):
            for file in files:
                if file.endswith(".java"):
                    file_path = os.path.join(root, file)
                    try:
                        class_name = self._extract_class_name(file_path)
                        if class_name:
                            self.java_files_map[class_name] = file_path
                    except Exception as e:
                        logger.warning(f"Error extracting class name from {file_path}: {e}")
    
    def _extract_class_name(self, file_path: str) -> Optional[str]:
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
        return None
    
    def _analyze_endpoint_flow(self, endpoint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the method call flow starting from a controller endpoint.
        
        Args:
            endpoint: Dictionary containing controller and endpoint information
            
        Returns:
            A dictionary containing the flow information
        """
        try:
            controller = endpoint.get('controller', '')
            method = endpoint.get('method', '')
            http_method = endpoint.get('http_method', 'GET')
            path = endpoint.get('path', '')
            
            if not controller or not method:
                logger.warning(f"Missing required controller or method in endpoint: {endpoint}")
                return {
                    "controller": controller,
                    "endpoint": path,
                    "http_method": http_method,
                    "flow": []
                }
            
            logger.info(f"Analyzing flow for endpoint: {http_method} {path} in {controller}.{method}")
            
            # Check if controller exists in our map
            controller_found = False
            actual_controller = controller
            
            # Try exact match first
            if controller in self.java_files_map:
                controller_found = True
            else:
                # Try to find similar controller name
                for potential_controller in self.java_files_map.keys():
                    if (controller.lower() in potential_controller.lower() or 
                        potential_controller.lower() in controller.lower()):
                        logger.info(f"Found similar controller: {potential_controller} for {controller}")
                        actual_controller = potential_controller
                        controller_found = True
                        break
            
            if not controller_found:
                logger.warning(f"Controller {controller} not found in Java files map")
                return {
                    "controller": controller,
                    "endpoint": path,
                    "http_method": http_method,
                    "flow": []
                }
            
            # Start flow analysis from controller method
            method_flow = self._analyze_method_flow(actual_controller, method)
            
            # If method not found directly, try to find the method by HTTP mapping annotation
            if method_flow is None or 'method' not in method_flow:
                logger.info(f"Method {method} not found directly, trying to find by HTTP mapping")
                
                # Get controller class info
                class_info = self.parsed_classes.get(actual_controller)
                if class_info:
                    # Look for method with HTTP mapping annotation matching the path
                    for m in class_info.get('methods', []):
                        # For REST endpoints, check if the method has the corresponding HTTP method annotation
                        mapping_annotation = f"{http_method.capitalize()}Mapping"  # e.g., PostMapping, GetMapping
                        any_mapping = "RequestMapping"
                        
                        if 'annotations' in m and (mapping_annotation in m.get('annotations', []) or any_mapping in m.get('annotations', [])):
                            logger.info(f"Found potential match for {method} via {mapping_annotation}: {m['name']}")
                            method_flow = self._analyze_method_flow(actual_controller, m['name'])
                            break
                
                # If still not found, try more aggressive matching of method name
                if method_flow is None:
                    logger.info(f"Trying to find method with similar name to {method}")
                    for potential_method_name in self._find_similar_method_names(actual_controller, method):
                        logger.info(f"Trying similar method: {potential_method_name}")
                        method_flow = self._analyze_method_flow(actual_controller, potential_method_name)
                        if method_flow:
                            break
            
            return {
                "controller": controller,
                "endpoint": path,
                "http_method": http_method,
                "flow": [method_flow] if method_flow else []
            }
        except Exception as e:
            logger.error(f"Error in _analyze_endpoint_flow: {e}")
            # Return a minimal structure to avoid breaking the flow
            return {
                "controller": endpoint.get('controller', 'unknown'),
                "endpoint": endpoint.get('path', 'unknown'),
                "http_method": endpoint.get('http_method', 'GET'),
                "flow": []
            }
    
    def _find_similar_method_names(self, class_name: str, method_name: str) -> List[str]:
        """Find methods with similar names in a class."""
        similar_methods = []
        class_info = self.parsed_classes.get(class_name)
        
        if not class_info:
            return similar_methods
            
        # Common REST method name variants
        if method_name == 'makeTransfer':
            similar_methods.extend(['transfer', 'transferMoney', 'processTransfer', 'performTransfer'])
        elif method_name == 'withdraw':
            similar_methods.extend(['withdrawMoney', 'processWithdraw', 'performWithdraw', 'withdrawAmount'])
        elif method_name == 'deposit':
            similar_methods.extend(['depositMoney', 'processDeposit', 'performDeposit', 'depositAmount'])
        elif method_name == 'checkAccountBalance':
            similar_methods.extend(['getBalance', 'retrieveBalance', 'accountBalance', 'getAccountBalance'])
        elif method_name == 'createAccount':
            similar_methods.extend(['addAccount', 'registerAccount', 'openAccount', 'newAccount'])
            
        # Look for methods with similar names
        for m in class_info.get('methods', []):
            if (method_name.lower() in m['name'].lower() or 
                m['name'].lower() in method_name.lower()):
                similar_methods.append(m['name'])
                
        # Add annotation-based matches
        for m in class_info.get('methods', []):
            if 'annotations' in m:
                for annotation in m.get('annotations', []):
                    # Path matching for REST annotations
                    if 'Mapping' in annotation and ('value' in annotation or 'path' in annotation):
                        similar_methods.append(m['name'])
                        
        return list(set(similar_methods))  # Remove duplicates
    
    def _analyze_method_flow(self, class_name: str, method_name: str, visited: Set[str] = None) -> Dict[str, Any]:
        """
        Analyze the flow of a method, tracking calls to other methods.
        
        Args:
            class_name: Name of the class containing the method
            method_name: Name of the method to analyze
            visited: Set of visited methods to avoid cycles
            
        Returns:
            Dictionary representing the flow of execution
        """
        if visited is None:
            visited = set()
            
        # Check for cycles
        method_key = f"{class_name}.{method_name}"
        if method_key in visited:
            logger.info(f"Detected cycle in method call: {method_key}")
            return {
                'class_name': class_name,
                'method': method_name,
                'class_type': self._determine_class_type_from_name(class_name),
                'return_type': 'void',
                'is_cycle': True
            }
        
        visited.add(method_key)
        
        # Get class info
        class_info = self.parsed_classes.get(class_name)
        if not class_info:
            logger.warning(f"Class {class_name} not found in analysis, trying to find it")
            # Look for similar class names as a fallback
            for potential_class in self.parsed_classes.keys():
                if class_name.lower() in potential_class.lower() or potential_class.lower() in class_name.lower():
                    logger.info(f"Found potential match {potential_class} for {class_name}")
                    class_info = self.parsed_classes.get(potential_class)
                    # Update class_name to the found one
                    class_name = potential_class
                    break
                    
            if not class_info:
                logger.warning(f"No match found for class {class_name}")
                return {
                    'class_name': class_name,
                    'method': method_name,
                    'class_type': self._determine_class_type_from_name(class_name),
                    'return_type': 'void'  # Default return type if class not found
                }
            
        # Get method info
        method_info = None
        for m in class_info.get('methods', []):
            if m['name'] == method_name:
                method_info = m
                break
                
        if not method_info:
            logger.warning(f"Method {method_name} not found in class {class_name}, checking controller methods")
            # Try to find a method with similar name or with corresponding annotations
            for m in class_info.get('methods', []):
                # For controller endpoints, match annotations like @GetMapping, @PostMapping etc.
                if 'annotations' in m and any(anno in ['GetMapping', 'PostMapping', 'PutMapping', 'DeleteMapping', 'RequestMapping'] for anno in m.get('annotations', [])):
                    logger.info(f"Found potential endpoint method {m['name']} with annotations")
                    method_info = m
                    break
                # Try to match by similar method name (case insensitive)
                if method_name.lower() in m['name'].lower() or m['name'].lower() in method_name.lower():
                    logger.info(f"Found potential method {m['name']} by similar name to {method_name}")
                    method_info = m
                    break
            
            if not method_info:
                logger.warning(f"Method {method_name} not found in class {class_name}")
                return {
                    'class_name': class_name,
                    'method': method_name,
                    'class_type': class_info.get('class_type', self._determine_class_type_from_name(class_name)),
                    'return_type': 'void'  # Default return type if method not found
                }
            
        # Extract method body
        if 'body' not in method_info:
            method_body = self._extract_method_body(class_info.get('content', ''), method_name)
            if method_body:
                method_info['body'] = method_body
                # Extract calls if not already done
                if 'calls' not in method_info:
                    method_info['calls'] = self._extract_method_calls(method_body)
            
        # Extract calls from this method
        calls = []
        for called_method in method_info.get('calls', []):
            called_class = called_method.get('class', '')
            called_method_name = called_method.get('method', '')
            
            # Skip if no class or method
            if not called_class or not called_method_name:
                continue
                
            # Skip self-references to avoid trivial cycles
            if called_class == class_name and called_method_name == method_name:
                continue
            
            # Log the call we're analyzing
            logger.info(f"Analyzing call from {class_name}.{method_name} to {called_class}.{called_method_name}")
                
            # Recursive call to analyze the flow of the called method
            # Deep copy the visited set to avoid sharing between parallel branches
            new_visited = visited.copy()
            nested_flow = self._analyze_method_flow(called_class, called_method_name, new_visited)
            if nested_flow:
                calls.append(nested_flow)
                logger.info(f"Added nested flow for {called_class}.{called_method_name}")
                
        return {
            'class_name': class_name,
            'method': method_name,
            'class_type': class_info.get('class_type', self._determine_class_type_from_name(class_name)),
            'return_type': method_info.get('return_type', 'void'),  # Use the actual return type or default to void
            'calls': calls
        }
    
    def _extract_method_body(self, class_content: str, method_name: str) -> Optional[str]:
        """Extract the method body for a given method name from class content."""
        # Pattern to match the method declaration and extract its body
        # This handles both regular methods and methods with annotations
        method_pattern = r'(?:@\w+(?:\([^)]*\))?\s*)*(?:public|private|protected)\s+(?:[\w<>[\],\s]+)\s+' + re.escape(method_name) + r'\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{([\s\S]*?)(?:\}(?:\s*\})*)'
        
        # Handle cases where there might be nested braces
        match = re.search(method_pattern, class_content)
        if match:
            # Found the method body
            body = match.group(1)
            
            # Count braces to ensure we get the full method body
            open_braces = body.count('{')
            close_braces = body.count('}')
            
            # If braces don't match, we need to adjust the end boundary
            if open_braces > close_braces:
                # We need to find the matching closing brace
                remaining_content = class_content[match.end():]
                braces_needed = open_braces - close_braces
                
                pos = 0
                for _ in range(braces_needed):
                    next_brace = remaining_content.find('}', pos)
                    if next_brace == -1:
                        break
                    pos = next_brace + 1
                
                if pos > 0:
                    body += remaining_content[:pos]
            
            return body
        
        return None
    
    def _parse_class(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a Java file to extract class information.
        
        Args:
            file_path: Path to the Java file
            
        Returns:
            Dictionary containing class information, methods, and method calls
        """
        logger.info(f"Parsing class file: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        
        class_info = {
            'name': self._extract_class_name(file_path),
            'annotations': self._extract_annotations(content),
            'methods': self._extract_methods(content),
            'implements': self._extract_interfaces(content),
            'extends': self._extract_parent_class(content),
            'content': content  # Store the entire class content for reference
        }
        
        return class_info
    
    def _extract_annotations(self, content: str) -> List[str]:
        """Extract annotations from class content."""
        annotations = []
        for line in content.split('\n'):
            annotation_match = re.search(r'@(\w+)', line)
            if annotation_match:
                annotations.append(annotation_match.group(0))
        return annotations
    
    def _extract_methods(self, content: str) -> List[Dict[str, Any]]:
        """Extract methods and their calls from class content."""
        methods = []
        
        # First identify all Spring mapping annotations to find controller methods
        mapping_annotations = {}
        annotation_pattern = r'@((?:Request|Get|Post|Put|Delete|Patch)Mapping)(?:\s*\((?:[^)]*(?:value\s*=\s*|path\s*=\s*)?"([^"]*)")?[^)]*\))?'
        
        for match in re.finditer(annotation_pattern, content, re.DOTALL):
            annotation = match.group(1)
            path = match.group(2) if match.group(2) else ""
            
            # Look for the method name following this annotation
            method_match = re.search(r'(?:public|private|protected)?\s+(?:[\w<>[\],\s]+)\s+(\w+)\s*\([^)]*\)', content[match.end():], re.DOTALL)
            if method_match:
                method_name = method_match.group(1)
                mapping_annotations[method_name] = {
                    'annotation': annotation,
                    'path': path
                }
                logger.info(f"Found REST method via annotation: {method_name} with {annotation} on path {path}")
        
        # Improved pattern to match method declarations, handling Spring annotations better
        # This pattern accounts for annotations and modifiers before method declaration
        method_pattern = r'(?:@\w+(?:\([^)]*\))?\s*)*(?:public|private|protected)?\s+(?:static\s+)?(?:[\w<>[\],\s]+)\s+(\w+)\s*\((.*?)\)\s*(?:throws\s+[\w,\s]+)?\s*(?:\{|;)'
        
        method_matches = re.finditer(method_pattern, content, re.DOTALL)
        
        for match in method_matches:
            method_name = match.group(1)
            params_str = match.group(2)
            
            # Skip if this is a constructor (same name as class)
            class_name = self._extract_class_name_from_content(content)
            if method_name == class_name:
                continue
            
            # Extract return type
            method_start = content[:match.start()].rfind('\n')
            return_type = 'void'  # Default
            if method_start >= 0:
                method_line = content[method_start:match.start()]
                return_match = re.search(r'([\w<>[\],\s]+)\s+' + re.escape(method_name), method_line)
                if return_match:
                    return_type = return_match.group(1).strip()
            
            # Find method body - more robust extraction
            method_body = ""
            if '{' in content[match.start():]:
                start_pos = content.find('{', match.start())
                # Find matching closing brace
                brace_count = 1
                for i in range(start_pos + 1, len(content)):
                    if content[i] == '{':
                        brace_count += 1
                    elif content[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            method_body = content[start_pos:i+1]
                            break
            
            # Look for Spring annotations that indicate this is a controller method
            # Go back from the method start to find related annotations
            annotation_start = max(0, content[:match.start()].rfind('@'))
            annotations = []
            if annotation_start > 0:
                # Try to capture all annotations above the method
                annotation_text = content[annotation_start:match.start()]
                annotations = re.findall(r'@(\w+)(?:\([^)]*\))?', annotation_text)
            
            # If this is a known mapping annotation method, add it
            if method_name in mapping_annotations:
                annotations.append(mapping_annotations[method_name]['annotation'])
            
            # Extract method calls
            calls = []
            if method_body:
                calls = self._extract_method_calls(method_body)
            
            methods.append({
                'name': method_name,
                'params': params_str,
                'return_type': return_type,
                'body': method_body,
                'annotations': annotations,
                'calls': calls
            })
            
            logger.info(f"Extracted method: {method_name} with {len(calls)} calls")
            
        return methods
    
    def _extract_method_calls(self, method_body: str) -> List[Dict[str, Any]]:
        """Extract method calls from method body."""
        calls = []
        
        # Spring-specific Autowired field detection
        autowired_fields = {}
        # Find both @Autowired and constructor-injected fields
        autowired_pattern = r'(?:@Autowired|@Inject)(?:\s+private|\s+protected)?\s+([\w<>[\],\s\.]+)\s+(\w+)'
        constructor_injection_pattern = r'(?:public|private|protected)?\s+\w+\s*\(\s*(?:final\s+)?([\w<>[\],\s\.]+)\s+(\w+)'
        
        # Find all autowired fields
        for match in re.finditer(autowired_pattern, method_body, re.DOTALL):
            field_type = match.group(1).strip()
            field_name = match.group(2).strip()
            autowired_fields[field_name] = field_type
            logger.info(f"Found autowired field: {field_type} {field_name}")
            
        # Find constructor injected fields
        for match in re.finditer(constructor_injection_pattern, method_body, re.DOTALL):
            field_type = match.group(1).strip()
            field_name = match.group(2).strip()
            if 'Service' in field_type or 'Repository' in field_type or 'Dao' in field_type:
                autowired_fields[field_name] = field_type
                logger.info(f"Found constructor-injected field: {field_type} {field_name}")
        
        # Find regular field declarations that might be services
        field_pattern = r'(?:private|protected|public)?\s+([\w<>[\],\s\.]+)\s+(\w+)(?:\s*=|\s*;)'
        for match in re.finditer(field_pattern, method_body, re.DOTALL):
            field_type = match.group(1).strip()
            field_name = match.group(2).strip()
            # Only add if it looks like a service or repository
            if ('Service' in field_type or 'Repository' in field_type or 'Dao' in field_type):
                autowired_fields[field_name] = field_type
                logger.info(f"Found service/repository field: {field_type} {field_name}")
        
        # REST controller common service call pattern
        # Look for cases like "return transactionService.makeTransfer(...)"
        service_call_pattern = r'(?:return\s+)?(\w+)\.(\w+)\s*\('
        
        for match in re.finditer(service_call_pattern, method_body):
            obj = match.group(1)
            method = match.group(2)
            
            # Skip if this is a built-in method or common utility
            if method in ['toString', 'equals', 'hashCode', 'println', 'print', 'debug', 'info', 'error', 'warn']:
                continue
                
            # Don't skip all get/set methods as they might be important service calls
            if obj:
                obj_class = None
                # Look up the object's class from autowired fields
                if obj in autowired_fields:
                    obj_class = autowired_fields[obj]
                    logger.info(f"Found service call on autowired field: {obj_class}.{method}()")
                else:
                    # Try to infer the class from naming convention
                    if obj.endswith('Service') or 'service' in obj:
                        possible_class = obj[0].upper() + obj[1:] if not obj[0].isupper() else obj
                        obj_class = possible_class
                    elif any(term in obj.lower() for term in ['repository', 'repo', 'dao']):
                        possible_class = obj[0].upper() + obj[1:] if not obj[0].isupper() else obj
                        obj_class = possible_class
                
                if obj_class:
                    calls.append({
                        'class': obj_class,
                        'method': method
                    })
                    logger.info(f"Added method call to: {obj_class}.{method}()")
                    
        # Look for transaction-related method calls
        # These are especially important in banking/financial applications
        if any(keyword in method_body.lower() for keyword in ['transaction', 'transfer', 'payment', 'balance', 'account']):
            # Look for methods like transactionService.makeTransfer, transferService.transfer, etc.
            transaction_call_pattern = r'(\w+(?:Service|Repository|Dao))\.(\w+(?:Transfer|Transaction|Payment|Deposit|Withdraw|Account|Balance))\s*\('
            for match in re.finditer(transaction_call_pattern, method_body, re.IGNORECASE):
                service = match.group(1)
                method = match.group(2)
                
                # Convert camelCase service name to proper class name
                if not service[0].isupper():
                    service = service[0].upper() + service[1:]
                    
                calls.append({
                    'class': service,
                    'method': method
                })
                logger.info(f"Added transaction-related call to: {service}.{method}()")
                
        # Make sure we don't have duplicate calls (same class and method)
        unique_calls = []
        seen = set()
        for call in calls:
            call_key = f"{call['class']}.{call['method']}"
            if call_key not in seen:
                seen.add(call_key)
                unique_calls.append(call)
                
        return unique_calls
    
    def _infer_class_from_object(self, obj: str, class_content: str) -> Optional[str]:
        """Infer class name from object variable using multiple detection strategies."""
        
        logger.info(f"Attempting to infer class for object: {obj}")
        
        # Strategy 1: Spring injection patterns in class level (most reliable)
        spring_patterns = [
            # Field injection with @Autowired
            rf'@Autowired(?:\s+private)?\s+(\w+)\s+{obj}\b',
            # Field injection with just private field + naming convention
            rf'private\s+(\w+)\s+{obj}\b',
            # Constructor injection parameter
            rf'(?:public|private)?\s+\w+\s*\(.*?(\w+)\s+{obj}.*?\)',
            # Final field with constructor assignment
            rf'private\s+final\s+(\w+)\s+{obj}\b'
        ]
        
        for pattern in spring_patterns:
            match = re.search(pattern, class_content)
            if match:
                class_name = match.group(1)
                logger.info(f"Found class name via Spring pattern: {class_name} for {obj}")
                
                # Check if this is a valid class in our map
                if class_name in self.java_files_map:
                    return class_name
                # Sometimes the actual implementation might be slightly different
                # Try appending 'Impl' which is common in Spring
                if f"{class_name}Impl" in self.java_files_map:
                    return f"{class_name}Impl"
        
        # Strategy 2: Check common naming conventions based on object name
        # Services and repositories usually follow consistent naming patterns
        if obj.endswith('Service') or 'service' in obj:
            # Try exact pattern match first
            for class_name in self.java_files_map.keys():
                # Match camelCase pattern: someService -> SomeService
                if class_name.endswith('Service') and obj[0].lower() + obj[1:] == class_name[0].lower() + class_name[1:]:
                    logger.info(f"Found service via naming convention: {class_name} for {obj}")
                    return class_name
                # Match with implementation suffix: someService -> SomeServiceImpl
                elif class_name.endswith('ServiceImpl') and obj.lower().replace('service', '') == class_name.lower().replace('serviceimpl', ''):
                    logger.info(f"Found service impl via naming convention: {class_name} for {obj}")
                    return class_name
            
            # Try pattern where object name is abbreviated/shortened
            # For example: txSvc -> TransactionService
            for class_name in self.java_files_map.keys():
                if class_name.endswith('Service') or class_name.endswith('ServiceImpl'):
                    # Extract root name without 'Service'/'ServiceImpl'
                    root = class_name.replace('Service', '').replace('Impl', '')
                    # Check if object name contains abbreviation
                    if root.lower().startswith(obj.lower().replace('service', '')):
                        logger.info(f"Found service via abbreviation: {class_name} for {obj}")
                        return class_name
        
        # Similar approach for repositories and DAOs
        if obj.endswith('Repository') or obj.endswith('Repo') or obj.endswith('Dao') or 'repository' in obj or 'repo' in obj or 'dao' in obj:
            for class_name in self.java_files_map.keys():
                if (class_name.endswith('Repository') or class_name.endswith('Dao')) and \
                   (obj[0].lower() + obj[1:]).replace('repository', '').replace('repo', '') == \
                   (class_name[0].lower() + class_name[1:]).replace('repository', '').replace('dao', ''):
                    logger.info(f"Found repository via naming convention: {class_name} for {obj}")
                    return class_name
            
        # Strategy 3: Look at method calls to infer type
        # This uses the context of how the object is used in the code
        usage_patterns = [
            # Method call patterns that suggest the object type
            rf'{obj}\.save\(', # Repository pattern
            rf'{obj}\.findBy', # Repository pattern
            rf'{obj}\.find\(', # Repository pattern
            rf'{obj}\.delete', # Repository pattern
            rf'{obj}\.getById', # Repository pattern
            rf'{obj}\.getAll', # Service pattern
            rf'{obj}\.process', # Service pattern
            rf'{obj}\.execute', # Service pattern
            rf'{obj}\.validate', # Service/validator pattern
            rf'{obj}\.transfer', # Specific to transaction services
            rf'{obj}\.makeTransfer', # Specific to transaction services
        ]
        
        for pattern in usage_patterns:
            if re.search(pattern, class_content):
                # Try to infer type from method usage
                if 'save' in pattern or 'find' in pattern or 'delete' in pattern or 'getById' in pattern:
                    # Likely a repository - look for matching repository classes
                    entity_name = obj.replace('Repository', '').replace('Repo', '').replace('Dao', '')
                    for class_name in self.java_files_map.keys():
                        if class_name.endswith('Repository') and entity_name.lower() in class_name.lower():
                            logger.info(f"Found repository via method usage: {class_name} for {obj}")
                            return class_name
                elif 'transfer' in pattern or 'makeTransfer' in pattern:
                    # Likely a transaction service
                    for class_name in self.java_files_map.keys():
                        if 'Transaction' in class_name and 'Service' in class_name:
                            logger.info(f"Found transaction service via method usage: {class_name} for {obj}")
                            return class_name
                elif any(method in pattern for method in ['getAll', 'process', 'execute', 'validate']):
                    # Generic service
                    for class_name in self.java_files_map.keys():
                        if class_name.endswith('Service') and obj.replace('service', '').lower() in class_name.lower():
                            logger.info(f"Found service via method usage: {class_name} for {obj}")
                            return class_name
        
        # Strategy 4: Direct name matching with first letter capitalized
        first_cap = obj[0].upper() + obj[1:] if len(obj) > 0 else ''
        if first_cap in self.java_files_map:
            logger.info(f"Found class via direct name match: {first_cap} for {obj}")
            return first_cap
        
        # Strategy 5: Special cases for common naming patterns
        common_mappings = {
            'transactionService': ['TransactionService', 'TransactionServiceImpl'],
            'accountService': ['AccountService', 'AccountServiceImpl'],
            'userService': ['UserService', 'UserServiceImpl'],
            'customerService': ['CustomerService', 'CustomerServiceImpl'],
            'authService': ['AuthService', 'AuthenticationService', 'AuthServiceImpl'],
            'validator': ['InputValidator', 'Validator', 'ValidationService'],
            'txService': ['TransactionService', 'TransactionServiceImpl'],
            'accService': ['AccountService', 'AccountServiceImpl']
        }
        
        if obj in common_mappings:
            for possible_class in common_mappings[obj]:
                if possible_class in self.java_files_map:
                    logger.info(f"Found class via common mapping: {possible_class} for {obj}")
                    return possible_class
        
        # If we couldn't find a match, check substrings for partial matches
        obj_lower = obj.lower()
        for class_name in self.java_files_map.keys():
            class_lower = class_name.lower()
            if (obj_lower in class_lower) or (class_lower in obj_lower):
                # Only match if the class name is significantly present in the object name
                if len(obj_lower) > 3 and len(class_lower) > 3:
                    logger.info(f"Found class via partial match: {class_name} for {obj}")
                    return class_name
        
        logger.info(f"Could not infer class for object: {obj}")
        return None
    
    def _extract_class_name_from_content(self, content: str) -> Optional[str]:
        """Extract class name from content."""
        class_match = re.search(r'(?:public\s+|private\s+|protected\s+)?(?:abstract\s+)?class\s+(\w+)', content)
        if class_match:
            return class_match.group(1)
        return None
    
    def _extract_interfaces(self, content: str) -> List[str]:
        """Extract implemented interfaces."""
        interfaces = []
        implements_match = re.search(r'implements\s+([\w,\s]+)(?:\{|extends)', content)
        if implements_match:
            interfaces_str = implements_match.group(1)
            interfaces = [interface.strip() for interface in interfaces_str.split(',')]
        return interfaces
    
    def _extract_parent_class(self, content: str) -> Optional[str]:
        """Extract parent class."""
        extends_match = re.search(r'extends\s+(\w+)', content)
        if extends_match:
            return extends_match.group(1)
        return None
    
    def _determine_class_type(self, class_info: Dict[str, Any]) -> str:
        """Determine if class is a controller, service, or repository."""
        name = class_info.get('name', '')
        annotations = class_info.get('annotations', [])
        implements = class_info.get('implements', [])
        
        # Check annotations and name patterns for services
        for pattern in self.SERVICE_PATTERNS:
            if any(re.search(pattern, anno) for anno in annotations) or re.search(pattern, name):
                return 'service'
        
        # Check annotations, name patterns, and interfaces for repositories
        for pattern in self.REPOSITORY_PATTERNS:
            if (any(re.search(pattern, anno) for anno in annotations) or 
                re.search(pattern, name) or
                any(re.search(pattern, impl) for impl in implements)):
                return 'repository'
        
        # If it's in the controller list, it's a controller
        if any(re.search(r'Controller$', anno) for anno in annotations) or re.search(r'Controller$', name):
            return 'controller'
        
        # Default to 'unknown'
        return 'unknown'
    
    def _find_java_files(self, repo_path: str) -> List[str]:
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
                            java_files.append(os.path.join(root, file))
            except Exception as e:
                logger.error(f"Error finding Java files in main directory: {e}")
        
        # If no Java files found or standard directory doesn't exist, search the entire repository
        if not java_files:
            logger.info(f"Searching for Java files in entire repository: {repo_path}")
            try:
                for root, _, files in os.walk(repo_path):
                    for file in files:
                        if file.endswith(".java"):
                            java_files.append(os.path.join(root, file))
            except Exception as e:
                logger.error(f"Error finding Java files: {e}")
        
        return java_files
    
    def _map_classes_to_files(self, java_files: List[str]) -> Dict[str, str]:
        """
        Map class names to their file paths.
        
        Args:
            java_files: List of Java file paths
            
        Returns:
            Dictionary mapping class names to file paths
        """
        class_map = {}
        
        for file_path in java_files:
            try:
                class_name = self._extract_class_name(file_path)
                if class_name:
                    class_map[class_name] = file_path
            except Exception as e:
                logger.warning(f"Error extracting class name from {file_path}: {e}")
                
        return class_map 