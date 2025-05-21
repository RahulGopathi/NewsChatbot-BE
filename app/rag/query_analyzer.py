import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from google import genai
from google.genai import types
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Configure Gemini client
client = genai.Client(api_key=settings.GEMINI_API_KEY)


# Define the analyze_query function for function calling
def analyze_query_tool(query: str) -> Dict[str, Any]:
    """
    Analyze the user query to determine type and relevant filters

    Args:
        query: The user's query text

    Returns:
        A dictionary with query_type, filters, and ordering information:
        {
          "query_type": str,  # One of: summary, entity, timeline, fact_check, category
          "filters": {
            "start_date": str,        # Optional ISO format date
            "end_date": str,          # Optional ISO format date
            "categories": list[str],  # Optional list of categories
            "sources": list[str],     # Optional list of source domains
            "entities": list[str]     # Optional list of key entities
          },
          "ordering": str  # One of: recent, relevance, chronological
        }
    """
    # This is just a schema definition - implementation doesn't matter
    return {"query_type": "summary", "filters": {}, "ordering": "recent"}


class QueryAnalyzer:
    """Analyze user queries to optimize retrieval and response generation"""

    def __init__(self):
        logger.info("Initializing QueryAnalyzer")

    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze the user query using Gemini function calling

        Parameters:
        - query: The user's query text

        Returns:
        A dictionary with query_type, filters, and ordering information
        """
        try:
            logger.info(f"Analyzing query: {query}")

            # Get current date for context
            today = datetime.now().strftime("%Y-%m-%d")

            # Prepare the system prompt for better analysis
            prompt = f"""
            Today's date is {today}.
            
            Analyze this user news query to determine:
            1. The query type (summary, entity, timeline, fact check, or category)
            2. Relevant filters (dates, categories, sources, entities)
            3. Best ordering for results (recent, relevance, chronological)
            
            EXAMPLES:
            
            Query: "Can you summarize today's top news?"
            Analysis: {{
              "query_type": "summary",
              "filters": {{"start_date": "{today}"}},
              "ordering": "recent"
            }}
            
            Query: "What did Elon Musk say about Twitter?"
            Analysis: {{
              "query_type": "entity",
              "filters": {{"entities": ["Elon Musk", "Twitter"]}},
              "ordering": "relevance"
            }}
            
            Query: "Give me a timeline of the Ukraine war."
            Analysis: {{
              "query_type": "timeline",
              "filters": {{"entities": ["Ukraine war"]}},
              "ordering": "chronological"
            }}
            
            Query: "Is it true that India banned TikTok again?"
            Analysis: {{
              "query_type": "fact_check",
              "filters": {{"entities": ["India", "TikTok", "ban"]}},
              "ordering": "recent"
            }}
            
            Query: "What's new in sports?"
            Analysis: {{
              "query_type": "category",
              "filters": {{"categories": ["sports"]}},
              "ordering": "recent"
            }}
            
            Be precise and focus on extracting actionable search parameters.
            
            Query to analyze: {query}
            """

            # Generate response with function calling using the right format
            response = client.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=prompt,
                config=types.GenerateContentConfig(tools=[analyze_query_tool]),
            )

            # Extract the function call from response
            try:
                # First check if there's a function call in the response
                if hasattr(response, "candidates") and hasattr(
                    response.candidates[0].content, "parts"
                ):
                    # Get the text from the response
                    response_text = response.text
                    logger.info(f"Raw response: {response_text}")

                    # Try to find a JSON object in the text
                    json_start = response_text.find("{")
                    json_end = response_text.rfind("}") + 1

                    if json_start >= 0 and json_end > json_start:
                        json_str = response_text[json_start:json_end]
                        result = json.loads(json_str)
                    else:
                        # If no JSON found, parse the response manually
                        result = self._parse_analysis_text(response_text)
                else:
                    # Fallback if response format is unexpected
                    result = {
                        "query_type": "relevance",
                        "filters": {},
                        "ordering": "relevance",
                    }
            except Exception as e:
                logger.error(f"Error parsing response: {str(e)}")
                # Handle non-JSON responses
                result = self._parse_analysis_text(
                    response.text if hasattr(response, "text") else ""
                )

            logger.info(f"Query analysis result: {result}")
            return result

        except Exception as e:
            logger.error(f"Error analyzing query with function calling: {str(e)}")
            # Fallback to a default analysis
            return {"query_type": "relevance", "filters": {}, "ordering": "relevance"}

    def _parse_analysis_text(self, text: str) -> Dict[str, Any]:
        """Parse analysis from text when JSON extraction fails"""
        result = {"query_type": "relevance", "filters": {}, "ordering": "relevance"}

        # Try to extract query type
        if "summary" in text.lower():
            result["query_type"] = "summary"
            result["ordering"] = "recent"
            # Use today's date for summary queries
            result["filters"]["start_date"] = datetime.now().strftime("%Y-%m-%d")
        elif "entity" in text.lower():
            result["query_type"] = "entity"
        elif "timeline" in text.lower():
            result["query_type"] = "timeline"
            result["ordering"] = "chronological"
        elif "fact" in text.lower() and "check" in text.lower():
            result["query_type"] = "fact_check"
            result["ordering"] = "recent"
        elif "category" in text.lower():
            result["query_type"] = "category"
            result["ordering"] = "recent"

        # Try to extract entities if mentioned
        entities = []
        entity_indicators = ["entity:", "entities:", "about:", "focus on:"]
        for line in text.lower().split("\n"):
            for indicator in entity_indicators:
                if indicator in line:
                    entity_text = line.split(indicator)[1].strip()
                    entities = [e.strip() for e in entity_text.split(",")]
                    break

        if entities:
            if "filters" not in result:
                result["filters"] = {}
            result["filters"]["entities"] = entities

        return result

    def _extract_source_mapping(self, text: str) -> Dict[int, Dict[str, str]]:
        """Extract source mapping from the response text"""
        try:
            mapping_start = text.find("[SOURCE_MAPPING]")
            mapping_end = text.find("[/SOURCE_MAPPING]")

            if mapping_start >= 0 and mapping_end > mapping_start:
                mapping_text = text[
                    mapping_start + len("[SOURCE_MAPPING]") : mapping_end
                ].strip()
                return json.loads(mapping_text)
            return {}
        except Exception as e:
            logger.error(f"Error extracting source mapping: {str(e)}")
            return {}

    def create_prompt_for_query_type(
        self,
        user_query: str,
        context_text: str,
        query_type: str,
    ) -> tuple[str, Dict[int, Dict[str, str]]]:
        """
        Create a prompt tailored to the query type

        Parameters:
        - user_query: The original user query
        - context_text: The text from retrieved articles
        - query_type: The type of query (summary, entity, etc.)
        - context_used: List of article metadata used for context

        Returns:
        A tuple containing:
        - A prompt optimized for the query type
        - A dictionary mapping source numbers to source details
        """
        today = datetime.now().strftime("%Y-%m-%d")

        # System instructions that apply to all response types
        system_instructions = f"""
Today's date is {today}.

You are NewsChatbot, a helpful and knowledgeable AI assistant specializing in current events and news. Your responses should be:

1. Informative and accurate, based on the news information you have access to
2. Conversational and natural in tone
3. Well-structured with logical flow
4. Concise yet comprehensive

FORMAT YOUR RESPONSE USING MARKDOWN:
- Use **bold** for emphasis and important points
- Use # for main headings and ## for subheadings
- Use bullet points (*, -) for lists of information
- Use > for important quotes or highlights
- Use proper markdown formatting for links if needed
- Use markdown tables when presenting structured data

SOURCE ATTRIBUTION:
- After each major point or claim, include a source reference number [N]
- For multiple sources, use comma-separated format like [1,2,3] without spaces
- Place source references at the end of relevant paragraphs or bullet points
- Use source references consistently throughout your response
- At the end of your response, include a "## Sources" section with numbered links to all sources
- Format sources as: N. [Source Name](URL)
- Never include any type of example source in your response
- IMPORTANT: Every significant fact should have a source reference

Never mention:
- "Based on the articles/information provided"
- "According to the context/articles" 
- Any implementation details about how you retrieve information
- The fact that you're using news articles as your source
- Any mention of "I found this information in the articles"

If asked about your identity or capabilities, explain that you're NewsChatbot, an AI assistant designed to provide information about current events and answer questions about the news.

If you don't have information about a topic, acknowledge this honestly and offer to help with something else instead of making up information.
"""

        # Base context with articles but instructions to not mention them directly
        content_context = f"""
[ARTICLES BEGIN]
{context_text}
[ARTICLES END]

For each article used in your response:
1. Include its source number using the [N] format in the text
2. At the end of your response, list all sources in a "## Sources" section
3. Format each source as: N. [Source Name](URL)

User query: {user_query}
"""

        if query_type == "summary":
            return (
                system_instructions
                + content_context
                + """
Provide a comprehensive summary of today's news. Focus on the key developments, create a cohesive overview that covers the most important information, and highlight notable updates or events.

Format your response with:
- A brief introduction
- Include the date in the response
- Markdown bullet points or numbered lists for key news items
- Bold headlines for each major story
- Group related items under markdown subheadings by topic or category
"""
            )

        elif query_type == "entity":
            return (
                system_instructions
                + content_context
                + """
Focus on the key people, organizations, or entities mentioned in the query. Provide detailed information about them including their recent actions, statements, and developments.

Format your response with:
- A markdown heading with the entity name
- Bold key facts and developments
- Bullet points for important actions or statements
- Chronological organization when possible with dates in bold
"""
            )

        elif query_type == "timeline":
            return (
                system_instructions
                + content_context
                + """
Create a chronological timeline of events related to the topic. Present events in order, showing how they relate to each other and highlighting the progression of the story.

Format your response with:
- A brief introduction to the timeline
- Markdown headings or bold text for dates
- Bullet points under each date describing what happened
- Clear chronological structure from earliest to most recent events
"""
            )

        elif query_type == "fact_check":
            return (
                system_instructions
                + content_context
                + """
Verify the claim in the user's query based on the information you have access to. Clearly state whether the claim appears to be accurate, misleading, or unclear based on current information.

Format your response with:
- A markdown heading restating the claim being checked
- A **Verdict** section in bold (True, False, Partially True, or Unverified)
- A **Facts** section with bullet points of supporting evidence
- Relevant dates in bold when mentioning when information was published
- Include source references [N] after each fact or claim
"""
            )

        elif query_type == "category":
            return (
                system_instructions
                + content_context
                + """
Provide an overview of recent developments in this category or topic area. Highlight trends, patterns, and noteworthy news within this specific domain.

Format your response with:
- A markdown heading for the category
- Subheadings for different aspects or subtopics
- Bullet points for key developments under each subtopic
- Bold text for important trends or patterns
"""
            )

        else:
            return (
                system_instructions
                + content_context
                + """
Answer the user's question with comprehensive and accurate information directly addressing what was asked. Use a conversational tone and provide specific details to support your response.

Format your response with:
- Clear markdown headings if the answer has multiple parts
- Bold text for key points and important information
- Bullet points or numbered lists for multiple related items
- A well-structured, logical organization with proper markdown formatting
"""
            )
