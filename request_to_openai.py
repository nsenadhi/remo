import base64
import requests
from openai import OpenAI
import os
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
import json
import logging

load_dotenv()
api_key = os.getenv("OPENAI_KEY")

client = OpenAI(api_key=api_key)
logger = logging.getLogger(__name__)

def _encode_image(image_path):
    """Encode image to base64"""
    try:
        image = Image.open(image_path)
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        image_byte_data = buffered.getvalue()
        return base64.b64encode(image_byte_data).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encoding image {image_path}: {e}")
        return ""


def gpt(text,
        model_name,
        image_path=list(),
        system_prompt='You are a helpful assistant.',
        temperature=1,
        previous_response_id=None,
        conversation_history=None,
        use_responses_api=True):

    
    # ========================================================================
    # ATTEMPT 1: Try Responses API (if requested)
    # ========================================================================
    if use_responses_api:
        try:
            # Build input message properly for Responses API
            if len(image_path) == 0:
                # Simple text - try as string first
                input_data = text
            else:
                # With images - build message content
                content = [{"type": "text", "text": text}]
                
                for img_path in image_path:
                    base64_image = _encode_image(img_path)
                    if base64_image:
                        content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "low"
                            }
                        })
                
                input_data = [{"role": "user", "content": content}]
            
            logger.info(f"📡 Attempting Responses API (previous_id: {previous_response_id[:20] + '...' if previous_response_id else 'None'})")
            
            response = client.responses.create(
                model=model_name,
                instructions=system_prompt,
                input=input_data,
                previous_response_id=previous_response_id,
                temperature=temperature,
                max_output_tokens=4000
            )
            
            output = response.output_text
            response_id = response.id
            
            logger.info(f"✅ Responses API success - response_id: {response_id[:20]}...")
            
            # Handle intent detection JSON
            if "intent" in system_prompt.lower() and "patient_id" in system_prompt.lower():
                try:
                    parsed = json.loads(output)
                    required_fields = ['patient_id', 'list_date', 'list_time', 'vital_sign',
                                       'is_plot', 'recognition', 'is_image', 'data_format']
                    for field in required_fields:
                        if field not in parsed:
                            parsed[field] = [] if field in ['list_date', 'list_time', 'vital_sign'] else False
                    return json.dumps(parsed), response_id
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ Invalid JSON: {output[:100]}...")
                    return json.dumps({
                        "patient_id": "",
                        "list_date": [],
                        "list_time": [],
                        "vital_sign": [],
                        "is_plot": False,
                        "recognition": False,
                        "is_image": False,
                        "data_format": "raw"
                    }), response_id
            
            return output, response_id
            
        except Exception as e:
            logger.warning(f"⚠️ Responses API failed: {e}")
            logger.info("🔄 Falling back to Chat Completions API...")
    try:
        logger.info("📡 Using Chat Completions API (standard mode)")
        
        # Build messages array
        messages = []
        
        # Add system message
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)
        
        # Build user message content
        if len(image_path) == 0:
            # Text only
            user_content = text
        else:
            # With images
            user_content = [{"type": "text", "text": text}]
            
            for img_path in image_path:
                base64_image = _encode_image(img_path)
                if base64_image:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": "low"
                        }
                    })
        
        messages.append({
            "role": "user",
            "content": user_content
        })
        
        # Call Chat Completions API
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=4000
        )
        
        output = response.choices[0].message.content
        
        logger.info("✅ Chat Completions API success")
        
        # Handle intent detection JSON
        if "intent" in system_prompt.lower() and "patient_id" in system_prompt.lower():
            try:
                parsed = json.loads(output)
                required_fields = ['patient_id', 'list_date', 'list_time', 'vital_sign',
                                   'is_plot', 'recognition', 'is_image', 'data_format']
                for field in required_fields:
                    if field not in parsed:
                        parsed[field] = [] if field in ['list_date', 'list_time', 'vital_sign'] else False
                return json.dumps(parsed), None  # No response_id in fallback mode
            except json.JSONDecodeError:
                logger.warning(f"⚠️ Invalid JSON: {output[:100]}...")
                return json.dumps({
                    "patient_id": "",
                    "list_date": [],
                    "list_time": [],
                    "vital_sign": [],
                    "is_plot": False,
                    "recognition": False,
                    "is_image": False,
                    "data_format": "raw"
                }), None
        
        return output, None  # Return None for response_id in fallback mode
        
    except Exception as e:
        logger.error(f"❌ Chat Completions API Error: {e}")
        
        # Error message
        error_msg = "I'm having trouble processing your request. Please try again."
        
        # For intent detection errors
        if "intent" in system_prompt.lower():
            return json.dumps({
                "patient_id": "",
                "list_date": [],
                "list_time": [],
                "vital_sign": [],
                "is_plot": False,
                "recognition": False,
                "is_image": False,
                "data_format": "raw"
            }), None
        
        return error_msg, None