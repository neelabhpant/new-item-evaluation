import sys
from pathlib import Path
from typing import Any, Callable

from crewai import Crew, Process

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents import risk_market_analyst, financial_modeler, recommendation_synthesizer
from tasks import risk_market_task, financial_task, recommendation_task

AGENT_NAMES = [
    "Risk & Market Analyst",
    "Financial Modeler",
    "Recommendation Synthesizer",
]


def create_evaluation_crew(
    data_package: dict,
    task_callback: Callable[[Any], None] | None = None,
    step_callback: Callable[[Any], None] | None = None,
) -> Crew:
    agent1 = risk_market_analyst()
    agent2 = financial_modeler()
    agent3 = recommendation_synthesizer()

    task1 = risk_market_task(agent1, data_package)
    task2 = financial_task(agent2, data_package, context=[task1])
    task3 = recommendation_task(agent3, data_package, context=[task1, task2])

    return Crew(
        agents=[agent1, agent2, agent3],
        tasks=[task1, task2, task3],
        process=Process.sequential,
        verbose=True,
        task_callback=task_callback,
        step_callback=step_callback,
    )


if __name__ == "__main__":
    import time
    from dotenv import load_dotenv

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    load_dotenv(BASE_DIR / ".env")

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from pipeline.data_collector import collect_evaluation_data

    test_image = BASE_DIR / "data" / "images" / "catalog" / "0857777004195.jpg"

    print("=" * 60)
    print("PHASE 1: DETERMINISTIC DATA COLLECTION")
    print("=" * 60)

    t0 = time.time()
    data_package = collect_evaluation_data(
        image_path=str(test_image),
        name="NatureCrunch Eco-Grain Bites",
        description="Wholesome baked grain bites made with ancient grains, chia seeds, and real honey",
        price=5.49,
        category="Organic Snacks",
        claims=["Organic", "Non-GMO", "Plant-Based", "Gluten-Free"],
        brand="NatureCrunch",
    )
    t1 = time.time()

    print(f"\nData collection completed in {t1 - t0:.1f}s")
    print(f"Similar products: {len(data_package['similar_products'])}")
    print(f"Overlap: {data_package['overlap_classification']}")
    print(f"Sales records: {len(data_package['sales_data'])}")

    print("\n" + "=" * 60)
    print("PHASE 2: CREWAI REASONING (3 agents)")
    print("=" * 60)

    t2 = time.time()
    crew = create_evaluation_crew(data_package)
    result = crew.kickoff()
    t3 = time.time()

    print(f"\nReasoning completed in {t3 - t2:.1f}s")
    print(f"Total time: {t3 - t0:.1f}s")

    print("\n" + "=" * 60)
    print("TASK OUTPUTS")
    print("=" * 60)
    for i, task_output in enumerate(result.tasks_output, 1):
        print(f"\n{'=' * 40}")
        print(f"Agent {i}: {AGENT_NAMES[i - 1]}")
        print("=" * 40)
        print(task_output.raw[:2000])
        if len(task_output.raw) > 2000:
            print("... (truncated)")

    print("\n" + "=" * 60)
    print("FINAL RECOMMENDATION")
    print("=" * 60)
    print(result.raw)
