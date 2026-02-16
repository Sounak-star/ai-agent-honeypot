import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from agent.llm_clients import GeminiClient, OpenAIClient, extract_json_object


URGENCY_PATTERN = re.compile(
    r"(?i)\b(urgent|immediately|right now|within \d+ (minute|minutes|hour|hours)|final warning|last warning)\b"
)
AUTHORITY_PATTERN = re.compile(
    r"(?i)\b(bank|sbi|security team|fraud team|customs|police|rbi|compliance|official)\b"
)
REWARD_PATTERN = re.compile(r"(?i)\b(prize|lottery|reward|cashback|gift|bonus|offer)\b")
VERIFY_PATTERN = re.compile(
    r"(?i)\b(verify|verification|otp|one time password|pin|upi pin|cvv|account number)\b"
)
LINK_PRESSURE_PATTERN = re.compile(
    r"(?i)\b(click|open|tap|visit)\b.*\b(link|url|site|website)\b|\bhttps?://\S+|www\.\S+"
)
ALT_CHANNEL_PATTERN = re.compile(r"(?i)\b(call|whatsapp|telegram|email|contact)\b")


@dataclass(frozen=True)
class BehavioralAnalysisResult:
    score: float
    confidence: float
    indicators: List[str]
    category_hint: Optional[str]


class BehaviorAnalyzer:
    def _rule_based_analysis(self, text: str) -> BehavioralAnalysisResult:
        if not text:
            return BehavioralAnalysisResult(score=0.0, confidence=0.0, indicators=[], category_hint=None)

        indicators: List[str] = []
        score = 0.0

        if URGENCY_PATTERN.search(text):
            score += 2.0
            indicators.append("urgency")
        if AUTHORITY_PATTERN.search(text):
            score += 2.0
            indicators.append("authority_impersonation")
        if REWARD_PATTERN.search(text):
            score += 1.5
            indicators.append("reward_bait")
        if VERIFY_PATTERN.search(text):
            score += 2.5
            indicators.append("verification_or_secret_request")
        if LINK_PRESSURE_PATTERN.search(text):
            score += 2.0
            indicators.append("external_link_pressure")
        if ALT_CHANNEL_PATTERN.search(text):
            score += 1.0
            indicators.append("alternate_channel_push")

        category = None
        if "reward_bait" in indicators:
            category = "LOTTERY_SCAM"
        elif "external_link_pressure" in indicators:
            category = "PHISHING"
        elif "verification_or_secret_request" in indicators and "authority_impersonation" in indicators:
            category = "BANK_FRAUD"

        confidence = min(1.0, score / 8.0)
        return BehavioralAnalysisResult(
            score=round(min(10.0, score), 2),
            confidence=round(confidence, 2),
            indicators=sorted(set(indicators)),
            category_hint=category,
        )

    def _llm_analysis(
        self,
        text: str,
        openai: Optional[OpenAIClient],
        gemini: Optional[GeminiClient],
    ) -> Optional[BehavioralAnalysisResult]:
        if not text:
            return None
        if not ((openai and openai.api_key) or (gemini and gemini.api_key)):
            return None

        system_prompt = (
            "Analyze scam intent behavior in the message and return ONLY JSON with keys:\n"
            "- riskScore: number 0-10\n"
            "- confidence: number 0-1\n"
            "- indicators: string[] (urgency, authority_impersonation, reward_bait, "
            "verification_or_secret_request, external_link_pressure, alternate_channel_push)\n"
            "- categoryHint: string (UPI_FRAUD, PHISHING, BANK_FRAUD, LOTTERY_SCAM, REFUND_SCAM, GENERIC_SCAM)\n"
            "No prose."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

        raw = None
        if openai and openai.api_key:
            raw = openai.chat(
                messages,
                temperature=0.0,
                max_tokens=180,
                response_format={"type": "json_object"},
            )
        if not raw and gemini and gemini.api_key:
            raw = gemini.chat(messages, temperature=0.0, max_tokens=180)
        if not raw:
            return None

        payload = extract_json_object(raw)
        if not isinstance(payload, dict):
            return None

        try:
            score = float(payload.get("riskScore", 0.0))
            confidence = float(payload.get("confidence", 0.0))
        except (TypeError, ValueError):
            return None

        indicators_raw = payload.get("indicators") or []
        if isinstance(indicators_raw, list):
            indicators = [str(i).strip() for i in indicators_raw if str(i).strip()]
        else:
            indicators = []
        category_hint = payload.get("categoryHint")
        category_hint = str(category_hint).strip() if category_hint else None

        return BehavioralAnalysisResult(
            score=round(max(0.0, min(10.0, score)), 2),
            confidence=round(max(0.0, min(1.0, confidence)), 2),
            indicators=sorted(set(indicators)),
            category_hint=category_hint,
        )

    def analyze(
        self,
        text: str,
        openai: Optional[OpenAIClient],
        gemini: Optional[GeminiClient],
    ) -> BehavioralAnalysisResult:
        rule_result = self._rule_based_analysis(text)
        llm_result = self._llm_analysis(text, openai, gemini)
        if not llm_result:
            return rule_result

        combined_score = (rule_result.score * 0.6) + (llm_result.score * 0.4)
        combined_confidence = max(rule_result.confidence, llm_result.confidence)
        combined_indicators = sorted(set(rule_result.indicators).union(llm_result.indicators))
        category_hint = llm_result.category_hint or rule_result.category_hint

        return BehavioralAnalysisResult(
            score=round(min(10.0, combined_score), 2),
            confidence=round(min(1.0, combined_confidence), 2),
            indicators=combined_indicators,
            category_hint=category_hint,
        )

