#!/usr/bin/env python3
"""Hybrid detector: offline + LLM for gray zone.

Pattern:
1. Offline detector scans all blocks (free, fast)
2. LLM judge reviews only gray zone findings (score 0.30-0.50)
3. If LLM confirms → boost score to 0.50+
4. If LLM rejects → lower score to 0.30-

This saves API calls while maintaining high recall.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import detectors  # noqa: F401
from detectors.factory import DetectorFactory
from models import TextBlock, Confidence
from repo_scanner import ScanConfig, scan_file, scan_repo


# Gray zone thresholds
GRAY_ZONE_LOW = 0.30
GRAY_ZONE_HIGH = 0.50

# LLM boost/reduce amounts
LLM_BOOST = 0.20  # Add to score if LLM confirms
LLM_REDUCE = 0.15  # Subtract from score if LLM rejects


def scan_with_hybrid(path: str, max_files: int = 100) -> dict:
    """Scan with offline detector, mark gray zone for LLM review."""
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
    
    # Process findings
    findings = []
    for span in spans:
        if span.details.get("source") != "style":
            continue
        
        # Find the block
        block = None
        for f in files:
            for b in f.blocks:
                if b.block_id == span.block_id:
                    block = b
                    break
            if block:
                break
        
        if not block:
            continue
        
        text = block.text[span.start:span.end]
        score = span.score
        
        # Determine if needs LLM review
        needs_llm = GRAY_ZONE_LOW <= score < GRAY_ZONE_HIGH
        
        findings.append({
            "text": text,
            "score": round(score, 3),
            "confidence": span.confidence.value,
            "file": getattr(block, "file_path", getattr(block, "page_url", "")),
            "line": getattr(block, "line_number", 0),
            "explanation": span.explanation,
            "details": span.details,
            "block_text": block.text,
            "needs_llm_review": needs_llm,
            "gray_zone": needs_llm,
        })
    
    return {
        "path": str(p),
        "files_read": len(files),
        "blocks_found": len(all_blocks),
        "findings": findings,
        "total": len(findings),
        "gray_zone_count": sum(1 for f in findings if f["gray_zone"]),
    }


def apply_llm_review(findings: list, llm_assessments: list) -> list:
    """Apply LLM assessments to gray zone findings.
    
    llm_assessments: list of {"index": int, "llm_score": float, "reason": str}
    """
    for assessment in llm_assessments:
        idx = assessment["index"]
        if 0 <= idx < len(findings):
            finding = findings[idx]
            if finding["gray_zone"]:
                llm_score = assessment["llm_score"]
                reason = assessment.get("reason", "")
                
                # Apply boost or reduce
                if llm_score >= 0.50:
                    # LLM confirms - boost
                    finding["score"] = min(1.0, finding["score"] + LLM_BOOST)
                    finding["llm_action"] = "boosted"
                elif llm_score < 0.30:
                    # LLM rejects - reduce
                    finding["score"] = max(0.0, finding["score"] - LLM_REDUCE)
                    finding["llm_action"] = "reduced"
                else:
                    # LLM uncertain - keep as is
                    finding["llm_action"] = "unchanged"
                
                finding["llm_score"] = llm_score
                finding["llm_reason"] = reason
                finding["needs_llm_review"] = False
    
    return findings


def main() -> int:
    import argparse
    
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="file or directory to scan")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-files", type=int, default=100)
    args = parser.parse_args()
    
    result = scan_with_hybrid(args.path, args.max_files)
    
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Scanned: {result['path']}")
        print(f"Files: {result['files_read']}, Blocks: {result['blocks_found']}")
        print(f"Total findings: {result['total']}")
        print(f"Gray zone (need LLM): {result['gray_zone_count']}")
        print()
        
        for i, f in enumerate(result["findings"]):
            marker = " [LLM]" if f["gray_zone"] else ""
            print(f"[{i}] Score: {f['score']:.3f} ({f['confidence']}){marker}")
            print(f"    Text: {f['text'][:80]}...")
            print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
