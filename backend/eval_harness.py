"""
RAG Evaluation Harness — generates test sets, runs both pipelines,
scores with LLM-as-judge, and computes retrieval + generation metrics.
"""
import os
import re
import json
import time
import logging
from datetime import datetime

import anthropic
from dotenv import load_dotenv

from database import (
    SessionLocal, Document, DocumentSection,
    EvalTestCase, EvalRun, EvalResult,
)
from study_agent import chat_with_agent, chat_with_agent_rag
from rag_pipeline import retrieve_chunks

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-20250514"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("eval_harness")


# ── Test Set Generation ──────────────────────────────────────────────

def generate_test_set(document_id: str, questions_per_section: int = 3) -> list:
    """Auto-generate Q&A test cases from document sections."""
    db = SessionLocal()
    sections = (
        db.query(DocumentSection)
        .filter(DocumentSection.document_id == document_id)
        .order_by(DocumentSection.section_order)
        .all()
    )

    # Clear old test cases for this document
    db.query(EvalTestCase).filter(EvalTestCase.document_id == document_id).delete()
    db.commit()

    test_cases = []

    for section in sections:
        if not section.content or len(section.content.strip()) < 100:
            continue

        prompt = f"""Generate exactly {questions_per_section} question-answer pairs from this text.
Each question should be answerable ONLY from the provided text.
Include a short source excerpt (1-2 sentences) from the text that directly answers the question.

Text:
\"\"\"{section.content[:4000]}\"\"\"

Return a JSON array only, no other text:
[{{"question": "...", "answer": "...", "source_excerpt": "exact sentence(s) from text"}}]"""

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            raw = re.sub(r"^```(?:json)?\s*\n?", "", raw, flags=re.MULTILINE)
            raw = re.sub(r"\n?```\s*$", "", raw, flags=re.MULTILINE)
            pairs = json.loads(raw.strip())

            for pair in pairs:
                tc = EvalTestCase(
                    document_id=document_id,
                    section_id=section.id,
                    question=pair["question"],
                    ground_truth=pair["answer"],
                    source_chunk_text=pair.get("source_excerpt", ""),
                )
                db.add(tc)
                db.flush()
                test_cases.append({
                    "id": tc.id,
                    "section_id": section.id,
                    "section_title": section.title,
                    "question": pair["question"],
                    "ground_truth": pair["answer"],
                    "source_excerpt": pair.get("source_excerpt", ""),
                })

            log.info(f"Generated {len(pairs)} test cases for section '{section.title}'")

        except Exception as e:
            log.warning(f"Failed to generate test cases for section '{section.title}': {e}")

    db.commit()
    db.close()
    log.info(f"Total test cases generated: {len(test_cases)}")
    return test_cases


# ── LLM-as-Judge Scoring ─────────────────────────────────────────────

def judge_answer(question: str, ground_truth: str, candidate: str,
                 source_chunks: list = None) -> dict:
    """Score a candidate answer on accuracy, groundedness, relevance."""
    source_text = "\n---\n".join(source_chunks) if source_chunks else "N/A (full context mode)"

    prompt = f"""You are an evaluation judge. Score the candidate answer strictly.

Question: {question}

Ground Truth Answer: {ground_truth}

Candidate Answer: {candidate}

Source Chunks Provided to Candidate:
{source_text}

Score on three dimensions (0.0 to 1.0, use one decimal):
- accuracy: How factually correct is the candidate compared to ground truth? (1.0 = perfectly correct, 0.0 = completely wrong)
- groundedness: Is the candidate answer supported by the source chunks? (1.0 = fully grounded, 0.0 = hallucinated)
- relevance: Are the source chunks relevant to answering the question? (1.0 = perfectly relevant, 0.0 = irrelevant)

Return JSON only, no explanation:
{{"accuracy": 0.0, "groundedness": 0.0, "relevance": 0.0}}"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\n?```\s*$", "", raw, flags=re.MULTILINE)
        return json.loads(raw.strip())
    except Exception as e:
        log.warning(f"Judge scoring failed: {e}")
        return {"accuracy": 0.0, "groundedness": 0.0, "relevance": 0.0}


# ── Retrieval Quality Metrics ─────────────────────────────────────────

def compute_retrieval_metrics(document_id: str, test_cases: list) -> dict:
    """Compute Precision@k, Hit Rate, and MRR for the retrieval step."""
    hits = 0
    reciprocal_ranks = []
    precision_at_k_list = []

    for tc in test_cases:
        chunks = retrieve_chunks(document_id, tc["question"], top_k=5)
        chunk_section_ids = [c["section_id"] for c in chunks]
        target_section = tc["section_id"]

        # Hit: did we retrieve at least one chunk from the correct section?
        hit = target_section in chunk_section_ids
        if hit:
            hits += 1

        # MRR: reciprocal rank of the first relevant chunk
        for rank, sid in enumerate(chunk_section_ids, 1):
            if sid == target_section:
                reciprocal_ranks.append(1.0 / rank)
                break
        else:
            reciprocal_ranks.append(0.0)

        # Precision@k: fraction of retrieved chunks from the correct section
        relevant_count = sum(1 for sid in chunk_section_ids if sid == target_section)
        precision_at_k_list.append(relevant_count / len(chunk_section_ids) if chunk_section_ids else 0)

    n = len(test_cases) or 1
    return {
        "hit_rate": round(hits / n, 3),
        "mrr": round(sum(reciprocal_ranks) / n, 3),
        "avg_precision_at_k": round(sum(precision_at_k_list) / n, 3),
        "total_queries": n,
    }


# ── Full Evaluation Run ──────────────────────────────────────────────

def run_evaluation(document_id: str) -> dict:
    """Run both pipelines on all test cases, score, and aggregate."""
    db = SessionLocal()

    # Load test cases
    test_cases_db = (
        db.query(EvalTestCase)
        .filter(EvalTestCase.document_id == document_id)
        .all()
    )
    if not test_cases_db:
        db.close()
        return {"error": "No test cases found. Run generate_test_set first."}

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        db.close()
        return {"error": "Document not found."}

    # Create eval run
    run = EvalRun(document_id=document_id, status="running")
    db.add(run)
    db.commit()
    run_id = run.id

    log.info(f"Starting eval run {run_id} with {len(test_cases_db)} test cases")

    results = {"rag": [], "full_context": []}
    test_case_list = []

    for tc in test_cases_db:
        test_case_list.append({
            "id": tc.id,
            "section_id": tc.section_id,
            "question": tc.question,
            "ground_truth": tc.ground_truth,
        })

        log.info(f"  Evaluating: {tc.question[:60]}...")

        # ── Pipeline A: Full Context ──
        start = time.time()
        try:
            response_fc = chat_with_agent(
                user_message=tc.question,
                conversation_history=[],
                document_title=doc.filename,
                summary_text=doc.summary or "",
            )
        except Exception as e:
            response_fc = f"[Error: {e}]"
        latency_fc = int((time.time() - start) * 1000)

        # ── Pipeline B: RAG ──
        start = time.time()
        try:
            result_rag = chat_with_agent_rag(
                user_message=tc.question,
                conversation_history=[],
                document_id=document_id,
                document_title=doc.filename,
            )
            response_rag = result_rag["response"]
            rag_sources = result_rag["sources"]
            rag_usage = result_rag.get("usage", {})
        except Exception as e:
            response_rag = f"[Error: {e}]"
            rag_sources = []
            rag_usage = {}
        latency_rag = int((time.time() - start) * 1000)

        # ── Judge both ──
        scores_fc = judge_answer(
            tc.question, tc.ground_truth, response_fc
        )
        scores_rag = judge_answer(
            tc.question, tc.ground_truth, response_rag,
            source_chunks=[s["text"] for s in rag_sources],
        )

        # Save full_context result
        fc_result = EvalResult(
            run_id=run_id,
            test_case_id=tc.id,
            pipeline="full_context",
            answer=response_fc,
            accuracy_score=scores_fc.get("accuracy", 0),
            relevance_score=scores_fc.get("relevance", 0),
            groundedness_score=scores_fc.get("groundedness", 0),
            latency_ms=latency_fc,
            token_count=0,
            retrieved_chunks=None,
        )
        db.add(fc_result)

        # Save RAG result
        rag_result = EvalResult(
            run_id=run_id,
            test_case_id=tc.id,
            pipeline="rag",
            answer=response_rag,
            accuracy_score=scores_rag.get("accuracy", 0),
            relevance_score=scores_rag.get("relevance", 0),
            groundedness_score=scores_rag.get("groundedness", 0),
            latency_ms=latency_rag,
            token_count=rag_usage.get("input_tokens", 0),
            retrieved_chunks=rag_sources,
        )
        db.add(rag_result)

        results["full_context"].append({
            "question": tc.question,
            "answer": response_fc,
            "latency_ms": latency_fc,
            **scores_fc,
        })
        results["rag"].append({
            "question": tc.question,
            "answer": response_rag,
            "sources": rag_sources,
            "latency_ms": latency_rag,
            "input_tokens": rag_usage.get("input_tokens", 0),
            **scores_rag,
        })

        db.commit()

    # ── Retrieval metrics ──
    retrieval_metrics = compute_retrieval_metrics(document_id, test_case_list)

    # ── Aggregate ──
    summary = {}
    for pipeline_name in ["rag", "full_context"]:
        r = results[pipeline_name]
        n = len(r) or 1
        summary[pipeline_name] = {
            "avg_accuracy": round(sum(x.get("accuracy", 0) for x in r) / n, 3),
            "avg_groundedness": round(sum(x.get("groundedness", 0) for x in r) / n, 3),
            "avg_relevance": round(sum(x.get("relevance", 0) for x in r) / n, 3),
            "avg_latency_ms": round(sum(x["latency_ms"] for x in r) / n),
            "count": len(r),
        }

    # Win/loss/tie counts
    wins = {"rag": 0, "full_context": 0, "tie": 0}
    for i in range(len(results["rag"])):
        rag_acc = results["rag"][i].get("accuracy", 0)
        fc_acc = results["full_context"][i].get("accuracy", 0)
        if rag_acc > fc_acc:
            wins["rag"] += 1
        elif fc_acc > rag_acc:
            wins["full_context"] += 1
        else:
            wins["tie"] += 1

    summary["wins"] = wins
    summary["retrieval_metrics"] = retrieval_metrics

    # Update run
    run = db.query(EvalRun).filter(EvalRun.id == run_id).first()
    run.status = "completed"
    run.completed_at = datetime.utcnow()
    run.summary = summary
    db.commit()
    db.close()

    log.info(f"Eval run {run_id} completed!")
    log.info(f"  RAG:  acc={summary['rag']['avg_accuracy']}, grnd={summary['rag']['avg_groundedness']}, rel={summary['rag']['avg_relevance']}")
    log.info(f"  Full: acc={summary['full_context']['avg_accuracy']}, grnd={summary['full_context']['avg_groundedness']}, rel={summary['full_context']['avg_relevance']}")
    log.info(f"  Wins: RAG={wins['rag']}, Full={wins['full_context']}, Tie={wins['tie']}")
    log.info(f"  Retrieval: hit_rate={retrieval_metrics['hit_rate']}, MRR={retrieval_metrics['mrr']}, P@k={retrieval_metrics['avg_precision_at_k']}")

    return {
        "run_id": run_id,
        "test_case_count": len(test_case_list),
        "results": results,
        "summary": summary,
    }


# ── Get past eval results ────────────────────────────────────────────

def get_eval_runs(document_id: str) -> list:
    """Get all eval runs for a document."""
    db = SessionLocal()
    runs = (
        db.query(EvalRun)
        .filter(EvalRun.document_id == document_id)
        .order_by(EvalRun.started_at.desc())
        .all()
    )
    result = []
    for r in runs:
        result.append({
            "id": r.id,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "summary": r.summary,
        })
    db.close()
    return result


def get_eval_run_detail(run_id: int) -> dict:
    """Get detailed results for a specific eval run."""
    db = SessionLocal()
    run = db.query(EvalRun).filter(EvalRun.id == run_id).first()
    if not run:
        db.close()
        return {"error": "Run not found"}

    results = (
        db.query(EvalResult)
        .filter(EvalResult.run_id == run_id)
        .all()
    )

    detail = {"rag": [], "full_context": []}
    for r in results:
        tc = db.query(EvalTestCase).filter(EvalTestCase.id == r.test_case_id).first()
        entry = {
            "question": tc.question if tc else "?",
            "ground_truth": tc.ground_truth if tc else "?",
            "answer": r.answer,
            "accuracy": r.accuracy_score,
            "groundedness": r.groundedness_score,
            "relevance": r.relevance_score,
            "latency_ms": r.latency_ms,
            "token_count": r.token_count,
        }
        if r.pipeline == "rag":
            entry["retrieved_chunks"] = r.retrieved_chunks
        detail[r.pipeline].append(entry)

    db.close()
    return {
        "run_id": run_id,
        "status": run.status,
        "summary": run.summary,
        "results": detail,
    }


# ── CLI Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage:")
        print("  python eval_harness.py generate <document_id>   — generate test cases")
        print("  python eval_harness.py run <document_id>        — run full evaluation")
        print("  python eval_harness.py list <document_id>       — list past runs")
        print("  python eval_harness.py detail <run_id>          — show run details")
        sys.exit(1)

    command = sys.argv[1]
    arg = sys.argv[2]

    if command == "generate":
        cases = generate_test_set(arg)
        print(f"\nGenerated {len(cases)} test cases:")
        for c in cases:
            print(f"  [{c['section_title']}] {c['question']}")

    elif command == "run":
        # Generate test cases first if none exist
        db = SessionLocal()
        count = db.query(EvalTestCase).filter(EvalTestCase.document_id == arg).count()
        db.close()
        if count == 0:
            print("No test cases found. Generating...")
            generate_test_set(arg)

        print(f"\nRunning evaluation on document {arg}...")
        result = run_evaluation(arg)

        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            s = result["summary"]
            print(f"\n{'='*60}")
            print(f"EVALUATION RESULTS — {result['test_case_count']} test cases")
            print(f"{'='*60}")
            print(f"\n{'Metric':<25} {'Full Context':>15} {'RAG':>15}")
            print(f"{'-'*55}")
            print(f"{'Avg Accuracy':<25} {s['full_context']['avg_accuracy']:>15} {s['rag']['avg_accuracy']:>15}")
            print(f"{'Avg Groundedness':<25} {s['full_context']['avg_groundedness']:>15} {s['rag']['avg_groundedness']:>15}")
            print(f"{'Avg Relevance':<25} {s['full_context']['avg_relevance']:>15} {s['rag']['avg_relevance']:>15}")
            print(f"{'Avg Latency (ms)':<25} {s['full_context']['avg_latency_ms']:>15} {s['rag']['avg_latency_ms']:>15}")
            print(f"\nWins: RAG={s['wins']['rag']}, Full={s['wins']['full_context']}, Tie={s['wins']['tie']}")
            rm = s["retrieval_metrics"]
            print(f"\nRetrieval Metrics:")
            print(f"  Hit Rate:     {rm['hit_rate']}")
            print(f"  MRR:          {rm['mrr']}")
            print(f"  Precision@5:  {rm['avg_precision_at_k']}")

    elif command == "list":
        runs = get_eval_runs(arg)
        if not runs:
            print("No eval runs found.")
        for r in runs:
            print(f"  Run #{r['id']} — {r['status']} — {r['started_at']}")
            if r["summary"]:
                s = r["summary"]
                print(f"    RAG: acc={s['rag']['avg_accuracy']}, Full: acc={s['full_context']['avg_accuracy']}")

    elif command == "detail":
        result = get_eval_run_detail(int(arg))
        print(json.dumps(result, indent=2, default=str))

    else:
        print(f"Unknown command: {command}")
