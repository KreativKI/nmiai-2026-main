# Slack Announcement — Blocked Import Bans
**Time:** 2026-03-20 ~00:40 CET
**Source:** Official NM i AI Slack
**Affects:** CV track (NorgesGruppen)

## Announcement
More than 30 accounts have been banned for submitting `import sys` to the Computer Vision task. The organizers view blocked imports as a security threat and enforce instant account bans, not just submission failures.

## Blocked import list (from docs)
os, sys, subprocess, socket, multiprocessing, threading, signal, shutil, ctypes, builtins, importlib, marshal, shelve, code, codeop, pty, requests, urllib

## Implications
- This is a BAN, not a failed submission. You lose your account.
- Many teams likely used `import sys` for `sys.argv` in run.py. Use `argparse` or hardcode paths instead.
- Libraries that internally import blocked modules (e.g., some parts of PyTorch, ultralytics) might also trigger this. Test in the Docker sandbox FIRST.
- Before every CV submission: grep ALL .py files for blocked imports, including transitive ones.
