from strands.models.openai import OpenAIModel
from app.config import settings
def _model():
    # Use config variables instead of resetting them to empty strings
    #MODEL_ID = settings.model_id
    #API_KEY = settings.api_key
    #BASE_URl = settings.base_url
    
    
    model = OpenAIModel(
        client_args={
            "api_key": API_KEY,  # Uses the imported API_KEY from app.config
            "base_url": BASE_URL, # Uses the imported BASE_URL from app.config
        },
        model_id=MODEL_ID,
        params={
            "max_tokens": 4096,      # High limit to handle reasoning tokens without clipping
            "temperature": 0.6,      # Slightly lower temperature reduces agent hallucination loops
            "extra_body": {
                "allow_missing_thinking": True
            }
        }
    )
    return model
