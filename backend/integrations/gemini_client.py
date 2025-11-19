"""
Google Gemini API Client
Wrapper for Google's Generative AI (Gemini) API
"""
import json
import re
import time
from typing import Optional, Dict, Any

import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse
from google.api_core import exceptions


class GeminiClient:
    """
    Wrapper for Google Gemini API

    Provides simple interface for text generation and JSON parsing
    """

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        """
        Initialize Gemini client

        Args:
            api_key: Google Gemini API key
            model_name: Model to use (default: gemini-1.5-flash)
        """
        if not api_key:
            raise ValueError("API key is required for Gemini client")

        self.api_key = api_key
        self.model_name = model_name

        # Configure the API
        genai.configure(api_key=api_key)

        # Initialize the model
        self.model = genai.GenerativeModel(model_name)

        # Statistics
        self.total_tokens = 0
        self.request_count = 0

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate text using Gemini API

        Args:
            prompt: User prompt
            system_prompt: System-level instructions (will be prepended to prompt)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 1.0)

        Returns:
            Generated text response
        """
        # Combine system prompt and user prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # Configure generation settings
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        )

        # Retry logic with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(
                    full_prompt,
                    generation_config=generation_config
                )

                # Extract text from response
                if response.text:
                    self.request_count += 1
                    # Note: Token counting may not be directly available in all SDK versions
                    # We'll track requests instead
                    return response.text
                else:
                    raise Exception("Empty response from Gemini API")

            except exceptions.ResourceExhausted as e:
                # Rate limit hit
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2  # Exponential backoff: 2s, 4s, 8s
                    print(f"Rate limit hit, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Rate limit exceeded after {max_retries} retries: {e}")

            except exceptions.InvalidArgument as e:
                raise Exception(f"Invalid API request: {e}")

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt)
                    print(f"Error occurred, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Failed after {max_retries} retries: {e}")

        raise Exception("Failed to generate response")

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> Dict[str, Any]:
        """
        Generate and parse JSON response from Gemini

        Handles common issues like markdown code blocks around JSON

        Args:
            prompt: User prompt
            system_prompt: System-level instructions
            max_tokens: Maximum tokens to generate

        Returns:
            Parsed JSON as dictionary
        """
        # Use lower temperature for more consistent JSON output
        response_text = self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=0.3  # Lower temperature for structured output
        )

        # Strip markdown code blocks if present
        # Pattern: ```json ... ``` or ``` ... ```
        json_text = self._strip_markdown(response_text)

        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            # Try to extract JSON from the response
            print(f"JSON parse error: {e}")
            print(f"Response text: {response_text[:500]}")

            # Try to find JSON object in the text
            json_match = re.search(r'\{.*\}', json_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

            raise Exception(f"Failed to parse JSON response: {e}\nResponse: {response_text[:200]}")

    def _strip_markdown(self, text: str) -> str:
        """
        Remove markdown code block formatting from text

        Args:
            text: Text potentially containing markdown

        Returns:
            Cleaned text
        """
        # Remove ```json ... ```
        text = re.sub(r'^```json\s*\n', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*\n', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n```\s*$', '', text, flags=re.MULTILINE)

        return text.strip()

    def get_stats(self) -> Dict[str, int]:
        """Get client statistics"""
        return {
            'request_count': self.request_count,
            'total_tokens': self.total_tokens  # May not be accurate without token counting
        }
