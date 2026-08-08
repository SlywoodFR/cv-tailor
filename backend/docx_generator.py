"""Génère un CV au format DOCX (facilement modifiable / exportable en PDF
depuis Word) à partir du même contexte que le template HTML."""
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


BLUE = RGBColor(0x25, 0x63, 0xEB)
GREY = RGBColor(0x4B, 0x55, 0x63)


def _fmt(d, fmt):
    return d.strftime(fmt) if d else ""


def build_docx(context: dict) -> Document:
    profile = context["profile"]
    doc = Document()

    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    title = doc.add_paragraph()
    run = title.add_run(profile.full_name)
    run.bold = True
    run.font.size = Pt(22)
    run.font.color.rgb = BLUE

    contact_bits = [b for b in [profile.email, profile.phone, profile.location,
                                 profile.linkedin, profile.github, profile.website] if b]
    if contact_bits:
        p = doc.add_paragraph(" | ".join(contact_bits))
        p.runs[0].font.color.rgb = GREY
        p.runs[0].font.size = Pt(9.5)

    if context.get("summary"):
        p = doc.add_paragraph(context["summary"])
        p.runs[0].italic = True

    def add_heading(text):
        h = doc.add_heading(text, level=2)
        for run in h.runs:
            run.font.color.rgb = BLUE
            run.font.size = Pt(12)

    if context.get("experiences"):
        add_heading("Expériences")
        for e in context["experiences"]:
            p = doc.add_paragraph()
            r = p.add_run(f"{e['role']} — {e['company']}")
            r.bold = True
            dates = f"{_fmt(e['start_date'], '%m/%Y')} – {_fmt(e['end_date'], '%m/%Y') or 'en cours'}"
            p.add_run(f"    ({dates})").italic = True
            if e.get("location"):
                loc = doc.add_paragraph(e["location"])
                loc.runs[0].font.color.rgb = GREY
                loc.runs[0].font.size = Pt(9.5)
            for b in e.get("bullets", []):
                doc.add_paragraph(b, style="List Bullet")

    if context.get("skills_by_category"):
        add_heading("Compétences")
        for cat, items in context["skills_by_category"].items():
            p = doc.add_paragraph()
            p.add_run(f"{cat} : ").bold = True
            names = ", ".join(
                (s["name"] + (f" ({s['level']})" if s.get("level") else "")) for s in items
            )
            p.add_run(names)

    if context.get("projects"):
        add_heading("Projets")
        for pr in context["projects"]:
            p = doc.add_paragraph()
            p.add_run(pr["name"]).bold = True
            if pr.get("link"):
                p.add_run(f"  ({pr['link']})").italic = True
            if pr.get("description"):
                doc.add_paragraph(pr["description"])

    if context.get("educations"):
        add_heading("Formation")
        for ed in context["educations"]:
            p = doc.add_paragraph()
            label = ed.degree + (f" — {ed.field}" if ed.field else "") + f", {ed.school}"
            r = p.add_run(label)
            r.bold = True
            years = f"{_fmt(ed.start_date, '%Y')} – {_fmt(ed.end_date, '%Y') or 'en cours'}"
            p.add_run(f"    ({years})").italic = True
            if ed.description:
                doc.add_paragraph(ed.description)

    if context.get("languages"):
        add_heading("Langues")
        doc.add_paragraph(" | ".join(f"{l.name} — {l.level}" for l in context["languages"]))

    return doc
