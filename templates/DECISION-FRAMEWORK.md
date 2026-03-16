# Decision Framework: Build vs Fork vs Adapt

Use this flowchart BEFORE writing any solution code.

## Decision Tree

```
START
 |
 v
Is there a public solution scoring >70% of estimated ceiling?
 |
 YES --> FORK
         Copy code, adapt I/O format, iterate on top.
         Time: 1-3 hours.
         Log in MEMORY.md: "FORK from {url}, match score {X}%"
 |
 NO --> Is there a pre-trained model for this exact task type?
         |
         YES --> ADAPT
                 Use model as backbone, fine-tune or prompt-engineer.
                 Time: 2-4 hours.
                 Log in MEMORY.md: "ADAPT {model}, task match {X}%"
         |
         NO --> Is this a well-known problem type with standard approaches?
                 |
                 YES --> BUILD with templates
                         Use shared/templates/ starters (sklearn, PyTorch, transformers).
                         Time: 3-6 hours.
                         Log in MEMORY.md: "BUILD from template {name}"
                 |
                 NO --> NOVEL problem
                        Build from scratch, simplest approach first.
                        Flag to Matilda: "novel problem, need JC input."
                        Time: 6-12 hours. May need deprioritization.
                        Log in MEMORY.md: "NOVEL, building from scratch"
```

## Search Order (for FORK/ADAPT candidates)

1. GitHub: "{problem description} solution", "{metric} baseline"
2. Kaggle: similar competition kernels
3. HuggingFace: pre-trained models for this domain
4. Papers With Code: SOTA on this task type
5. NM i AI 2025 solutions (Race Car, Tumor Segmentation, Emergency Healthcare RAG)

## Evaluation Criteria

For each candidate found, score:
- **Match %**: How close is this to our exact problem? (>70% = FORK territory)
- **Adaptation effort**: Hours to adapt I/O format and scoring
- **License**: Can we use it? (MIT/Apache = yes, no license = risky)
- **Quality**: Does it have tests? Documentation? Recent activity?

## Golden Rule

When in doubt, FORK first. You can throw away forked code.
You cannot recover time spent building from scratch.

## Document the Decision

Every decision goes in MEMORY.md:
```
### Decision: {FORK/ADAPT/BUILD/NOVEL}
**Source:** {url or "from scratch"}
**Match %:** {X}
**Adaptation effort:** {Y hours}
**Reasoning:** {why this choice}
```
