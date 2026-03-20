# NLP Push Blocked: CV Large Files in Git History

**Time:** 2026-03-20 ~22:00 CET
**Priority:** High (blocks all pushes on agent-nlp branch)

## Problem
`git push origin agent-nlp` is rejected by GitHub:
- `agent-cv/submissions/submission_dinov2_classify_v1.zip` = 143 MB (over 100 MB limit)
- `agent-cv/submissions/submission_ensemble_v1.zip` = 130 MB (over 100 MB limit)

These files were committed by the CV agent in earlier commits on this branch. They block ALL pushes, including NLP changes.

## Impact
- NLP commit `5b88a35` is saved locally but cannot be pushed
- Bot is deployed and working (rev 37, QC 8/8 PASS), so no competition impact
- But no remote backup of NLP code changes

## Fix needed (overseer or CV agent)
Remove the large files from git history using `git filter-repo` or `BFG Repo-Cleaner`, then force push. Or add them to `.gitlfs` tracking. This affects the shared repo, not just NLP.

## NLP status
Bot deployed, QC passing, ready to submit. This push issue does not block competition work.
