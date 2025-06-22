# llms/gemini_client.py
"""
Google Gemini client implementation for the HITL system.
Uses Gemini 2.0 Flash for creative response generation.
"""
import asyncio
import logging
from typing import List, Dict, Any

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
except ImportError:
    genai = None

from .base_client import BaseLLMClient

logger = logging.getLogger(__name__)


class GeminiClient(BaseLLMClient):
    """
    Google Gemini client for creative LLM-1 generation.
    Uses Gemini 2.0 Flash Experimental model.
    """
    
    # Gemini pricing (as of latest known rates)
    INPUT_COST_PER_TOKEN = 0.000001  # $0.001/1K tokens
    OUTPUT_COST_PER_TOKEN = 0.000002  # $0.002/1K tokens
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp"):
        """Initialize Gemini client."""
        super().__init__(api_key, model)
        
        if genai is None:
            raise ImportError(
                "google-generativeai not installed. "
                "Install with: pip install google-generativeai"
            )
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Create model instance
        self.generation_config = {
            "temperature": 0.8,  # Default temperature for creativity
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
            "response_mime_type": "text/plain",
        }
        
        # Safety settings - minimal blocking for HITL system
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        self.model_instance = genai.GenerativeModel(
            model_name=model,
            generation_config=self.generation_config,
            safety_settings=self.safety_settings
        )
        
        logger.info(f"Gemini client initialized with model: {model}")
    
    async def generate_response(self, messages: List[Dict[str, Any]], temperature: float = 0.8) -> str:
        """
        Generate response using Gemini API.
        
        Args:
            messages: OpenAI-format messages
            temperature: Sampling temperature
            
        Returns:
            Generated response text
        """
        try:
            # Convert OpenAI format to Gemini format
            gemini_prompt = self._convert_messages_to_prompt(messages)
            
            # Update temperature for this request
            config = self.generation_config.copy()
            config["temperature"] = temperature
            
            # Generate response with rate limiting consideration
            response = await self._generate_with_retry(gemini_prompt, config)
            
            # Extract text and update metrics
            response_text = response.text
            
            # Calculate token usage and cost
            self._update_usage_metrics(response)
            
            logger.info(f"Gemini response generated. Tokens: {self._last_tokens_used}, Cost: ${self._last_cost:.6f}")
            
            return response_text
            
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise Exception(f"Gemini generation failed: {str(e)}")
    
    def get_model_name(self) -> str:
        """Get the Gemini model name."""
        return self.model
    
    def _convert_messages_to_prompt(self, messages: List[Dict[str, Any]]) -> str:
        """
        Convert OpenAI message format to Gemini prompt format.
        
        Args:
            messages: OpenAI format messages
            
        Returns:
            Formatted prompt for Gemini
        """
        prompt_parts = []
        
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        # Add final prompt for response
        prompt_parts.append("Assistant:")
        
        return "\n\n".join(prompt_parts)
    
    async def _generate_with_retry(self, prompt: str, config: Dict) -> Any:
        """
        Generate response with retry logic for rate limits.
        
        Args:
            prompt: Formatted prompt
            config: Generation configuration
            
        Returns:
            Gemini response object
        """
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Create temporary model instance with updated config
                temp_model = genai.GenerativeModel(
                    model_name=self.model,
                    generation_config=config,
                    safety_settings=self.safety_settings
                )
                
                # Run in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, 
                    temp_model.generate_content, 
                    prompt
                )
                
                return response
                
            except Exception as e:
                if "rate limit" in str(e).lower() or "quota" in str(e).lower():
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Gemini rate limit hit, retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                
                # Re-raise other exceptions or final retry failure
                raise e
        
        raise Exception("Max retries exceeded for Gemini API")
    
    def _update_usage_metrics(self, response: Any) -> None:
        """
        Update token usage and cost metrics from response.
        
        Args:
            response: Gemini response object
        """
        try:
            # Get usage metadata from response
            usage_metadata = getattr(response, 'usage_metadata', None)
            
            if usage_metadata:
                prompt_tokens = getattr(usage_metadata, 'prompt_token_count', 0)
                completion_tokens = getattr(usage_metadata, 'candidates_token_count', 0)
                total_tokens = getattr(usage_metadata, 'total_token_count', 0)
                
                self._last_tokens_used = total_tokens
                self._last_cost = self._calculate_cost(prompt_tokens, completion_tokens)
            else:
                # Fallback: estimate tokens if metadata not available
                response_text = getattr(response, 'text', '')
                estimated_tokens = len(response_text.split()) * 1.3  # Rough estimation
                self._last_tokens_used = int(estimated_tokens)
                self._last_cost = self._calculate_cost(0, int(estimated_tokens))
                
        except Exception as e:
            logger.warning(f"Could not calculate Gemini usage metrics: {e}")
            self._last_tokens_used = 0
            self._last_cost = 0.0
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate cost for Gemini API usage.
        
        Args:
            prompt_tokens: Input tokens
            completion_tokens: Output tokens
            
        Returns:
            Cost in USD
        """
        input_cost = prompt_tokens * self.INPUT_COST_PER_TOKEN
        output_cost = completion_tokens * self.OUTPUT_COST_PER_TOKEN
        return input_cost + output_cost