from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
from typing import Optional

from abc import ABC, abstractmethod

load_dotenv()
API_KEY = os.environ.get('API_KEY')

class Model(ABC):
    """
    Interface for AI models.x
    """
    
    @abstractmethod
    def invoke(self, system_prompt: str, payload: str, response_schema: Optional[type] = None) -> str:
        """
        Send a request to the model and return the response.
        
        Args:
            system_prompt: The system instruction for the model
            payload: The user content/prompt
            response_schema: Optional Pydantic model class for structured output
        """
        pass

class GeminiModel(Model):
    def invoke(self, system_prompt: str, payload: str, response_schema: Optional[type] = None) -> str:
        client = genai.Client(api_key=API_KEY)

        # Set system prompt
        config = types.GenerateContentConfig(
            system_instruction=system_prompt
        )
        
        # Enable structured output if schema is provided
        if response_schema:
            config.response_mime_type = "application/json"
            config.response_json_schema = response_schema.model_json_schema()

        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            config=config,
            contents=payload
        )
        
        return response.text