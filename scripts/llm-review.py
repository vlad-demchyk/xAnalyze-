#!/usr/bin/env python3
"""CLI + LLM judge pattern: scan with offline detector, then review with agent.

This script demonstrates the sequential pattern:
1. CLI scans with offline detector (free, fast)
2. Agent reviews flagged passages (LLM, contextual)
3. Combined report with both assessments

Usage:
    python scripts/llm-review.py <path> [--json] [--threshold 0.33]

The script outputs findings that need LLM review, ready for an agent to analyze.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import detectors  # noqa: F401 - registers detectors
from detectors.factory import DetectorFactory
from models import TextBlock, Confidence
from repo_scanner import ScanConfig, scan_file, scan_repo


def scan_path(path: str, threshold: float = 0.33, max_files: int = 100) -> dict:
    """Scan a path with offline detector and return findings."""
    p = Path(path)
    
    # Create offline detector
    detector = DetectorFactory.create("offline")
    
    # Scan
    if p.is_file():
        files = [scan_file(str(p))]
    else:
        config = ScanConfig(max_files=max_files)
        files = scan_repo(str(p), config)
    
    # Analyze
    all_blocks = []
    for f in files:
        all_blocks.extend(f.blocks)
    
    spans = detector.analyze_blocks(all_blocks)
    
    # Filter style findings above threshold
    style_findings = []
    for span in spans:
        if span.details.get("source") == "style" and span.score >= threshold:
            # Find the block
            block = None
            for f in files:
                for b in f.blocks:
                    if b.block_id == span.block_id:
                        block = b
                        break
                if block:
                    break
            
            if block:
                style_findings.append({
                    "text": block.text[span.start:span.end],
                    "score": round(span.score, 3),
                    "confidence": span.confidence.value,
                    "file": getattr(block, "file_path", getattr(block, "page_url", "")),
                    "line": getattr(block, "line_number", 0),
                    "explanation": span.explanation,
                    "details": span.details,
                    "block_text": block.text,
                    "needs_llm_review": True,
                })
    
    # Character findings (always exact, no LLM review needed)
    char_findings = []
    for span in spans:
        if span.details.get("source") == "characters":
            block = None
            for f in files:
                for b in f.blocks:
                    if b.block_id == span.block_id:
                        block = b
                        break
                if block:
                    break
            
            if block:
                char_findings.append({
                    "text": block.text[span.start:span.end],
                    "score": round(span.score, 3),
                    "confidence": span.confidence.value,
                    "file": getattr(block, "file_path", getattr(block, "page_url", "")),
                    "line": getattr(block, "line_number", 0),
                    "explanation": span.explanation,
                    "replacement": span.replacement,
                    "needs_llm_review": False,
                })
    
    return {
        "path": str(p),
        "files_read": len(files),
        "blocks_found": len(all_blocks),
        "style_findings": style_findings,
        "char_findings": char_findings,
        "total_style": len(style_findings),
        "total_char": len(char_findings),
        "threshold": threshold,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="file or directory to scan")
    parser.add_argument("--json", action="store_true", help="output as JSON")
    parser.add_argument("--threshold", type=float, default=0.33,
                        help="minimum score for style findings (default: 0.33)")
    parser.add_argument("--max-files", type=int, default=100,
                        help="maximum files to scan (default: 100)")
    args = parser.parse_args()
    
    result = scan_path(args.path, args.threshold, args.max_files)
    
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Scanned: {result['path']}")
        print(f"Files: {result['files_read']}, Blocks: {result['blocks_found']}")
        print(f"Style findings: {result['total_style']}")
        print(f"Character findings: {result['total_char']}")
        print()
        
        if result["style_findings"]:
            print("=== STYLE FINDINGS (need LLM review) ===")
            for i, f in enumerate(result["style_findings"], 1):
                print(f"\n[{i}] Score: {f['score']} ({f['confidence']})")
                print(f"    File: {f['file']}:{f['line']}")
                print(f"    Text: {f['text'][:100]}...")
                print(f"    Explanation: {f['explanation']}")
        
        if result["char_findings"]:
            print("\n=== CHARACTER FINDINGS (exact, no review needed) ===")
            for i, f in enumerate(result["char_findings"], 1):
                print(f"\n[{i}] {f['text']!r} -> {f.get('replacement', '?')!r}")
                print(f"    File: {f['file']}:{f['line']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
