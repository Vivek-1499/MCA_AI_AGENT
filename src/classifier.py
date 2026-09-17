import os
import re
from typing import Literal
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

load_dotenv()

CategoryType = Literal["Act", "Rules", "Notification", "Circular", "Amendment", "Order", "Ordinance", "Other"]

class CategoryResult(BaseModel):
    category: CategoryType = Field(
        description="The document category out of: Act, Rules, Notification, Circular, Amendment, Order, Ordinance, Other."
    )
    reasoning: str = Field(default="", description="Short reason for choosing this category.")

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("GROQ_API_KEY is not set in environment variables.")

llm = ChatGroq(
    model_name="openai/gpt-oss-20b",
    temperature=0.1,
    groq_api_key=groq_api_key
)

prompt_template = ChatPromptTemplate.from_messages([
    ("system", """You are an expert legal document classifier for Indian Corporate Law and the Ministry of Corporate Affairs (MCA) under The Companies Act, 2013.

Classify the given document into EXACTLY ONE of these 8 taxonomy categories:
1. "Act": The main Companies Act text, sections, or schedules.
2. "Rules": Standard Companies Rules (e.g., Companies Incorporation Rules, Audit Rules).
3. "Notification": Official Gazette notifications (e.g., S.O., G.S.R., commencement notifications, section delegations).
4. "Circular": General Circulars, clarification circulars, or compliance timeline extensions issued by MCA.
5. "Amendment": Specific Amendment Acts, Amendment Rules, or Amendment Orders explicitly modifying existing sections or rules.
6. "Order": Companies (Removal of Difficulties) Orders, Special Court Orders, or administrative orders.
7. "Ordinance": Presidential Ordinances (promulgated under Article 123).
8. "Other": Press releases, guidelines, forms, reports, FAQs, or general policy documents.

Reply with JSON in format: {{"category": "<CATEGORY>"}} where <CATEGORY> is strictly one of Act, Rules, Notification, Circular, Amendment, Order, Ordinance, Other.
"""),
    ("user", """Document Title/Filename: {filename}
Source/Table Metadata Hint: {hint}

Document Text Excerpt:
{text_chunk}""")
])

def classify_document(filename: str, text: str, hint: str = "Unknown") -> str:
    """
    Chunks document text and calls Groq LLM to determine document category.
    Includes fast-path heuristics for speed and accuracy.
    """
    clean_text = text[:3500] if text else ""
    upper_title = filename.upper()
    upper_hint = hint.upper()
    
    if "AMENDMENT" in upper_title:
        return "Amendment"
    elif "CIRCULAR" in upper_title or "CIRCULAR" in upper_hint:
        return "Circular"
    elif "ORDER" in upper_title or "ORDER" in upper_hint:
        return "Order"
    elif "RULES" in upper_title and "AMENDMENT" not in upper_title:
        return "Rules"

    try:
        chain = prompt_template | llm
        res = chain.invoke({
            "filename": filename,
            "hint": hint,
            "text_chunk": clean_text if clean_text else "No text extracted"
        })
        content = res.content.strip()
        
        for cat in ["Amendment", "Rules", "Notification", "Circular", "Order", "Ordinance", "Act", "Other"]:
            if re.search(r'\b' + cat + r'\b', content, re.IGNORECASE):
                return cat
    except Exception as e:
        print(f"[Classifier] Notice: {e}", flush=True)

    if "ORDER" in upper_hint:
        return "Order"
    elif "AMENDMENT" in upper_hint or "AMENDMENT" in upper_title:
        return "Amendment"
    elif "CIRCULAR" in upper_hint:
        return "Circular"
    elif "NOTIFICATION" in upper_hint:
        return "Notification"
    return "Other"
