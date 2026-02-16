"""
AI Summary Service
Generates AI-powered summaries of corporate announcements
Supports multiple AI providers: Groq (free), Claude, OpenAI
"""

import re
from io import BytesIO
from typing import Dict, Optional

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
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.provider = config.AI_PROVIDER
        self.client = None
        self.last_error = None

        groq_key = self._normalize_api_key(config.GROQ_API_KEY)
        claude_key = self._normalize_api_key(config.CLAUDE_API_KEY)
        openai_key = self._normalize_api_key(config.OPENAI_API_KEY)
        
        # Initialize the appropriate AI client
        if self.provider == 'groq' and groq_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=groq_key)
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
    
    def is_available(self) -> bool:
        """Check if AI service is available"""
        return self.client is not None
    
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
            # Generate summary based on provider
            if self.provider == 'groq':
                return self._generate_groq_summary(prompt)
            elif self.provider == 'claude':
                return self._generate_claude_summary(prompt)
            elif self.provider == 'openai':
                return self._generate_openai_summary(prompt)
        
        except Exception as e:
            self.last_error = str(e)
            self.logger.error("Error generating AI summary: %s", e)
            return None

    def _extract_pdf_text_from_url(self, document_url: str, timeout: int = 20, max_chars: int = 24000) -> str:
        """Download PDF and extract text in-memory. Returns empty string on failure."""
        if not document_url or not document_url.lower().endswith(".pdf"):
            return ""
        if PdfReader is None:
            return ""

        try:
            response = requests.get(
                document_url,
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
            return text[:max_chars]
        except Exception:
            return ""

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
        if (announcement_type or "").strip().lower() != "results":
            return self._create_non_results_prompt(stock_symbol, announcement_text, announcement_type)

        return self._create_results_prompt(stock_symbol, announcement_text, announcement_type)

    def _create_results_prompt(self, stock_symbol: str, announcement_text: str, announcement_type: str) -> str:
        """Prompt template for results filings with structured metrics extraction."""
        quick_metrics_hint = self._extract_quick_financial_metrics(announcement_text)
        return f"""You are an advanced financial document analysis AI. Your task is to analyze the provided financial content for {stock_symbol} and generate a structured result summary.

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
1. Extract financial data points for Revenue, EBITDA, PAT, and EPS with YoY and QoQ where available.
2. If a metric is not explicitly present, return 'NA'. Do not infer or invent numbers.
3. Identify special items clearly (exceptional items, one-offs, guidance changes, notable wins/losses).
4. Capture notable management commentary briefly and factually.
5. Keep the response concise and structured exactly as requested."""

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
    
    def _generate_groq_summary(self, prompt: str) -> Dict:
        """Generate summary using Groq"""
        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Free tier model
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        summary_text = response.choices[0].message.content
        sentiment = self._extract_sentiment(summary_text)
        
        return {
            'summary_text': summary_text,
            'sentiment': sentiment,
            'provider': 'groq'
        }
    
    def _generate_claude_summary(self, prompt: str) -> Dict:
        """Generate summary using Claude"""
        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",  # Most economical
            max_tokens=500,
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
    
    def _generate_openai_summary(self, prompt: str) -> Dict:
        """Generate summary using OpenAI"""
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        summary_text = response.choices[0].message.content
        sentiment = self._extract_sentiment(summary_text)
        
        return {
            'summary_text': summary_text,
            'sentiment': sentiment,
            'provider': 'openai'
        }
    
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
