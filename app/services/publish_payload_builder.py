import logging
from typing import Dict, List, Any, Optional
import os
import json

from ..services.markdown_to_confluence_html import MarkdownToConfluenceConverter

logger = logging.getLogger(__name__)

class PublishPayloadBuilder:
    """
    Builds payloads for publishing to Confluence by assembling content from various sources.
    """
    
    def __init__(self, repo_path: str, repo_name: str):
        """
        Initialize the payload builder.
        
        Args:
            repo_path: Path to the repository
            repo_name: Name of the repository
        """
        self.repo_path = repo_path
        self.repo_name = repo_name
        self.converter = MarkdownToConfluenceConverter()
    
    def get_api_docs_section(self, endpoints_data: Dict[str, Any]) -> str:
        """
        Generate API documentation section from endpoints data.
        
        Args:
            endpoints_data: Parsed endpoints data
            
        Returns:
            HTML content for the API docs section
        """
        sections = {}
        
        for controller_name, controller_data in endpoints_data.get("controllers", {}).items():
            controller_section = []
            
            # Controller description
            controller_section.append(f"<p>{controller_data.get('description', 'No description available.')}</p>")
            
            # Endpoints table
            controller_section.append("<table><thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead><tbody>")
            for endpoint in controller_data.get("endpoints", []):
                method = endpoint.get("method", "GET")
                path = endpoint.get("path", "/")
                description = endpoint.get("description", "No description available.")
                
                controller_section.append(f"<tr><td>{method}</td><td>{path}</td><td>{description}</td></tr>")
            
            controller_section.append("</tbody></table>")
            
            sections[f"{controller_name} Controller"] = "\n".join(controller_section)
        
        return self.converter.create_page_with_toc("API Documentation", sections)
    
    def get_feature_files_section(self, features_data: Dict[str, Any]) -> str:
        """
        Generate feature files section from feature data.
        
        Args:
            features_data: Parsed feature files data
            
        Returns:
            HTML content for the feature files section
        """
        sections = {}
        
        for feature in features_data.get("features", []):
            feature_title = feature.get("title", "Feature")
            feature_description = feature.get("description", "No description available.")
            
            feature_content = [f"<p>{feature_description}</p>", "<h3>Scenarios</h3>"]
            
            for scenario in feature.get("scenarios", []):
                scenario_title = scenario.get("title", "Scenario")
                feature_content.append(f"<h4>{scenario_title}</h4>")
                
                if scenario.get("steps"):
                    feature_content.append("<ul>")
                    for step in scenario.get("steps", []):
                        feature_content.append(f"<li>{step}</li>")
                    feature_content.append("</ul>")
            
            sections[feature_title] = "\n".join(feature_content)
        
        return self.converter.create_page_with_toc("Feature Files", sections)
    
    def get_diagrams_section(self, diagrams_data: Dict[str, Dict[str, Any]]) -> str:
        """
        Generate diagrams section from available diagrams.
        
        Args:
            diagrams_data: Dictionary of diagram types to their data
            
        Returns:
            HTML content for the diagrams section
        """
        sections = {}
        
        for diagram_type, diagram_data in diagrams_data.items():
            if diagram_data.get("status") == "success" and diagram_data.get("diagram_url"):
                # Create section with embedded image
                sections[f"{diagram_type.replace('-', ' ').title()} Diagram"] = f"""
                <p>Generated {diagram_type} diagram:</p>
                <p><img src="{diagram_data.get('diagram_url')}" alt="{diagram_type} diagram"></p>
                """
            elif diagram_data.get("puml_source"):
                # Create section with code block for PUML source
                sections[f"{diagram_type.replace('-', ' ').title()} Diagram"] = f"""
                <p>Generated {diagram_type} diagram source:</p>
                <ac:structured-macro ac:name="code">
                    <ac:parameter ac:name="language">puml</ac:parameter>
                    <ac:plain-text-body><![CDATA[{diagram_data.get('puml_source')}]]></ac:plain-text-body>
                </ac:structured-macro>
                """
        
        if not sections:
            sections["Diagrams"] = "<p>No diagrams available.</p>"
        
        return self.converter.create_page_with_toc("System Diagrams", sections)
    
    def get_flow_section(self, flows_data: Dict[str, Any]) -> str:
        """
        Generate flow summaries section from flow data.
        
        Args:
            flows_data: Parsed flow data
            
        Returns:
            HTML content for the flow summaries section
        """
        sections = {}
        
        for flow_name, flow in flows_data.get("flows", {}).items():
            flow_content = []
            
            flow_content.append(f"<p>{flow.get('description', 'No description available.')}</p>")
            
            # Flow steps
            if flow.get("steps"):
                flow_content.append("<ol>")
                for step in flow.get("steps", []):
                    flow_content.append(f"<li>{step}</li>")
                flow_content.append("</ol>")
            
            # Technical details
            if flow.get("technical_details"):
                flow_content.append("<h3>Technical Details</h3>")
                flow_content.append("<ul>")
                for detail in flow.get("technical_details", []):
                    flow_content.append(f"<li>{detail}</li>")
                flow_content.append("</ul>")
            
            sections[flow_name] = "\n".join(flow_content)
        
        return self.converter.create_page_with_toc("Flow Summaries", sections)
    
    def build_documentation_payload(self, 
                                   selected_sections: List[str],
                                   endpoints_data: Optional[Dict[str, Any]] = None,
                                   features_data: Optional[Dict[str, Any]] = None,
                                   diagrams_data: Optional[Dict[str, Dict[str, Any]]] = None,
                                   flows_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Build the full documentation payload based on selected sections.
        
        Args:
            selected_sections: List of section IDs to include ("api_docs", "features", "diagrams", "flows")
            endpoints_data: Optional pre-loaded endpoints data
            features_data: Optional pre-loaded features data
            diagrams_data: Optional pre-loaded diagrams data
            flows_data: Optional pre-loaded flows data
            
        Returns:
            Dictionary with sections content
        """
        from ..services.endpoint_parser import EndpointParser
        from ..services.feature_builder import FeatureBuilder
        from ..services.flow_analyzer import FlowAnalyzer
        from ..services.diagram_renderer import DiagramRenderer
        
        sections_content = {}
        
        # Process each requested section
        for section in selected_sections:
            if section == "api_docs":
                if not endpoints_data:
                    parser = EndpointParser()
                    endpoints_data = parser.parse_endpoints(self.repo_path)
                
                sections_content["API Documentation"] = self.get_api_docs_section(endpoints_data)
                
            elif section == "features":
                if not features_data:
                    builder = FeatureBuilder()
                    features_data = builder.extract_feature_files(self.repo_path)
                
                sections_content["Feature Files"] = self.get_feature_files_section(features_data)
                
            elif section == "diagrams":
                if not diagrams_data:
                    diagrams_data = {}
                    renderer = DiagramRenderer(self.repo_path)
                    
                    # Generate all diagram types including comprehensive versions
                    diagram_types = [
                        "use-case", 
                        "comprehensive-use-case", 
                        "interaction", 
                        "comprehensive-interaction", 
                        "class"
                    ]
                    
                    for diagram_type in diagram_types:
                        diagrams_data[diagram_type] = renderer.generate_diagram(diagram_type)
                
                sections_content["System Diagrams"] = self.get_diagrams_section(diagrams_data)
                
            elif section == "flows":
                if not flows_data:
                    analyzer = FlowAnalyzer(self.repo_path)
                    flows_data = analyzer.analyze_flows()
                
                sections_content["Flow Summaries"] = self.get_flow_section(flows_data)
        
        # Create introduction section
        intro_content = f"""
        <p>This documentation was automatically generated for the <strong>{self.repo_name}</strong> repository.</p>
        <p>Table of contents:</p>
        <ul>
        """
        
        for section_title in sections_content.keys():
            intro_content += f"<li>{section_title}</li>"
        
        intro_content += "</ul>"
        
        sections_content = {"Introduction": intro_content, **sections_content}
        
        return sections_content 