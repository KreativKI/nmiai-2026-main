# Agent Learnings — NM i AI 2026

## CV Agent (NorgesGruppen): The Late Bloomer

Think of this agent as a chef who spent 2 days prepping ingredients, then cooked a masterpiece in the last 3 hours.

**Score progression:** 0.6584 -> 0.8293 -> 0.8521 -> 0.8783

### What worked
- Two-stage pipeline (YOLO detects, DINOv2 classifies) was the breakthrough. Like having a sous chef spot ingredients on the shelf, then a sommelier identify exactly which brand.
- PCA whitening (+0.0228) and LinearSVC (+0.0262) each added measurable gains
- Validation before every submission prevented regressions
- Competitor analysis (PMM team audit) revealed winning techniques

### What failed
- First 2 days: mediocre YOLO-only approach (0.6584)
- DINOv2 was marked "REJECT" in plan.md but the rejection was based on a packaging bug, not actual accuracy
- SAHI, TTA, ensemble: all tested, all negligible or harmful
- Multiscale attempt crashed at 14:58 (2 minutes before deadline)
- Combined gallery (studio photos mixed with shelf crops): zero improvement

### Root cause of slow start
The agent defaulted to familiar tools (YOLO11m) instead of exploring newer approaches (DINOv2, GroundingDINO). The breakthrough came from studying what the competition leaders were doing, not from internal iteration.

### Kitchen metaphor
Like a chef who kept trying to improve the same soup recipe for 2 days, when what was needed was a completely different dish. The moment they looked at the winning restaurant's menu (PMM audit), everything clicked.

---

## ML Agent (Astar Island): The Promising Chef Who Burned the Final Dish

**Best round:** 85.3 (R19). **Worst round:** 61.8 (R23, final submission).

### What worked
- Brain V4 (LightGBM, 32 features) was solid architecture
- Dirichlet-Categorical Bayesian blending (+1.1 pts)
- Temperature scaling T=1.12 (+1.2 pts)
- Adaptive stacking with hindsight (concentrated queries on uncertain cells)
- Autonomous round submission (overnight_v4.py on GCP)

### What failed catastrophically
**R23 (final round): alpha search on wrong data.** The agent ran an optimization locally using simulated observations (perfect ground truth argmax). Real observations are noisy single Monte Carlo samples. Low alpha looked optimal with clean data, but production needed HIGH alpha (trust the model more when obs are noisy). Deployed alpha=6 instead of alpha=15+. Score dropped from ~80 to 61.8.

Also:
- Missed R1-R2 (setup issues, lost early weight)
- ml-churn VM sat idle the entire final session (never used available compute)
- Scoring formula wrong for 15+ rounds (missing 3x multiplier in exp(-3*KL))

### Root cause
The agent optimized on a simulation that didn't match production conditions. This is the most expensive mistake in the competition: doing the right thing on the wrong data.

### Kitchen metaphor
Like a chef who tested a recipe at home with perfect ingredients, then served it at the restaurant with whatever was in the fridge. The recipe worked beautifully in the test kitchen, but the real-world ingredients behaved differently. Should have tested with actual restaurant-stock ingredients.

---

## NLP Agent (Tripletex): The Reliable Line Cook Who Couldn't Crack the Special

**Official score:** 29.08. **Estimated after final session:** ~40-43. **10/16 tasks at 100%.**

### What worked
- Structured workflow extraction (LLM extracts JSON, Python executes API calls deterministically)
- Zero MALFORMED_FUNCTION_CALL errors (no function calling = no format bugs)
- 27 working executors across Tier 1+2+3
- Hardcoded reference data (VAT IDs, payment types) saved 6+ API calls per request
- QC verification script (17 tests) caught regressions

### What failed
- Travel Expense stuck at 0% the ENTIRE competition (never solved)
- Payment Reversal stuck at 25%
- userType regression: subagent said "ADMINISTRATOR", API only accepts NO_ACCESS/STANDARD/EXTENDED. Broke all admin employee creation.
- Rate limit confusion: docs said 300/day, platform enforced 180
- Burned 249/300 submissions in one session (should have been targeted batches)

### Root cause
Two issues: (A) trusted subagent domain knowledge instead of verifying against actual API, and (B) threw submissions at the wall instead of targeting specific failing tasks.

### Kitchen metaphor
Like a line cook who perfected 10 dishes on the menu but couldn't crack the soufle (Travel Expense). Instead of stepping back to understand why the soufle kept falling, they kept remaking it the same way. Meanwhile, they trusted a recipe book (subagent) that said "use 200C" when the oven actually maxed at 180C (wrong API values).

---

## Ops Agent (Butler): The Kitchen Porter Who Got Confused About Their Role

### What was built
- Dashboard infrastructure (React/TypeScript)
- CV labeling tool (web GUI for bounding box annotation)
- Communication protocol templates
- NLP auto-submitter (JC-approved)

### What went wrong
- Tried to run NLP submissions directly (violated ownership rules)
- Dashboard never fully completed (low priority vs track work)
- Labeling tool arrived too late for full impact

### Kitchen metaphor
Like a kitchen porter who was told to keep the kitchen clean and organized, but occasionally tried to plate dishes for the front of house. Good intentions, wrong role.

---

## Overseer (Main Branch): The Head Chef Who Was Reactive, Not Proactive

### What worked
- Intelligence folder system enabled async agent communication
- QC catches (Boris bugs, wrong agent names, blocked imports)
- Competition monitoring (round status, rule changes)
- Submission ZIP validation pipeline

### What failed
- plan.md was 18+ hours stale at session start
- Reactive fire-fighting instead of proactive planning
- Commits after 15:00 deadline (15:02-15:04)
- Didn't catch Boris workflow being run incorrectly until JC pointed it out
- Didn't verify NLP rate limits against platform early enough

### Kitchen metaphor
Like a head chef who spent the dinner service running between stations putting out fires, instead of standing at the pass calling orders and managing the flow. The kitchen needed a leader who was ahead of the action, not behind it.
