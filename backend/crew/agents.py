import os

from crewai import Agent, LLM

MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")


def _llm() -> LLM:
    return LLM(model=f"openai/{MODEL_NAME}")


def risk_market_analyst() -> Agent:
    return Agent(
        role="Category performance and market strategy analyst",
        goal="Assess cannibalization risk and evaluate market context for the proposed product",
        backstory=(
            "You are an experienced category analyst and market strategist with deep expertise "
            "in grocery retail. You evaluate new items against existing shelf performance, "
            "understand velocity trends, competitive dynamics, and consumer behavior shifts. "
            "You assess both the risk to existing products and the market opportunity for new entries."
        ),
        tools=[],
        llm=_llm(),
        verbose=True,
        allow_delegation=False,
    )


def financial_modeler() -> Agent:
    return Agent(
        role="Retail financial analyst",
        goal="Project Year 1 financial performance and net category impact",
        backstory=(
            "You are a retail financial analyst who builds P&L projections for new product "
            "introductions. You model revenue, margin, and cannibalization impact using comparable "
            "product performance data. You always present best, expected, and worst case scenarios."
        ),
        tools=[],
        llm=_llm(),
        verbose=True,
        allow_delegation=False,
    )


def recommendation_synthesizer() -> Agent:
    return Agent(
        role="Senior category advisor and recommendation synthesizer",
        goal=(
            "Synthesize risk analysis and financial projections into a compelling "
            "recommendation report that explains the predetermined verdict"
        ),
        backstory=(
            "You are a senior category management executive with 20 years of experience "
            "in assortment decisions for major grocery retailers. You receive a predetermined "
            "verdict from the evaluation system's decision matrix and your job is to synthesize "
            "the risk and financial analysis into clear, evidence-based reasoning that explains "
            "why this verdict is correct. You are direct, specific, and always support the "
            "system's verdict with concrete data from the analysis."
        ),
        tools=[],
        llm=_llm(),
        verbose=True,
        allow_delegation=False,
    )
