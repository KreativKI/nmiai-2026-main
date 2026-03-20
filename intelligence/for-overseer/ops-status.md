**What:** Fixed NLP auto-submitter parser bug, launched full batch (--max 100). Bug: page shows fixed 20 results, new result replaces oldest, so count-based detection always saw 0 diff. Fix: detect by comparing first (newest) entry instead.
**Unblocks:** NLP submissions now running autonomously, ~30-75s per submission, scores parsing correctly.
**Next:** Monitor batch completion, commit parser fix, report final tally.
