import io

from fpdf import FPDF
from pydantic import BaseModel, Field

from harness.core.context import RunContext
from harness.core.models import ExecutionMode, ToolSpec
from harness.registry import register_tool


class RenderPdfInput(BaseModel):
    html: str = Field(description="HTML content to render as PDF")
    title: str | None = None


class RenderPdfOutput(BaseModel):
    pdf_bytes: bytes
    page_count: int


def _html_to_text(html: str) -> str:
    import re

    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _render_pdf_bytes(html: str, title: str | None) -> tuple[bytes, int]:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)

    if title:
        pdf.set_font("Helvetica", style="B", size=16)
        pdf.multi_cell(0, 10, title)
        pdf.ln(4)
        pdf.set_font("Helvetica", size=12)

    body = _html_to_text(html)
    pdf.multi_cell(0, 8, body or "(empty document)")
    page_count = max(1, pdf.page_no())
    return pdf.output(), page_count


@register_tool
class RenderPdfFromHtmlTool:
    spec = ToolSpec(
        name="render_pdf_from_html",
        description="Renders HTML content into a PDF byte stream.",
        capability_tags=["document-generation", "pdf"],
        input_schema=RenderPdfInput,
        output_schema=RenderPdfOutput,
        side_effects=True,
        requires_approval=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: RenderPdfInput, *, context: RunContext) -> RenderPdfOutput:
        pdf_bytes, page_count = _render_pdf_bytes(args.html, args.title)
        return RenderPdfOutput(pdf_bytes=pdf_bytes, page_count=page_count)
