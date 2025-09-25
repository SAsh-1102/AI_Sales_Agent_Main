from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .voice_utils import text_to_speech, speech_to_text
from agent.casual_responses import casual_responses
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
import pytz
import re
import os
import json
import tempfile
import base64
import requests
import logging

from agent.memory_service import save_message, get_history
from agent.prompts import SALES_CHATBOT_PROMPT

# Import ChromaDB product search functions
from agent.memory_manager import (
    search_products,
    get_product_by_category,
    get_all_categories,
    get_products_in_price_range,
)

# Setup logging
logger = logging.getLogger(__name__)

# Pakistan timezone
PAKISTAN_TZ = pytz.timezone("Asia/Karachi")

# Get API key from environment variables (more secure)
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

def index(request):
    return render(request, "index.html")

def extract_intent_and_search(user_message):
    """
    Dynamically analyze user message and search for relevant products.
    Returns formatted product information based on the query.
    """
    try:
        message_lower = user_message.lower()

        # 1. Search ChromaDB for relevant products
        search_results = search_products(user_message, n_results=5)

        # 2. Category detection
        categories = get_all_categories()
        for category in categories:
            if category.lower() in message_lower or category.lower().rstrip("s") in message_lower:
                category_results = get_product_by_category(category, n_results=6)
                if category_results:
                    search_results = category_results
                    break

        # 3. Price-related queries
        price_pattern = r"\$?(\d+)(?:\s*(?:to|-)?\s*\$?(\d+))?"
        price_match = re.search(price_pattern, user_message)
        if price_match and (
            "budget" in message_lower
            or "price" in message_lower
            or "under" in message_lower
            or "between" in message_lower
        ):
            min_price = int(price_match.group(1))
            max_price = int(price_match.group(2)) if price_match.group(2) else min_price + 500
            if "under" in message_lower:
                max_price = min_price
                min_price = 0

            price_results = get_products_in_price_range(min_price, max_price, n_results=5)
            if price_results:
                search_results = price_results

        # 4. Format results
        if search_results:
            products_context = ""
            for i, product in enumerate(search_results[:5], 1):
                products_context += f"\n{i}. {product['name']} ({product['category']}) - ${product['price']}"
                desc = product.get("description", "")
                if desc:
                    key_info = (
                        desc.replace("Product:", "")
                        .replace("Category:", "")
                        .replace("Model:", "")
                        .replace("Price:", "")
                    )
                    products_context += f"\n   {key_info[:150]}..."

            return {
                "found_products": True,
                "products_context": products_context,
                "product_count": len(search_results),
                "products_data": search_results,
            }

        return {"found_products": False, "products_context": "", "product_count": 0, "products_data": []}
    
    except Exception as e:
        logger.error(f"Error in extract_intent_and_search: {str(e)}")
        return {"found_products": False, "products_context": "", "product_count": 0, "products_data": []}

def create_dynamic_system_prompt(products_info):
    """
    Build system prompt including product context.
    """
    base_prompt = """You are an expert AI sales agent for a technology store. 
You are helpful, knowledgeable, and focused on helping customers find the perfect tech products.

GUIDELINES:
- Always be conversational and engaging
- If products are found, present them clearly with specs & price
- Always mention prices
- Ask follow-up questions
- Highlight differences when comparing products
- Format with line breaks for readability
"""

    if products_info["found_products"]:
        product_prompt = f"""
Relevant products found ({products_info['product_count']} matches):
{products_info['products_context']}

Your job:
1. Acknowledge what the customer is asking
2. Present the most relevant products with highlights
3. Suggest why each one is useful
4. End with a helpful follow-up question
"""
    else:
        try:
            categories = get_all_categories()
            category_list = ', '.join(categories) if categories else "various tech products"
        except Exception as e:
            logger.error(f"Error getting categories: {str(e)}")
            category_list = "various tech products"
            
        product_prompt = f"""
No exact products were found.

Your job:
1. Acknowledge the customer's request
2. Suggest alternatives or categories
3. Ask clarifying questions
4. Mention available categories: {category_list}
"""

    return base_prompt + product_prompt

def call_groq_api(messages):
    """
    Separate function to handle GROQ API calls with better error handling
    """
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY is not set in environment variables")
        return None, "API key not configured. Please set GROQ_API_KEY environment variable."

    try:
        # Validate messages format
        if not isinstance(messages, list) or not messages:
            logger.error("Invalid messages format")
            return None, "Invalid message format"

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 800,
        }

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}", 
            "Content-Type": "application/json"
        }

        logger.info(f"Making API call to GROQ with {len(messages)} messages")
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions", 
            headers=headers, 
            json=payload, 
            timeout=30
        )

        logger.info(f"GROQ API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                resp_json = response.json()
                if "choices" in resp_json and len(resp_json["choices"]) > 0:
                    reply_text = resp_json["choices"][0]["message"]["content"].strip()
                    logger.info("Successfully got response from GROQ API")
                    return reply_text, None
                else:
                    logger.error(f"Invalid response format: {resp_json}")
                    return None, "Invalid API response format"
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                return None, "Failed to parse API response"
        elif response.status_code == 401:
            logger.error(f"API Authentication Error: {response.text}")
            return None, "Invalid API key. Please check your GROQ_API_KEY."
        elif response.status_code == 429:
            logger.error(f"API Rate limit exceeded: {response.text}")
            return None, "Rate limit exceeded. Please try again later."
        else:
            logger.error(f"API Error: {response.status_code} - {response.text}")
            return None, f"API returned status {response.status_code}"

    except requests.exceptions.Timeout:
        logger.error("GROQ API timeout")
        return None, "API timeout - please try again"
    except requests.exceptions.ConnectionError:
        logger.error("GROQ API connection error")
        return None, "Connection error - please check your internet connection"
    except Exception as e:
        logger.error(f"Unexpected error in GROQ API call: {str(e)}")
        return None, f"API error: {str(e)}"

@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    try:
        # Validate content type
        if request.content_type != 'application/json':
            logger.warning(f"Invalid content type: {request.content_type}")
            return JsonResponse({"error": "Content-Type must be application/json"}, status=400)

        # Parse JSON body
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error: {str(e)}")
            return JsonResponse({"error": "Invalid character encoding"}, status=400)

        # Validate required fields
        user_message = data.get("message", "").strip()
        session_id = data.get("session_id", "default")

        if not user_message:
            return JsonResponse({"error": "Message field is required and cannot be empty"}, status=400)

        if len(user_message) > 1000:  # Add reasonable length limit
            return JsonResponse({"error": "Message too long (max 1000 characters)"}, status=400)

        logger.info(f"Processing message from session {session_id}: {user_message[:50]}...")

        # Save user message
        try:
            save_message(session_id, "user", user_message)
        except Exception as e:
            logger.error(f"Error saving user message: {str(e)}")
            # Continue processing even if saving fails

        # Get conversation history
        try:
            history = get_history(session_id, limit=10)
        except Exception as e:
            logger.error(f"Error getting history: {str(e)}")
            history = []

        # Product search
        products_info = extract_intent_and_search(user_message)
        logger.info(f"Product search found {products_info['product_count']} products")

        # Initialize defaults
        reply_text = "I'm having trouble processing your request right now. Please try again."
        lead_stage = "cold"
        emotion = "neutral"

        # System prompt with product context
        system_prompt = create_dynamic_system_prompt(products_info)

        # Convert history into proper messages
        messages = [{"role": "system", "content": system_prompt}]
        
        try:
            for h in history:
                role = "assistant" if h.sender == "agent" else "user"
                messages.append({"role": role, "content": h.message})
        except Exception as e:
            logger.error(f"Error processing history: {str(e)}")
            # Continue with just system prompt and current message

        # Append current user input
        messages.append({"role": "user", "content": user_message})

        # Call GROQ API
        api_response, error = call_groq_api(messages)

        if api_response:
            reply_text = api_response
            
            # Lead stage logic
            if products_info["found_products"]:
                if products_info["product_count"] == 1:
                    lead_stage = "hot"
                elif products_info["product_count"] <= 3:
                    lead_stage = "warm"
                else:
                    lead_stage = "interested"
                emotion = "helpful"
            else:
                lead_stage = "curious"
                emotion = "friendly"
        else:
            # Fallback response when API fails
            logger.warning(f"API failed: {error}. Using fallback response.")
            
            if products_info["found_products"]:
                product_list = [
                    f"• {p['name']} - ${p['price']} ({p['category']})" 
                    for p in products_info["products_data"][:3]
                ]
                reply_text = "I found some great options for  you:\n\n" + "\n".join(product_list)
                reply_text += "\n\nWould you like more details about any of these products?"
                lead_stage = "warm"
                emotion = "helpful"
            else:
                try:
                    categories = get_all_categories()
                    if categories:
                        reply_text = f"I can help you find tech products! We have items in these categories: {', '.join(categories)}. What specifically are you looking for?"
                    else:
                        reply_text = "I'm here to help you find the perfect tech products! What are you looking for today?"
                except Exception as e:
                    logger.error(f"Error getting categories for fallback: {str(e)}")
                    reply_text = "I'm here to help you find the perfect tech products! What are you looking for today?"

        # Save agent response
        try:
            save_message(session_id, "agent", reply_text)
        except Exception as e:
            logger.error(f"Error saving agent response: {str(e)}")
            # Continue even if saving fails

        # Updated history
        try:
            history = get_history(session_id, limit=50)
            history_data = [
                {
                    "sender": h.sender,
                    "message": h.message,
                    "timestamp": h.timestamp.astimezone(PAKISTAN_TZ).strftime("%d-%m-%Y %I:%M:%S %p"),
                }
                for h in history
            ]
        except Exception as e:
            logger.error(f"Error formatting history: {str(e)}")
            history_data = []

        return JsonResponse(
            {
                "reply": reply_text,
                "lead_stage": lead_stage,
                "emotion": emotion,
                "history": history_data,
                "debug_info": {
                    "products_found": products_info["product_count"],
                    "search_successful": products_info["found_products"],
                    "api_used": api_response is not None,
                    "api_error": error if error else None,
                },
            }
        )

    except Exception as e:
        logger.error(f"Unexpected error in chat_api: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def voice_api(request):
    action = request.GET.get("action", "tts")

    try:
        if action == "tts":
            try:
                data = json.loads(request.body.decode("utf-8"))
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON format"}, status=400)
            
            text = data.get("text", "").strip()
            if not text:
                return JsonResponse({"error": "Text field is required"}, status=400)
            
            if len(text) > 500:  # Add reasonable limit
                return JsonResponse({"error": "Text too long (max 500 characters)"}, status=400)
            
            try:
                audio_path = text_to_speech(text)
                with open(audio_path, "rb") as f:
                    audio_bytes = f.read()
                os.remove(audio_path)
                audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
                return JsonResponse({"audio_base64": audio_base64})
            except Exception as e:
                logger.error(f"Error in text-to-speech: {str(e)}")
                return JsonResponse({"error": "Text-to-speech failed"}, status=500)

        elif action == "stt":
            audio_file = request.FILES.get("audio")
            if not audio_file:
                return JsonResponse({"error": "No audio file provided"}, status=400)

            # Add file size limit (10MB)
            if audio_file.size > 10 * 1024 * 1024:
                return JsonResponse({"error": "Audio file too large (max 10MB)"}, status=400)

            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    for chunk in audio_file.chunks():
                        tmp.write(chunk)
                    temp_path = tmp.name

                text = speech_to_text(temp_path)
                os.remove(temp_path)
                return JsonResponse({"text": text})
            except Exception as e:
                logger.error(f"Error in speech-to-text: {str(e)}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return JsonResponse({"error": "Speech-to-text failed"}, status=500)

        else:
            return JsonResponse({"error": "Invalid action. Use ?action=tts or ?action=stt"}, status=400)
    
    except Exception as e:
        logger.error(f"Unexpected error in voice_api: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)