import time
from typing import Optional

from ..interfaces import ImageAnalyzer
from ..models import AIResult

class StubImageAnalyzer(ImageAnalyzer):
    """
    A stub image analyzer that returns 'Flood Water' if the media type is 'image'.
    Used for the demo scenario. Real implementations would call a vision model.
    """
    async def analyze(self, image_bytes: Optional[bytes], content_type: str) -> AIResult:
        start_time = time.time()
        
        category = "Unknown"
        confidence = 0.0
        summary = ""
        
        if content_type.startswith("image"):
            category = "Flood Water"
            confidence = 0.88
            summary = "Visual evidence of urban waterlogging/flooding."
            
        processing_time = (time.time() - start_time) * 1000
        
        return AIResult(
            prediction=category,
            confidence=confidence,
            provider="StubImageAnalyzer",
            model_version="1.0.0",
            processing_time_ms=processing_time,
            fallback_triggered=True,
            metadata={"evidence_summary": summary}
        )
