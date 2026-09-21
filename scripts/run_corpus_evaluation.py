"""Run the real-file corpus evaluation and print a JSON report."""

import json
import sys

from app.evaluation.corpus_suite import run_corpus_evaluation


if __name__ == "__main__":
    # Windows PowerShell may use GBK by default, which cannot display all
    # Japanese characters contained in the evaluation report.
    # Windows PowerShell 默认可能使用 GBK，无法显示评测报告中的部分日文字符。
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(run_corpus_evaluation(), ensure_ascii=False, indent=2))
