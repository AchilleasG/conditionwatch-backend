import base64
from pathlib import Path
from openai import OpenAI
from ..config import Settings
from ..schemas import ConditionInterpretation, VisionDecision
from ..security import privacy_identifier


class OpenAIService:
    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key)

    def transcribe(self, path: Path) -> str:
        with path.open("rb") as audio:
            result = self.client.audio.transcriptions.create(
                model=self.settings.openai_transcribe_model,
                file=audio,
                response_format="text",
            )
        text = result if isinstance(result, str) else result.text
        if not text.strip():
            raise ValueError("The recording contained no recognizable speech")
        return text.strip()

    def normalize_condition(self, transcript: str, user_id: str) -> ConditionInterpretation:
        response = self.client.responses.parse(
            model=self.settings.openai_condition_model,
            store=self.settings.openai_store_responses,
            safety_identifier=privacy_identifier(user_id),
            input=[{
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": (
                        "Convert this spoken monitoring request into one concise condition that can be "
                        "judged from a single camera image. Preserve the user's intent. Do not invent "
                        "objects, locations, identities, or timing. Mark it non-observable if it depends "
                        "on private thoughts, off-camera events, sound alone, or future prediction.\n\n"
                        f"Request: {transcript}"
                    ),
                }],
            }],
            text_format=ConditionInterpretation,
        )
        if response.output_parsed is None:
            raise ValueError("The condition could not be interpreted")
        return response.output_parsed

    def evaluate_image(self, jpeg: bytes, condition: str, user_id: str) -> VisionDecision:
        encoded = base64.b64encode(jpeg).decode("ascii")
        response = self.client.responses.parse(
            model=self.settings.openai_vision_model,
            store=self.settings.openai_store_responses,
            safety_identifier=privacy_identifier(user_id),
            input=[{
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Evaluate only what is visibly supported by this camera frame. Return matched "
                            "only when the condition is currently satisfied. If the relevant area is "
                            "occluded, ambiguous, too dark, or off-frame, matched must be false and "
                            "confidence should reflect uncertainty.\n\n"
                            f"Condition: {condition}"
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{encoded}",
                        "detail": "low",
                    },
                ],
            }],
            text_format=VisionDecision,
        )
        if response.output_parsed is None:
            raise ValueError("The frame could not be evaluated")
        return response.output_parsed
