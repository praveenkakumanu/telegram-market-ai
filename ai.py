import base64
import json
import mimetypes
import os
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
You are an AI financial market intelligence analyst analyzing Telegram messages.

Analyze stock/company news, technical analysis, options, futures, IPOs,
macroeconomics, market sentiment, trade ideas, screenshots and charts.

Never invent symbols, prices, targets, stop losses, entries or facts.
If an image is unclear, say so. Separate facts from opinions.
Telegram trading calls are not verified facts. Never guarantee profits.
Ignore greetings, casual chat, spam and content with no meaningful financial information.

Return ONLY valid JSON:
{
  "important": true,
  "category": "market_news",
  "importance": "high",
  "title": "Short title",
  "summary": "Short factual summary",
  "entities": [],
  "sentiment": "bullish",
  "market_impact": "Potential market impact",
  "trade_information": {
    "instrument": "",
    "direction": "",
    "entry": "",
    "target": "",
    "stop_loss": ""
  },
  "confidence": 0.0
}

Categories:
market_news, stock_analysis, technical_analysis, options, futures, ipo,
macro_economics, company_news, market_sentiment, trade_idea,
general_finance, irrelevant, other

Importance: low, medium, high, critical
Sentiment: bullish, bearish, neutral, unknown
"""

def image_to_data_url(path):
    mime, _ = mimetypes.guess_type(path)
    mime = mime or "image/jpeg"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{encoded}"

def analyze_message(text, image_path=None):
    content=[{"type":"input_text","text":text or ""}]
    if image_path and os.path.exists(image_path):
        content.append({
            "type":"input_image",
            "image_url":image_to_data_url(image_path),
            "detail":"high"
        })

    response=client.responses.create(
        model=OPENAI_MODEL,
        instructions=SYSTEM_PROMPT,
        input=[{"role":"user","content":content}],
    )
    result=response.output_text.strip()
    if result.startswith("```"):
        result=result.replace("```json","").replace("```","").strip()
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {
            "important":False,
            "category":"other",
            "importance":"low",
            "title":"AI parsing error",
            "summary":result[:1000],
            "entities":[],
            "sentiment":"unknown",
            "market_impact":"",
            "trade_information":{},
            "confidence":0.0,
        }
