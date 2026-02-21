"""
AI Summary Service
Generates AI-powered summaries of corporate announcements
Supports multiple AI providers: Groq (free), Claude, OpenAI
"""

import re
import hashlib
from datetime import date
from io import BytesIO
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests
from utils.config import config
from utils.logger import get_logger

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

class AISummaryService:
    """Generates AI summaries using configured provider"""

    PLACEHOLDER_KEYS = {
        "your_groq_api_key_here",
        "your_claude_api_key_here",
        "your_openai_api_key_here",
    }
    
    def __init__(self, db_manager=None):
        """Init.

        Args:
            db_manager: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        self.logger = get_logger(__name__)
        self.db = db_manager
        self.provider = config.AI_PROVIDER
        self.client = None
        self.groq_client = None
        self.last_error = None

        groq_key = self._normalize_api_key(config.GROQ_API_KEY)
        claude_key = self._normalize_api_key(config.CLAUDE_API_KEY)
        openai_key = self._normalize_api_key(config.OPENAI_API_KEY)
        
        # Initialize the appropriate AI client
        if self.provider == 'groq' and groq_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=groq_key)
                self.groq_client = self.client
            except ImportError:
                self.logger.warning("Groq package not installed. Run: pip install groq")
        
        elif self.provider == 'claude' and claude_key:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=claude_key)
            except ImportError:
                self.logger.warning("Anthropic package not installed. Run: pip install anthropic")
        
        elif self.provider == 'openai' and openai_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=openai_key)
            except ImportError:
                self.logger.warning("OpenAI package not installed. Run: pip install openai")
        elif self.provider == 'ollama':
            # Local provider via HTTP API. No SDK/client object required.
            self.client = True

    def _get_groq_client(self):
        """Get groq client.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        key = self._normalize_api_key(config.GROQ_API_KEY)
        if not key:
            return None
        if self.groq_client is not None:
            return self.groq_client
        try:
            from groq import Groq
            self.groq_client = Groq(api_key=key)
            return self.groq_client
        except Exception:
            return None
    
    def is_available(self) -> bool:
        """Check if AI service is available"""
        return self.client is not None

    def _model_name_for_provider(self, provider: str) -> str:
        """Model name for provider.

        Args:
            provider: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        p = (provider or "").lower()
        if p == "ollama":
            return config.OLLAMA_MODEL or "ollama"
        if p == "groq":
            return "llama-3.3-70b-versatile"
        if p == "claude":
            return "claude-haiku-4-5-20251001"
        if p == "openai":
            return "gpt-3.5-turbo"
        return "unknown"

    def _active_model_name(self) -> str:
        """Active model name.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        return self._model_name_for_provider(self.provider)

    @staticmethod
    def _prompt_hash(prompt: str) -> str:
        """Prompt hash.

        Args:
            prompt: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        return hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()

    def _generate_with_provider(self, prompt: str, max_tokens: int = 500, provider: str = None) -> Optional[Dict]:
        """Generate with provider.

        Args:
            prompt: Input parameter.
            max_tokens: Input parameter.
            provider: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        target_provider = (provider or self.provider or "").lower()
        if target_provider == 'groq':
            groq_client = self._get_groq_client()
            if not groq_client:
                return None
            return self._generate_groq_summary(prompt, max_tokens=max_tokens, groq_client=groq_client)
        elif target_provider == 'claude':
            return self._generate_claude_summary(prompt, max_tokens=max_tokens)
        elif target_provider == 'openai':
            return self._generate_openai_summary(prompt, max_tokens=max_tokens)
        elif target_provider == 'ollama':
            return self._generate_ollama_summary(prompt, max_tokens=max_tokens)
        return None

    def _generate_with_cache_for_provider(
        self, task_type: str, prompt: str, provider: str, max_tokens: int = 500
    ) -> Optional[Dict]:
        """Generate with cache for provider.

        Args:
            task_type: Input parameter.
            prompt: Input parameter.
            provider: Input parameter.
            max_tokens: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        target_provider = (provider or self.provider or "").lower()
        model = self._model_name_for_provider(target_provider)
        prompt_hash = self._prompt_hash(prompt)
        if self.db and config.AI_CACHE_ENABLED:
            cached = self.db.get_ai_response_cache(task_type, target_provider, model, prompt_hash)
            if cached:
                return {
                    "summary_text": cached.get("response_text") or "",
                    "sentiment": cached.get("sentiment") or self._extract_sentiment(cached.get("response_text") or ""),
                    "provider": target_provider,
                    "model": model,
                    "cache_hit": True,
                }

        generated = self._generate_with_provider(prompt, max_tokens=max_tokens, provider=target_provider)
        if generated and (generated.get("summary_text") or "").strip() and self.db and config.AI_CACHE_ENABLED:
            self.db.upsert_ai_response_cache(
                task_type=task_type,
                provider=target_provider,
                model=model,
                prompt_hash=prompt_hash,
                response_text=generated.get("summary_text") or "",
                sentiment=generated.get("sentiment"),
            )
            generated["cache_hit"] = False
        return generated

    def _generate_with_cache(self, task_type: str, prompt: str, max_tokens: int = 500) -> Optional[Dict]:
        """Generate with cache.

        Args:
            task_type: Input parameter.
            prompt: Input parameter.
            max_tokens: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        return self._generate_with_cache_for_provider(
            task_type=task_type,
            prompt=prompt,
            provider=self.provider,
            max_tokens=max_tokens,
        )
    
    def generate_summary(self, stock_symbol: str, announcement_text: str, 
                        announcement_type: str = "ANNOUNCEMENT",
                        document_url: str = None) -> Optional[Dict]:
        """
        Generate AI summary of corporate announcement
        
        Args:
            stock_symbol: Stock symbol (e.g., RELIANCE.NS)
            announcement_text: Full announcement text
            announcement_type: Type of announcement
        
        Returns:
            Dict with summary_text and sentiment, or None if failed
        """
        if not self.is_available():
            return None
        
        document_text = ""
        if document_url:
            document_text = self._extract_pdf_text_from_url(document_url)

        combined_text = announcement_text or ""
        if document_text:
            combined_text = f"{combined_text}\n\n[Extracted PDF Text]\n{document_text}".strip()

        # Create prompt
        prompt = self._create_prompt(stock_symbol, combined_text, announcement_type)
        
        try:
            return self._generate_with_cache(task_type="summary", prompt=prompt, max_tokens=500)
        
        except Exception as e:
            self.last_error = str(e)
            self.logger.error("Error generating AI summary: %s", e)
            return None

    def generate_analyst_consensus(
        self,
        company_name: str,
        stock_symbol: str = "",
        current_price: Optional[float] = None,
        as_of_date: Optional[str] = None,
    ) -> Optional[Dict]:
        """Generate analyst consensus style report for one company."""
        if not self.is_available():
            return None

        as_of = as_of_date or date.today().isoformat()
        price_text = "NA" if current_price is None else f"{current_price:.2f}"
        symbol_text = f" ({stock_symbol})" if stock_symbol else ""
        prompt = f"""You are an experienced financial research analyst covering the Indian stock market.
Provide consensus analyst view for company <<{company_name}{symbol_text}>> as of {as_of}.

Output strictly in this format:
{company_name} - Analyst Consensus (as of {as_of})
| Metric | Value |
|---|---|
| Current price (Rs) | {price_text} |
| Consensus price target | ... |
| Price-target range (analysts) | ... |
| 12-month price target | ... |
| Buy/Sell rating | ... |

Executive Summary (max 100 words): ...

Rules:
- Use concise factual language.
- If unavailable, write NA.
- No extra sections.
"""
        try:
            target_provider = config.ANALYST_AI_PROVIDER or self.provider
            result = self._generate_with_cache_for_provider(
                task_type="analyst_consensus",
                prompt=prompt,
                provider=target_provider,
                max_tokens=260
            )
            if result:
                return result
            return self._generate_with_cache(task_type="analyst_consensus", prompt=prompt, max_tokens=260)
        except Exception as e:
            self.last_error = str(e)
            self.logger.error("Error generating analyst consensus: %s", e)
            return None

    def _extract_pdf_text_from_url(self, document_url: str, timeout: int = 20, max_chars: int = 24000) -> str:
        """Download PDF and extract text in-memory. Returns empty string on failure."""
        if PdfReader is None:
            return ""

        for idx, url in enumerate(self._build_pdf_candidate_urls(document_url)):
            try:
                response = requests.get(
                    url,
                    timeout=timeout,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": "https://www.bseindia.com/",
                    },
                )
                response.raise_for_status()
                pdf_bytes = BytesIO(response.content)
                reader = PdfReader(pdf_bytes)
                parts = []
                for page in reader.pages[:12]:
                    page_text = (page.extract_text() or "").strip()
                    if page_text:
                        parts.append(page_text)
                    if sum(len(p) for p in parts) >= max_chars:
                        break
                text = "\n".join(parts).strip()
                if text:
                    if idx > 0:
                        self.logger.info("PDF extraction succeeded using fallback URL: %s", url)
                    return text[:max_chars]
            except Exception:
                continue
        return ""

    @staticmethod
    def _extract_pdf_filename(value: str) -> str:
        """Extract pdf filename.

        Args:
            value: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        text = (value or "").strip()
        if not text:
            return ""
        parsed = urlparse(text)
        candidate = parsed.path.split("/")[-1] if parsed.path else text.split("/")[-1]
        candidate = candidate.split("?")[0].strip()
        return candidate if candidate.lower().endswith(".pdf") else ""

    @staticmethod
    def _join_base_and_filename(base_url: str, filename: str) -> str:
        """Join base and filename.

        Args:
            base_url: Input parameter.
            filename: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        base = (base_url or "").strip()
        if not base or not filename:
            return ""
        if not base.endswith("/"):
            base = f"{base}/"
        return f"{base}{filename}"

    def _build_pdf_candidate_urls(self, document_url: str) -> List[str]:
        """Build pdf candidate urls.

        Args:
            document_url: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        value = (document_url or "").strip()
        if not value:
            return []

        filename = self._extract_pdf_filename(value)
        candidates: List[str] = []

        # Preferred order: configured primary, configured secondary, then provided URL.
        if filename:
            primary = self._join_base_and_filename(config.BSE_ATTACH_PRIMARY_BASE, filename)
            secondary = self._join_base_and_filename(config.BSE_ATTACH_SECONDARY_BASE, filename)
            if primary:
                candidates.append(primary)
            if secondary and secondary not in candidates:
                candidates.append(secondary)

        if value.startswith("http://") or value.startswith("https://"):
            if value not in candidates:
                candidates.append(value)
        elif filename:
            # Resolve relative path for robustness.
            resolved = f"https://www.bseindia.com/{value.lstrip('/')}"
            if resolved not in candidates:
                candidates.append(resolved)

        return candidates

    @classmethod
    def _normalize_api_key(cls, value: str) -> str:
        """Treat empty/template values as not configured."""
        key = (value or "").strip()
        if not key or key in cls.PLACEHOLDER_KEYS:
            return ""
        return key
    
    def _create_prompt(self, stock_symbol: str, announcement_text: str, 
                      announcement_type: str) -> str:
        """Create the prompt for AI summary"""
        ann_type = (announcement_type or "").strip().lower()
        if ann_type == "results":
            return self._create_results_prompt(stock_symbol, announcement_text, announcement_type)
        if ann_type == "earnings call":
            return self._create_earnings_call_prompt(stock_symbol, announcement_text, announcement_type)

        return self._create_non_results_prompt(stock_symbol, announcement_text, announcement_type)

    def _create_results_prompt(self, stock_symbol: str, announcement_text: str, announcement_type: str) -> str:
        """Prompt template for results filings with structured metrics extraction."""
        quick_metrics_hint = self._extract_quick_financial_metrics(announcement_text)
        return f"""You are an AI designed to generate concise summaries of quarterly results based on filings for {stock_symbol}.
Your task is to create a structured summary that highlights the most important aspects of the filings without listing all similar filings.

Input:
- Announcement Type: {announcement_type}
- Source Content (document URL and/or extracted text blob):
{announcement_text}

Use these parsed hints if relevant:
{quick_metrics_hint}

Output Format (follow strictly):
Result Summary
Revenue: [Insert value or 'NA'] | YoY: [Insert value or 'NA'] | QoQ: [Insert value or 'NA']
EBITDA: [Insert value or 'NA'] | YoY: [Insert value or 'NA'] | QoQ: [Insert value or 'NA']
PAT: [Insert value or 'NA'] | YoY: [Insert value or 'NA'] | QoQ: [Insert value or 'NA']
EPS: [Insert value or 'NA'] | YoY: [Insert value or 'NA'] | QoQ: [Insert value or 'NA']
Special Items: [Insert details or 'None highlighted']

Additional Management Insights: [Summarize any commentary or insights shared by management in a professional tone.]

Instructions:
1. Extract and summarize only key financial metrics from the current quarter.
2. If a metric is not explicitly present, return 'NA'. Do not infer or invent numbers.
3. Identify special items clearly (exceptional items, one-offs, guidance changes, notable wins/losses).
4. Capture notable management commentary briefly and factually.
5. Ensure clarity, conciseness, and focus on current quarter data only.
6. Do not enumerate multiple similar filings."""

    @staticmethod
    def _create_earnings_call_prompt(stock_symbol: str, announcement_text: str, announcement_type: str) -> str:
        """Prompt template for conference call analysis."""
        return f"""You are an AI designed to generate concise summaries of conference call transcripts based on filings for {stock_symbol}.
Your task is to create a structured summary that highlights the most important aspects of the filings without listing all similar filings.

Input:
- Announcement Type: {announcement_type}
- Source Content (document URL and/or extracted text blob):
{announcement_text}

Output format (strict):
Summary:
- [One concise overall summary for quick scan]

Management Commentary:
- [Brief overview of management perspective on performance, challenges, strategy]

Business Insights:
- [Insights on business environment, market conditions, competitive landscape]

Forward Guidance and Outlook:
- [Guidance for upcoming quarters/fiscal year, growth/cost outlook, expectations]

Risks:
- [Key internal and external risks mentioned]

Earnings Trigger:
- [Potential positive triggers and expected timelines]

Instructions:
1. Keep output concise and structured.
2. Focus on current quarter-relevant data only.
3. If a section is not present in the source, write 'NA'.
4. Avoid generic statements and avoid listing repetitive similar filings."""

    @staticmethod
    def _create_non_results_prompt(stock_symbol: str, announcement_text: str, announcement_type: str) -> str:
        """Prompt template for non-results filings."""
        return f"""You are an advanced financial announcements analyst.

Analyze this announcement for {stock_symbol}.
Type: {announcement_type}
Content:
{announcement_text}

Output format (strict):
Summary: [3-5 concise lines covering what happened and why it matters for investors]
SENTIMENT: [Positive/Neutral/Negative]

Rules:
1. Keep it brief and factual.
2. Do not invent numbers or facts not present in the content.
3. Focus on the key disclosure, timeline, and investor relevance."""

    @staticmethod
    def _extract_quick_financial_metrics(announcement_text: str) -> str:
        """
        Extract lightweight metric hints (Revenue/EBITDA/PAT/EPS with YoY/QoQ mentions)
        to guide model output without inventing numbers.
        """
        text = re.sub(r"\s+", " ", (announcement_text or "")).strip()
        if not text:
            return "No numeric hints detected."

        metric_patterns = {
            "Revenue": r"(revenue[^.:\n]{0,120})",
            "EBITDA": r"(ebitda[^.:\n]{0,120})",
            "PAT": r"((?:pat|profit after tax)[^.:\n]{0,120})",
            "EPS": r"(eps[^.:\n]{0,120})",
        }
        yoy_pattern = r"(\d+(?:\.\d+)?\s*%\s*(?:yoy|y\/y|year[\s-]*over[\s-]*year))"
        qoq_pattern = r"(\d+(?:\.\d+)?\s*%\s*(?:qoq|q\/q|quarter[\s-]*over[\s-]*quarter))"

        lines = []
        for label, pattern in metric_patterns.items():
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                lines.append(f"{label}: NA")
                continue

            snippet = match.group(1)
            yoy = re.search(yoy_pattern, snippet, flags=re.IGNORECASE)
            qoq = re.search(qoq_pattern, snippet, flags=re.IGNORECASE)
            lines.append(
                f"{label}: {snippet.strip()} | YoY hint: {(yoy.group(1) if yoy else 'NA')} | "
                f"QoQ hint: {(qoq.group(1) if qoq else 'NA')}"
            )

        special_match = re.search(
            r"(exceptional|one[\s-]*off|guidance|order win|acquisition|bonus|fund raise)[^.]{0,140}",
            text,
            flags=re.IGNORECASE
        )
        lines.append(f"Special hint: {(special_match.group(0).strip() if special_match else 'None')}")
        return "\n".join(lines)
    
    def _generate_groq_summary(self, prompt: str, max_tokens: int = 500, groq_client=None) -> Dict:
        """Generate summary using Groq"""
        client = groq_client or self.client
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Free tier model
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.3
        )
        
        summary_text = response.choices[0].message.content
        sentiment = self._extract_sentiment(summary_text)
        
        return {
            'summary_text': summary_text,
            'sentiment': sentiment,
            'provider': 'groq'
        }
    
    def _generate_claude_summary(self, prompt: str, max_tokens: int = 500) -> Dict:
        """Generate summary using Claude"""
        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",  # Most economical
            max_tokens=max_tokens,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        summary_text = response.content[0].text
        sentiment = self._extract_sentiment(summary_text)
        
        return {
            'summary_text': summary_text,
            'sentiment': sentiment,
            'provider': 'claude'
        }
    
    def _generate_openai_summary(self, prompt: str, max_tokens: int = 500) -> Dict:
        """Generate summary using OpenAI"""
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.3
        )
        
        summary_text = response.choices[0].message.content
        sentiment = self._extract_sentiment(summary_text)
        
        return {
            'summary_text': summary_text,
            'sentiment': sentiment,
            'provider': 'openai'
        }

    def _generate_ollama_summary(self, prompt: str, max_tokens: int = 500) -> Dict:
        """Generate summary using local Ollama HTTP API."""
        base = config.OLLAMA_BASE_URL.rstrip("/")
        models = []
        if config.OLLAMA_MODEL:
            models.append(config.OLLAMA_MODEL)
        for model in config.OLLAMA_FALLBACK_MODELS:
            if model not in models:
                models.append(model)

        last_error = None
        for model in models:
            timeout_sec = (
                config.OLLAMA_TIMEOUT_PRIMARY_SEC
                if model == config.OLLAMA_MODEL
                else config.OLLAMA_TIMEOUT_FALLBACK_SEC
            )
            try:
                response = requests.post(
                    f"{base}/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "num_predict": max_tokens,
                        },
                    },
                    timeout=timeout_sec,
                )
                response.raise_for_status()
                payload = response.json() or {}
                msg = payload.get("message") or {}
                summary_text = (msg.get("content") or "").strip()
                if not summary_text:
                    continue
                sentiment = self._extract_sentiment(summary_text)
                return {
                    'summary_text': summary_text,
                    'sentiment': sentiment,
                    'provider': 'ollama',
                    'model': model,
                }
            except Exception as exc:
                last_error = exc
                self.logger.warning("Ollama model failed: %s (%s)", model, exc)
                continue

        if last_error:
            raise last_error
        raise RuntimeError("Ollama did not return a valid response for any configured model.")
    
    def _extract_sentiment(self, summary_text: str) -> str:
        """Extract sentiment from summary"""
        summary_lower = summary_text.lower()
        
        # Look for explicit sentiment marker
        if 'sentiment: positive' in summary_lower or 'sentiment:** positive' in summary_lower:
            return 'POSITIVE'
        elif 'sentiment: negative' in summary_lower or 'sentiment:** negative' in summary_lower:
            return 'NEGATIVE'
        elif 'sentiment: neutral' in summary_lower or 'sentiment:** neutral' in summary_lower:
            return 'NEUTRAL'
        
        # Fallback: analyze content
        positive_words = ['positive', 'growth', 'increase', 'profit', 'success', 'strong', 'up']
        negative_words = ['negative', 'decline', 'loss', 'weak', 'down', 'concern', 'risk']
        
        positive_count = sum(1 for word in positive_words if word in summary_lower)
        negative_count = sum(1 for word in negative_words if word in summary_lower)
        
        if positive_count > negative_count:
            return 'POSITIVE'
        elif negative_count > positive_count:
            return 'NEGATIVE'
        
        return 'NEUTRAL'
