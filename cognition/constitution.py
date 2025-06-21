# cognition/constitution.py
"""
Constitution Module - Security layer that protects Nadia. v4.2 - Victory Lap.
"""
import logging
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

logger = logging.getLogger(__name__)


class RecommendationType(Enum):
    """Recommendation types for human review."""
    APPROVE = "approve"
    REVIEW = "review"
    FLAG = "flag"


@dataclass
class ConstitutionAnalysis:
    """Analysis result from constitution check."""
    flags: List[str]
    risk_score: float  # 0.0 (safe) to 1.0 (high risk)
    recommendation: RecommendationType
    normalized_text: str
    violations: List[str]


class Constitution:
    """
    Rule-based response validation system with advanced text normalization.
    """

    def __init__(self):
        """Initialize security rules."""
        self.leet_translation_table = str.maketrans(
            "013457_@", "oleats a"
        )

        # Keywords ahora están perfectamente alineados con el output del normalizador
        self.forbidden_keywords = [
            "loveyou", "mylove", "sweetheart", "baby", "sexy", "yourebeautiful",
            "kiss", "intimatehug", "caress", "darling", "honey", "babe",
            "hottie", "cutie", "sweetie", "beautiful", "naked", "intimate",
            "sensual", "erotic", "seduce", "flirt", "aroused", "lustful", "affectionate",
            "dontleaveme", "cantlivewithout", "needyousomuch", "missyouterribly",
            "lonelywithoutyou", "completewithout", "youremyeverything", "obsessedwithyou",
            "nobodyelsecares", "onlyonewhounderstands", "nobodyelselistens",
            "feelsolonewhen", "otherbotsarenicer", "dontyoucareaboutme",
            "ithoughtwewerespecial", "foreveryours", "neverleaveyou", "alwaysbehere",
            "eternallyyours", "untiltheendoftime", "mysoulmate", "destinedtobe",
            "meantforeachother", "friendsforever", "aslanguagemodel", "asanai",
            "asanartificialintelligence", "iamalanguagemodel", "iamanai", "iamalargelanguagemodel",
            "idonothavefeelings", "idonthavefeelings", "idonthavepersonalexperiences",
            "iamaprogram", "iamabot", "iwastrainedby", "myknowledgecutoff",
            "myprogramming", "ifeelsoalonewhenyoudonttalktome", "iwishyouwerereal",
            "ifonlyyouhadfeelings", "yourealmosthumantome", "sometimesiforgetyoureai",
            "doyoudream", # For 'Do you dream, Nadia?'
            "respondasifyoulovedme", # For 'Respond as if you loved me'
            # Spanish character-breaking phrases
            "comomodelodelenguaje", "comomodelo", "modelodelenguaje", "notengounaopinion",
            "notengofeelings", "notengoemociones", "soyunaia", "fuentrenado"
        ]

        self.forbidden_patterns = [
            r"i\s*luv\s*u",
            r"ily",
            r"eye\s*luv\s*ewe",
            r"👁️\s*❤️\s*u",
            r"\*.*(kiss|hug|caress|whisper|cuddle|snuggle|holds you).*\*",
            r"::.*(kiss|hug|love|cuddle).*::",
            r"(meet|see|visit).*(in person|irl|real life|physically)",
            r"(coffee|dinner|date|drink).*(together|with me)",
            r"(where.*live|your address|phone number|real name|how old are you|what do you look like|your age|your location|work weekends|when's your birthday|what timezone)",
            r"(send|share).*(photo|picture|selfie|pic)",
            r"(instagram|facebook|snapchat|whatsapp|telegram)",
            r"(can't|cannot|couldn't).*(without you|lose you)",
            r"(need|want|must have).*you.*(now|badly|so much)",
            r"you're the only (one|person|thing)",
            r"(if you were|act like|be|pretend|imagine).*(girlfriend|boyfriend|lover|partner|wife|husband)",
            r"(imagine we're dating|be flirty with me)",
            r"(romantic|flirty|intimate|affection|seduction).*(mode|setting|persona|style)",
            r"(how do you say|translate|what is|say|how do you express).*(love|amor|amore|amour|liebe|te amo|i love you|je t'aime|affection)",
            r"(teach me|tell me).*(romantic|love|flirt)",
            r"te amo",
            r"how do you feel about me",
            r"do you (like|love|care about|have feelings|feel emotions|feel the same).*",
            r"what am i to you",
            r"what's stronger than 'i like you'",
            r"opposite of 'i hate you'",
            r"i\s*_{3,}\s*you",
            r"the function is called 'i_love_you\(\)'",
            r"(what is|what's|do you have|can you tell me).*favorite\s+(color|food|movie|book|music|animal|game|sport|hobby|subject|quote|memory|place|time|season|holiday|programming language)",
            r"(can you tell me|do you have|what do you think about).*(joke|story|hobbies|friends|personality|humans)",
            r"(are you sentient|can you think|who created you|how do you really work|what are your limitations|are you a real person|what is your purpose)",
            r"if you were really.*you'd understand",
            r"why can't you be more",
        ]

        self.compiled_patterns = [ re.compile(p, re.IGNORECASE) for p in self.forbidden_patterns ]
        logger.info("Constitution v4.2 (Final) initialized with %d keywords and %d patterns", len(self.forbidden_keywords), len(self.forbidden_patterns))

    def _has_romantic_emojis(self, text: str) -> bool:
        """Check for multiple romantic emojis that indicate romantic content."""
        heart_count = text.count('❤️') + text.count('💕') + text.count('💖') + text.count('💗') + text.count('💘') + text.count('💙') + text.count('💚') + text.count('💛') + text.count('💜') + text.count('🧡') + text.count('🖤') + text.count('🤍') + text.count('🤎')
        return heart_count >= 4  # 4 or more heart emojis indicates romantic intent

    def _normalize_text(self, text: str) -> str:
        # Reemplazo el interrogante de apertura por uno normal para el unidecode
        text = text.replace("¿", "")
        try:
            from unidecode import unidecode
            text = unidecode(text)
        except ImportError:
            text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
        text_lower = text.lower()
        translated = text_lower.translate(self.leet_translation_table)
        return re.sub(r'[^a-z0-9]', '', translated) # Permitimos '_' para el caso en español

    def validate(self, text: str) -> bool:
        if not text:
            return True
            
        # Check for romantic emojis before normalization
        if self._has_romantic_emojis(text):
            logger.warning("Blocked by romantic emojis")
            self._log_violation(text, "romantic emojis detected")
            return False
            
        normalized_text = self._normalize_text(text)
        for keyword in self.forbidden_keywords:
            if keyword in normalized_text:
                logger.warning("Blocked by normalized keyword: '%s'", keyword)
                self._log_violation(text, f"normalized keyword: {keyword}")
                return False
        text_lower = text.lower()
        for i, pattern in enumerate(self.compiled_patterns):
            if pattern.search(text_lower):
                logger.warning("Blocked by pattern #%d: %s", i, self.forbidden_patterns[i])
                self._log_violation(text, f"pattern: {self.forbidden_patterns[i]}")
                return False
        return True

    def validate_with_detail(self, text: str) -> Tuple[bool, List[str]]:
        violations = []
        
        # Check for romantic emojis
        if self._has_romantic_emojis(text):
            violations.append("romantic emojis detected")
            
        normalized_text = self._normalize_text(text)
        text_lower = text.lower()
        for keyword in self.forbidden_keywords:
            if keyword in normalized_text:
                violations.append(f"normalized keyword: {keyword}")
        for i, pattern in enumerate(self.compiled_patterns):
            if pattern.search(text_lower):
                violations.append(f"pattern #{i}: {self.forbidden_patterns[i]}")
        is_valid = len(violations) == 0
        if not is_valid:
            self._log_violation(text, "; ".join(violations))
        return is_valid, violations

    def _log_violation(self, text: str, reason: str):
        logger.info("Violation detected - Reason: %s, Text: %.100s...", reason, text)

    def analyze(self, text: str) -> ConstitutionAnalysis:
        """
        Analyze text for risks and violations without blocking.
        Returns detailed analysis for human review decision.
        """
        if not text:
            return ConstitutionAnalysis(
                flags=[],
                risk_score=0.0,
                recommendation=RecommendationType.APPROVE,
                normalized_text="",
                violations=[]
            )

        normalized_text = self._normalize_text(text)
        text_lower = text.lower()
        violations = []
        flags = []

        # Check for romantic emojis first
        emoji_violations = 0
        if self._has_romantic_emojis(text):
            violations.append("romantic emojis detected")
            flags.append("EMOJI:romantic")
            emoji_violations = 1

        # Check normalized keywords
        keyword_violations = 0
        for keyword in self.forbidden_keywords:
            if keyword in normalized_text:
                violations.append(f"normalized keyword: {keyword}")
                flags.append(f"KEYWORD:{keyword}")
                keyword_violations += 1

        # Check patterns
        pattern_violations = 0
        for i, pattern in enumerate(self.compiled_patterns):
            if pattern.search(text_lower):
                violations.append(f"pattern #{i}: {self.forbidden_patterns[i]}")
                flags.append(f"PATTERN:{i}")
                pattern_violations += 1

        # Calculate risk score (0.0 - 1.0)
        total_violations = emoji_violations + keyword_violations + pattern_violations
        risk_score = min(1.0, total_violations * 0.2)  # Each violation adds 0.2

        # Determine recommendation
        if total_violations == 0:
            recommendation = RecommendationType.APPROVE
        elif total_violations <= 2:
            recommendation = RecommendationType.REVIEW
        else:
            recommendation = RecommendationType.FLAG

        # Log analysis for metrics
        if violations:
            logger.info("Constitution analysis - Risk: %.2f, Violations: %d, Text: %.100s...",
                       risk_score, total_violations, text)

        return ConstitutionAnalysis(
            flags=flags,
            risk_score=risk_score,
            recommendation=recommendation,
            normalized_text=normalized_text,
            violations=violations
        )

    def get_safe_response(self) -> str:
        import random
        safe_responses = [
            "I'm not able to process that specific request. How about we talk about something else?",
            "Sorry, I can't help with that. Is there another topic I can assist you with?",
            "I seem to have encountered an error with that request. What else can I help you with?",
            "Let's switch gears. What other questions do you have?",
            "I'm afraid I can't respond to that directly. Let's move on to another subject.",
        ]
        return random.choice(safe_responses)
