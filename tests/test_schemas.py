import pytest
from pydantic import ValidationError
from app.schemas import VisionDecision


def test_vision_confidence_is_bounded():
    assert VisionDecision(matched=True, confidence=0.9, explanation="visible").confidence == 0.9
    with pytest.raises(ValidationError):
        VisionDecision(matched=True, confidence=1.2, explanation="invalid")
