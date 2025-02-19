import uuid
from dataclasses import dataclass

@dataclass
class BaseResponse:
    provider: str
    model: str
    response: str

class ProviderResponseGenerator:
    @staticmethod
    def get_generator(provider):
        generators = {
            'openai': OpenAIResponseGenerator,
            'anthropic': AnthropicResponseGenerator,
            'google': GoogleResponseGenerator
        }
        return generators.get(provider, DefaultResponseGenerator)

class OpenAIResponseGenerator:
    @staticmethod
    def generate_response(model, prompt):
        response_id = f"openai_response_{str(uuid.uuid4())[:8]}"
        return BaseResponse(
            provider="openai",
            model=model,
            response=f"OpenAI: Processed prompt '{prompt}' with model {model}. Response ID: {response_id}"
        ).__dict__

class GoogleResponseGenerator:
    @staticmethod
    def generate_response(model, prompt):
        response_id = f"google_response_{str(uuid.uuid4())[:8]}"
        return BaseResponse(
            provider="google",
            model=model,
            response=f"Google: Processed prompt '{prompt}' with model {model}. Response ID: {response_id}"
        ).__dict__

class AnthropicResponseGenerator:
    @staticmethod
    def generate_response(model, prompt):
        response_id = f"anthropic_response_{str(uuid.uuid4())[:8]}"
        return BaseResponse(
            provider="anthropic",
            model=model,
            response=f"Anthropic: Processed prompt '{prompt}' with model {model}. Response ID: {response_id}"
        ).__dict__

class DefaultResponseGenerator:
    @staticmethod
    def generate_response(model, prompt):
        return BaseResponse(
            provider="unknown",
            model=model,
            response="Unknown provider requested. Please use a supported provider."
        ).__dict__