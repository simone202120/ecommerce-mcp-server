"""CLI: `python -m ecommerce_mcp.agent "question"` asks the agent via the MCP server over HTTP."""

import argparse
import asyncio
import json
import logging
import sys

from ecommerce_mcp.agent.runner import RunReport, answer_question
from ecommerce_mcp.config import get_settings


def render(report: RunReport) -> str:
    result = report.result
    lines = ["Tool calls:"]
    lines += [
        f"  - {call.name}({json.dumps(call.arguments, ensure_ascii=False)})"
        for call in result.tool_calls
    ] or ["  (none)"]
    lines += ["", "Answer:", result.answer, ""]
    lines.append(
        f"{result.latency_seconds:.1f}s | {result.input_tokens} in / {result.output_tokens} out "
        f"tokens | ~${report.cost_usd:.4f}"
    )
    if report.trace_url:
        lines.append(f"Trace: {report.trace_url}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the shop analyst agent a question.")
    parser.add_argument("question", help='e.g. "Which products are running low?"')
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    report = asyncio.run(answer_question(args.question, get_settings()))
    # The answer is the CLI's output, not a log record.
    sys.stdout.write(render(report))


if __name__ == "__main__":
    main()
