"""
RAG Baseline -- NM i AI 2026
Embedding-based retrieval + LLM generation for question-answering tasks.

Usage:
    1. Copy to agent-nlp/solutions/bot_v1.py
    2. Update DOCUMENTS_PATH, QUESTIONS_PATH, LLM_PROVIDER
    3. Run: python bot_v1.py

Supports: Anthropic Claude, OpenAI GPT, Google Gemini
"""

import json
import os
import numpy as np
from pathlib import Path

# === CONFIGURE THESE ===
DOCUMENTS_PATH = "data/documents.json"   # List of {"id": ..., "text": ...}
QUESTIONS_PATH = "data/questions.json"    # List of {"id": ..., "question": ...}
LLM_PROVIDER = "anthropic"               # anthropic / openai / google
LLM_MODEL = "claude-sonnet-4-20250514"       # Model name
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
TOP_K = 5                                # Number of docs to retrieve
OUTPUT_PATH = "predictions.json"
# ========================


def load_documents():
    """Load document corpus."""
    with open(DOCUMENTS_PATH) as f:
        docs = json.load(f)
    print(f"Loaded {len(docs)} documents")
    return docs


def load_questions():
    """Load questions."""
    with open(QUESTIONS_PATH) as f:
        questions = json.load(f)
    print(f"Loaded {len(questions)} questions")
    return questions


def build_index(docs):
    """Build embedding index for retrieval."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING_MODEL)
    texts = [d["text"] for d in docs]
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)

    # Normalize for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms

    print(f"Index built: {embeddings.shape}")
    return model, embeddings


def retrieve(query, embed_model, doc_embeddings, docs, top_k=TOP_K):
    """Retrieve top-k relevant documents."""
    query_emb = embed_model.encode([query])
    query_emb = query_emb / np.linalg.norm(query_emb)

    similarities = np.dot(doc_embeddings, query_emb.T).flatten()
    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = []
    for idx in top_indices:
        results.append({
            "doc": docs[idx],
            "score": float(similarities[idx]),
        })

    return results


def generate_answer(question, context_docs):
    """Generate answer using LLM with retrieved context."""
    context = "\n\n---\n\n".join([
        f"Document {i+1} (relevance: {d['score']:.2f}):\n{d['doc']['text']}"
        for i, d in enumerate(context_docs)
    ])

    prompt = f"""Based on the following documents, answer the question accurately and concisely.
If the answer is not in the documents, say "I cannot determine this from the provided documents."

Documents:
{context}

Question: {question}

Answer:"""

    if LLM_PROVIDER == "anthropic":
        import anthropic
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    elif LLM_PROVIDER == "openai":
        import openai
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        return response.choices[0].message.content

    elif LLM_PROVIDER == "google":
        import google.generativeai as genai
        model = genai.GenerativeModel(LLM_MODEL)
        response = model.generate_content(prompt)
        return response.text

    else:
        raise ValueError(f"Unknown provider: {LLM_PROVIDER}")


def main():
    docs = load_documents()
    questions = load_questions()

    embed_model, doc_embeddings = build_index(docs)

    predictions = []
    for i, q in enumerate(questions):
        print(f"Processing question {i+1}/{len(questions)}: {q['question'][:80]}...")

        context = retrieve(q["question"], embed_model, doc_embeddings, docs)
        answer = generate_answer(q["question"], context)

        predictions.append({
            "id": q["id"],
            "question": q["question"],
            "answer": answer,
            "sources": [d["doc"]["id"] for d in context],
        })

    # Save
    with open(OUTPUT_PATH, "w") as f:
        json.dump(predictions, f, indent=2)
    print(f"\nPredictions saved to {OUTPUT_PATH}")

    # Summary for MEMORY.md
    print(f"\n--- For MEMORY.md ---")
    print(f"Approach: RAG ({EMBEDDING_MODEL} + {LLM_PROVIDER}/{LLM_MODEL})")
    print(f"Top-K retrieval: {TOP_K}")
    print(f"Questions answered: {len(predictions)}")


if __name__ == "__main__":
    main()
