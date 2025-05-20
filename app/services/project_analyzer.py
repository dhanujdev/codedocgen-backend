import os
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
import re

logger = logging.getLogger(__name__)

class ProjectAnalyzer:
    """Service for analyzing project types in a repository."""
    
    def __init__(self):
        pass
    
    def analyze_project(self, repo_path: str) -> dict:
        """
        Analyze the repository to identify project type (Maven/Gradle) and if it's a Spring Boot project.
        
        Args:
            repo_path: Path to the repository directory
            
        Returns:
            A dictionary with project information
        """
        logger.info(f"Analyzing project at: {repo_path}")
        
        if not os.path.isdir(repo_path):
            logger.error(f"Repository path does not exist: {repo_path}")
            return {
                "status": "error",
                "message": "Repository path does not exist or is not a directory"
            }
        
        # Check for Maven project using direct file check
        pom_files = self._find_maven_files(repo_path)
        is_maven = len(pom_files) > 0
        
        # Log the POM files found for debugging
        if pom_files:
            logger.info(f"Found Maven POM files: {pom_files}")
        else:
            logger.info(f"No Maven POM files found in {repo_path}")
            # Try direct file check if glob pattern fails
            pom_path = os.path.join(repo_path, "pom.xml")
            if os.path.isfile(pom_path):
                logger.info(f"Found Maven POM file via direct path: {pom_path}")
                pom_files = [Path(pom_path)]
                is_maven = True
        
        # Check for Gradle project using direct file check as well
        gradle_files = self._find_gradle_files(repo_path)
        is_gradle = len(gradle_files) > 0
        
        if gradle_files:
            logger.info(f"Found Gradle files: {gradle_files}")
        else:
            logger.info(f"No Gradle files found in {repo_path}")
            # Try direct file check
            gradle_path = os.path.join(repo_path, "build.gradle")
            gradle_kts_path = os.path.join(repo_path, "build.gradle.kts")
            if os.path.isfile(gradle_path):
                logger.info(f"Found Gradle file via direct path: {gradle_path}")
                gradle_files = [Path(gradle_path)]
                is_gradle = True
            elif os.path.isfile(gradle_kts_path):
                logger.info(f"Found Gradle KTS file via direct path: {gradle_kts_path}")
                gradle_files = [Path(gradle_kts_path)]
                is_gradle = True
        
        # Check if it's a Spring Boot project
        is_spring_boot = False
        spring_boot_details = {}
        
        if is_maven:
            spring_boot_details = self._is_maven_spring_boot(repo_path, pom_files)
            is_spring_boot = spring_boot_details.get('is_spring_boot', False)
            logger.info(f"Maven Spring Boot analysis: {spring_boot_details}")
        
        if is_gradle and not is_spring_boot:
            spring_boot_details = self._is_gradle_spring_boot(repo_path, gradle_files)
            is_spring_boot = spring_boot_details.get('is_spring_boot', False)
            logger.info(f"Gradle Spring Boot analysis: {spring_boot_details}")
        
        # If no build system is detected yet, try deeper Spring Boot detection
        if not (is_maven or is_gradle) or not is_spring_boot:
            deep_check = self._deep_spring_boot_check(repo_path)
            is_spring_boot = is_spring_boot or deep_check
            if deep_check:
                logger.info("Spring Boot detected through deep directory structure analysis")
        
        # Determine the primary build system
        build_system = None
        if is_maven and is_gradle:
            # Both found, determine primary based on further analysis
            # For simplicity, prioritize Maven if both are found
            build_system = "Maven/Gradle (Both found)"
        elif is_maven:
            build_system = "Maven"
        elif is_gradle:
            build_system = "Gradle"
        else:
            build_system = "Unknown"
        
        # Construct the result
        result = {
            "status": "success",
            "is_maven": is_maven,
            "is_gradle": is_gradle,
            "is_spring_boot": is_spring_boot,
            "build_system": build_system,
            "project_type": "Spring Boot" if is_spring_boot else "Java" if (is_maven or is_gradle) else "Unknown"
        }
        
        if 'version' in spring_boot_details and spring_boot_details['version']:
            result['spring_boot_version'] = spring_boot_details['version']
        
        logger.info(f"Project analysis result: {result}")
        return result
    
    def _find_maven_files(self, repo_path: str) -> list:
        """Find all Maven POM files in the repository."""
        pom_files = []
        
        # First approach: direct check for pom.xml in the root
        root_pom = os.path.join(repo_path, "pom.xml")
        if os.path.isfile(root_pom):
            logger.info(f"Found root pom.xml at {root_pom}")
            pom_files.append(Path(root_pom))
        
        # Second approach: try using Path.glob
        try:
            glob_files = list(Path(repo_path).glob("**/pom.xml"))
            for file in glob_files:
                if file not in pom_files:
                    pom_files.append(file)
        except Exception as e:
            logger.error(f"Error using Path.glob to find Maven files: {e}")
        
        # Third approach: fallback to os.walk
        try:
            for root, _, files in os.walk(repo_path):
                if "pom.xml" in files:
                    pom_path = Path(os.path.join(root, "pom.xml"))
                    if pom_path not in pom_files:
                        pom_files.append(pom_path)
        except Exception as e:
            logger.error(f"Error walking directory to find Maven files: {e}")
        
        # If we still haven't found any pom.xml files, list directory contents for debugging
        if not pom_files:
            try:
                logger.info(f"Listing directory contents of {repo_path}:")
                for root, dirs, files in os.walk(repo_path):
                    rel_path = os.path.relpath(root, repo_path)
                    if rel_path != ".":
                        logger.info(f"Directory: {rel_path}")
                    for file in files:
                        logger.info(f"File: {os.path.join(rel_path, file)}")
                    if not dirs and not files:
                        logger.warning(f"Directory is empty: {rel_path}")
            except Exception as e:
                logger.error(f"Error listing directory contents: {e}")
        
        return pom_files
    
    def _find_gradle_files(self, repo_path: str) -> list:
        """Find all Gradle build files in the repository."""
        try:
            gradle_files = list(Path(repo_path).glob("**/build.gradle"))
            gradle_kts_files = list(Path(repo_path).glob("**/build.gradle.kts"))
            return gradle_files + gradle_kts_files
        except Exception as e:
            logger.error(f"Error finding Gradle files: {e}")
            # Fallback to os.walk
            gradle_files = []
            for root, _, files in os.walk(repo_path):
                if "build.gradle" in files:
                    gradle_files.append(Path(os.path.join(root, "build.gradle")))
                if "build.gradle.kts" in files:
                    gradle_files.append(Path(os.path.join(root, "build.gradle.kts")))
            return gradle_files
    
    def _deep_spring_boot_check(self, repo_path: str) -> bool:
        """
        Perform a deeper check for Spring Boot projects by looking for common Spring Boot files
        even if build system files aren't detected.
        """
        # Check if the repository is empty
        is_empty = True
        for _, _, files in os.walk(repo_path):
            if files:
                is_empty = False
                break
        
        if is_empty:
            logger.warning(f"Repository appears to be empty: {repo_path}")
            return False
        
        # Check for Spring Boot application class
        application_files = []
        try:
            application_files = list(Path(repo_path).glob("**/src/**/*Application.java"))
            application_files.extend(list(Path(repo_path).glob("**/src/**/*App.java")))
        except Exception as e:
            logger.error(f"Error finding Application files: {e}")
            # Fallback to os.walk
            for root, _, files in os.walk(repo_path):
                for file in files:
                    if ("Application.java" in file or "App.java" in file) and "src" in os.path.relpath(root, repo_path):
                        application_files.append(Path(os.path.join(root, file)))
        
        if application_files:
            for app_file in application_files:
                try:
                    with open(app_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if ('SpringBootApplication' in content or 
                            'SpringApplication.run' in content or
                            'Spring Boot' in content or
                            '@EnableAutoConfiguration' in content or
                            'spring-boot' in content.lower()):
                            logger.info(f"Found Spring Boot Application class: {app_file}")
                            return True
                except Exception as e:
                    logger.error(f"Error reading application file {app_file}: {e}")
        
        # Check for application.properties or application.yml
        spring_config_files = []
        try:
            for pattern in ["**/src/**/application.properties", "**/src/**/application.yml", "**/src/**/application.yaml",
                            "**/application.properties", "**/application.yml", "**/application.yaml",
                            "**/src/**/bootstrap.properties", "**/src/**/bootstrap.yml", "**/src/**/bootstrap.yaml"]:
                spring_config_files.extend(list(Path(repo_path).glob(pattern)))
        except Exception as e:
            logger.error(f"Error finding Spring config files: {e}")
            # Fallback to os.walk
            config_filenames = ["application.properties", "application.yml", "application.yaml",
                               "bootstrap.properties", "bootstrap.yml", "bootstrap.yaml"]
            for root, _, files in os.walk(repo_path):
                for file in files:
                    if file in config_filenames:
                        spring_config_files.append(Path(os.path.join(root, file)))
        
        if spring_config_files:
            logger.info(f"Found Spring Boot configuration files: {spring_config_files}")
            return True
        
        # Check for Spring Boot wrapper files
        wrapper_files = []
        try:
            wrapper_files = list(Path(repo_path).glob("**/mvnw"))
            wrapper_files.extend(Path(repo_path).glob("**/gradlew"))
        except Exception as e:
            logger.error(f"Error finding wrapper files: {e}")
            # Fallback to os.walk
            for root, _, files in os.walk(repo_path):
                for file in files:
                    if file in ["mvnw", "gradlew"]:
                        wrapper_files.append(Path(os.path.join(root, file)))
        
        if wrapper_files:
            # Check for wrapper properties files
            wrapper_props = False
            try:
                mvn_wrapper_props = list(Path(repo_path).glob("**/.mvn/wrapper/maven-wrapper.properties"))
                gradle_wrapper_props = list(Path(repo_path).glob("**/gradle/wrapper/gradle-wrapper.properties"))
                wrapper_props = len(mvn_wrapper_props) > 0 or len(gradle_wrapper_props) > 0
            except Exception as e:
                logger.error(f"Error finding wrapper properties: {e}")
                # Fallback to manual path check
                mvn_wrapper_path = os.path.join(repo_path, ".mvn", "wrapper", "maven-wrapper.properties")
                gradle_wrapper_path = os.path.join(repo_path, "gradle", "wrapper", "gradle-wrapper.properties")
                wrapper_props = os.path.exists(mvn_wrapper_path) or os.path.exists(gradle_wrapper_path)
            
            if wrapper_props:
                logger.info(f"Found Spring Boot wrapper files: {wrapper_files}")
                return True
        
        # Scan all Java files for Spring Boot imports
        java_files = []
        try:
            java_files = list(Path(repo_path).glob("**/*.java"))
        except Exception as e:
            logger.error(f"Error finding Java files: {e}")
            # Fallback to os.walk
            for root, _, files in os.walk(repo_path):
                for file in files:
                    if file.endswith(".java"):
                        java_files.append(Path(os.path.join(root, file)))
        
        for java_file in java_files[:20]:  # Limit to first 20 files to avoid excessive processing
            try:
                with open(java_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if ('org.springframework.boot' in content or 
                        'SpringBootApplication' in content or
                        'SpringApplication' in content or
                        '@EnableAutoConfiguration' in content):
                        logger.info(f"Found Spring Boot imports in Java file: {java_file}")
                        return True
            except Exception as e:
                logger.error(f"Error reading Java file {java_file}: {e}")
        
        # Last resort: check for Spring dependencies in any XML or build files
        for root, _, files in os.walk(repo_path):
            for file in files:
                if file.endswith(".xml") or "build" in file.lower() or "pom" in file.lower():
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            content = f.read().lower()
                            if "org.springframework.boot" in content or "spring-boot" in content:
                                logger.info(f"Found Spring Boot reference in file: {os.path.join(root, file)}")
                                return True
                    except Exception as e:
                        logger.error(f"Error reading file {os.path.join(root, file)}: {e}")
        
        return False
    
    def _is_maven_spring_boot(self, repo_path: str, pom_files: list = None) -> dict:
        """
        Check if the Maven project is a Spring Boot project.
        Returns a dictionary with analysis results.
        """
        result = {
            'is_spring_boot': False,
            'version': None
        }
        
        if pom_files is None:
            pom_files = self._find_maven_files(repo_path)
        
        for pom_file in pom_files:
            try:
                # First try quick check with string search
                with open(pom_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Quick check for spring-boot string before parsing XML
                    if 'spring-boot' in content.lower() or 'org.springframework.boot' in content.lower():
                        logger.info(f"Found Spring Boot reference in POM file: {pom_file}")
                        result['is_spring_boot'] = True
                        
                        # Try to extract version using regex
                        version_match = re.search(r'<parent>\s*<groupId>org\.springframework\.boot</groupId>\s*<artifactId>spring-boot-starter-parent</artifactId>\s*<version>([^<]+)</version>', content)
                        if version_match:
                            result['version'] = version_match.group(1)
                            logger.info(f"Found Spring Boot version via regex: {result['version']}")
                
                # Parse XML for more detailed analysis if needed
                try:
                    tree = ET.parse(pom_file)
                    root = tree.getroot()
                    
                    # Remove namespace for easier parsing
                    namespace = root.tag.split('}')[0] + '}' if '}' in root.tag else ''
                    
                    # Check if the parent is spring-boot-starter-parent
                    parent_elements = root.findall(f"{namespace}parent")
                    for parent in parent_elements:
                        artifact_id = parent.find(f"{namespace}artifactId")
                        if artifact_id is not None and "spring-boot-starter-parent" in artifact_id.text:
                            result['is_spring_boot'] = True
                            
                            # Get version if available
                            version = parent.find(f"{namespace}version")
                            if version is not None:
                                result['version'] = version.text
                                logger.info(f"Found Spring Boot version: {version.text}")
                            break
                    
                    # Check for Spring Boot dependencies
                    deps = root.findall(f".//{namespace}dependencies/{namespace}dependency")
                    for dep in deps:
                        group_id = dep.find(f"{namespace}groupId")
                        artifact_id = dep.find(f"{namespace}artifactId")
                        
                        if group_id is not None and "org.springframework.boot" in group_id.text:
                            result['is_spring_boot'] = True
                            
                            # Try to get version if not found yet
                            if not result.get('version'):
                                version = dep.find(f"{namespace}version")
                                if version is not None:
                                    result['version'] = version.text
                                    logger.info(f"Found Spring Boot dependency version: {version.text}")
                            break
                        
                        if artifact_id is not None and "spring-boot" in artifact_id.text:
                            result['is_spring_boot'] = True
                            
                            # Try to get version if not found yet
                            if not result.get('version'):
                                version = dep.find(f"{namespace}version")
                                if version is not None:
                                    result['version'] = version.text
                                    logger.info(f"Found Spring Boot dependency version: {version.text}")
                            break
                    
                    # Check for Spring Boot Maven plugin
                    plugins = root.findall(f".//{namespace}plugins/{namespace}plugin")
                    for plugin in plugins:
                        group_id = plugin.find(f"{namespace}groupId")
                        artifact_id = plugin.find(f"{namespace}artifactId")
                        
                        if (group_id is not None and "org.springframework.boot" in group_id.text) or \
                        (artifact_id is not None and "spring-boot-maven-plugin" in artifact_id.text):
                            result['is_spring_boot'] = True
                            
                            # Try to get version if not found yet
                            if not result.get('version'):
                                version = plugin.find(f"{namespace}version")
                                if version is not None:
                                    result['version'] = version.text
                                    logger.info(f"Found Spring Boot plugin version: {version.text}")
                            break
                except ET.ParseError as e:
                    logger.error(f"Error parsing XML in POM file {pom_file}: {e}")
                    # If XML parsing fails but we already found Spring Boot via string matching, 
                    # we can still return the result
                    if result['is_spring_boot']:
                        return result
                
                # If we found Spring Boot in this POM, no need to check others
                if result['is_spring_boot']:
                    return result
                    
            except Exception as e:
                logger.error(f"Error processing POM file {pom_file}: {e}")
        
        # If we get here without returning, do a fallback check for Spring Boot directory structure
        if not result['is_spring_boot']:
            result['is_spring_boot'] = self._deep_spring_boot_check(repo_path)
        
        return result
    
    def _is_gradle_spring_boot(self, repo_path: str, gradle_files: list = None) -> dict:
        """
        Check if the Gradle project is a Spring Boot project.
        Returns a dictionary with analysis results.
        """
        result = {
            'is_spring_boot': False,
            'version': None
        }
        
        if gradle_files is None:
            gradle_files = self._find_gradle_files(repo_path)
        
        for gradle_file in gradle_files:
            try:
                with open(gradle_file, 'r', encoding='utf-8') as file:
                    content = file.read()
                    
                    # Check for Spring Boot plugin or dependency
                    if "org.springframework.boot" in content:
                        result['is_spring_boot'] = True
                        logger.info(f"Found Spring Boot reference in Gradle file: {gradle_file}")
                        
                        # Try to extract version
                        spring_boot_version_match = re.search(r'org\.springframework\.boot[\'"]?\s*:\s*[\'"]?spring-boot[^\'"\s]*[\'"]?\s*:\s*[\'"]?([0-9]+\.[0-9]+\.[0-9]+(?:\.[A-Z0-9]+)?)[\'"]?', content)
                        if spring_boot_version_match:
                            result['version'] = spring_boot_version_match.group(1)
                            logger.info(f"Found Spring Boot version: {result['version']}")
                        
                        # Also look for version as a property
                        spring_boot_version_prop = re.search(r'springBootVersion\s*=\s*[\'"]([0-9]+\.[0-9]+\.[0-9]+(?:\.[A-Z0-9]+)?)[\'"]', content)
                        if spring_boot_version_prop and not result.get('version'):
                            result['version'] = spring_boot_version_prop.group(1)
                            logger.info(f"Found Spring Boot version from property: {result['version']}")
                    
                    if "spring-boot" in content:
                        result['is_spring_boot'] = True
                        logger.info(f"Found Spring Boot reference in Gradle file: {gradle_file}")
                    
                    # If we found it, no need to check other files
                    if result['is_spring_boot']:
                        return result
            
            except Exception as e:
                logger.error(f"Error reading Gradle file {gradle_file}: {e}")
        
        # If we get here without returning, do a fallback check for Spring Boot directory structure
        if not result['is_spring_boot']:
            result['is_spring_boot'] = self._deep_spring_boot_check(repo_path)
        
        return result 