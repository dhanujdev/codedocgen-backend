import logging
import re
import html
from typing import Dict, Any, Optional
from markdown import markdown

logger = logging.getLogger(__name__)

class MarkdownToConfluenceConverter:
    """Converts Markdown to Confluence-compatible HTML format."""
    
    @staticmethod
    def convert_markdown_to_html(markdown_text: str) -> str:
        """Convert Markdown to standard HTML."""
        try:
            return markdown(markdown_text, extensions=['tables', 'fenced_code', 'codehilite'])
        except Exception as e:
            logger.error(f"Error converting markdown to HTML: {str(e)}")
            return f"<p>Error converting markdown: {str(e)}</p>"
    
    @staticmethod
    def adjust_html_for_confluence(html_content: str) -> str:
        """
        Adjust standard HTML to be compatible with Confluence storage format.
        """
        # Replace <code> blocks with Confluence macros
        html_content = re.sub(
            r'<pre><code class="language-(\w+)">(.+?)</code></pre>',
            r'<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">\1</ac:parameter><ac:plain-text-body><![CDATA[\2]]></ac:plain-text-body></ac:structured-macro>',
            html_content, 
            flags=re.DOTALL
        )
        
        # Replace basic <code> blocks with no language specified
        html_content = re.sub(
            r'<pre><code>(.+?)</code></pre>',
            r'<ac:structured-macro ac:name="code"><ac:plain-text-body><![CDATA[\1]]></ac:plain-text-body></ac:structured-macro>',
            html_content, 
            flags=re.DOTALL
        )
        
        # Make relative images use attachment references 
        html_content = re.sub(
            r'<img src="([^http].+?)" alt="(.+?)"',
            r'<ac:image><ri:attachment ri:filename="\1" /><ac:alt-text>\2</ac:alt-text></ac:image>',
            html_content
        )
        
        return html_content
    
    @staticmethod
    def convert(markdown_text: str) -> str:
        """
        Convert markdown to Confluence-compatible HTML.
        """
        standard_html = MarkdownToConfluenceConverter.convert_markdown_to_html(markdown_text)
        confluence_html = MarkdownToConfluenceConverter.adjust_html_for_confluence(standard_html)
        return confluence_html
    
    @staticmethod
    def get_section_template() -> str:
        """
        Returns a template for a Confluence section with expand/collapse support.
        """
        return """
        <ac:structured-macro ac:name="expand">
            <ac:parameter ac:name="title">{title}</ac:parameter>
            <ac:rich-text-body>
                <p>{content}</p>
            </ac:rich-text-body>
        </ac:structured-macro>
        """
    
    @staticmethod
    def get_info_panel_template() -> str:
        """
        Returns a template for a Confluence info panel.
        """
        return """
        <ac:structured-macro ac:name="info">
            <ac:rich-text-body>
                <p>{content}</p>
            </ac:rich-text-body>
        </ac:structured-macro>
        """
    
    @staticmethod 
    def create_page_with_toc(title: str, sections: Dict[str, Any]) -> str:
        """
        Create a Confluence page with table of contents and sections.
        
        Args:
            title: The page title
            sections: Dict with section titles as keys and content as values
        
        Returns:
            Confluence storage format HTML
        """
        html_parts = [
            f"<h1>{html.escape(title)}</h1>",
            '<ac:structured-macro ac:name="toc" />'
        ]
        
        for section_title, section_content in sections.items():
            html_parts.append(f"<h2>{html.escape(section_title)}</h2>")
            
            # Handle different content types
            if isinstance(section_content, str):
                # If it's already HTML, add directly
                if section_content.strip().startswith("<"):
                    html_parts.append(section_content)
                else:
                    # Convert from markdown
                    html_parts.append(MarkdownToConfluenceConverter.convert(section_content))
            elif isinstance(section_content, dict):
                # Handle nested sections
                for subsection_title, subsection_content in section_content.items():
                    html_parts.append(f"<h3>{html.escape(subsection_title)}</h3>")
                    
                    if isinstance(subsection_content, str):
                        if subsection_content.strip().startswith("<"):
                            html_parts.append(subsection_content)
                        else:
                            html_parts.append(MarkdownToConfluenceConverter.convert(subsection_content))
        
        return "\n".join(html_parts) 