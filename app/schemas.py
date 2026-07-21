from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    display_name: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class CreateSessionResponse(BaseModel):
    sessionId: str
    originalTranscript: str
    normalizedCondition: str
    sampleIntervalMs: int


class StartSessionRequest(BaseModel):
    condition: str = Field(min_length=3, max_length=1000)
    fcmToken: str | None = Field(default=None, min_length=20, max_length=4096)


class DeviceTokenRequest(BaseModel):
    fcmToken: str = Field(min_length=20, max_length=4096)


class FrameResult(BaseModel):
    accepted: bool
    matched: bool
    confidence: float | None = None


class SessionOut(BaseModel):
    id: str
    condition: str
    status: str
    sampleIntervalMs: int
    confidence: float | None


class ConditionInterpretation(BaseModel):
    normalized_condition: str = Field(description="A concise, visually observable condition in present tense")
    is_visually_observable: bool
    clarification: str | None = None


class VisionDecision(BaseModel):
    matched: bool = Field(description="True only when the condition is visibly satisfied in this image")
    confidence: float = Field(ge=0, le=1)
    explanation: str = Field(max_length=300)
