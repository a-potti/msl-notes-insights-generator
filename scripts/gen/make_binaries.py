#!/usr/bin/env python3
"""Generate the binary raw inputs (PDF abstract + poster image) for Chapter 3."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)


def make_pdf():
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=8.5, leading=11)
    doc = SimpleDocTemplate(str(RAW / "ecco2026_abstract_P0412.pdf"), pagesize=A4,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    story = [
        Paragraph("ECCO Congress 2026 &mdash; Vienna &mdash; Poster P0412", styles["Heading3"]),
        Paragraph("Mucosal TL1A expression predicts response to anti-TL1A therapy in "
                  "ulcerative colitis: a biomarker analysis of the AURORA programme",
                  styles["Heading2"]),
        Paragraph("<i>K. Vandermeer<super>1</super>, R. Achterberg<super>1</super>, "
                  "T. Saito<super>2</super>, M. Nkemdirim<super>3</super>, on behalf of "
                  "the AURORA investigators</i>", small),
        Paragraph("<super>1</super>St. Aldric's Hospital &nbsp; "
                  "<super>2</super>Harbourview Institute of Digestive Health &nbsp; "
                  "<super>3</super>Northgate University Hospital", small),
        Spacer(1, 10),
        Paragraph("<b>Background</b>", styles["Heading4"]),
        Paragraph("Anti-TL1A therapy is effective in a subset of patients with "
                  "moderate-to-severe ulcerative colitis, but no predictive biomarker "
                  "is established. We assessed whether baseline mucosal TL1A expression "
                  "is associated with clinical remission.", small),
        Paragraph("<b>Methods</b>", styles["Heading4"]),
        Paragraph("Baseline biopsies from 402 AURORA-1 participants randomised to "
                  "zoltarimab were analysed by RNA in situ hybridisation. Patients were "
                  "grouped into tertiles of mucosal TL1A expression. The primary "
                  "endpoint was clinical remission at week 12.", small),
        Paragraph("<b>Results</b>", styles["Heading4"]),
        Paragraph("Clinical remission at week 12 was achieved by 54.9% of patients in "
                  "the highest expression tertile versus 21.4% in the lowest "
                  "(difference 33.5%, 95% CI 22.1&ndash;44.9). The association persisted "
                  "after adjustment for prior advanced therapy exposure and baseline "
                  "Mayo score.", small),
        Spacer(1, 8),
    ]
    tbl = Table([
        ["TL1A tertile", "n", "Clinical remission wk12", "Endoscopic improvement wk12"],
        ["Low", "134", "21.4%", "29.9%"],
        ["Intermediate", "134", "37.3%", "44.0%"],
        ["High", "134", "54.9%", "61.2%"],
    ], colWidths=[3.6 * cm, 1.6 * cm, 5.0 * cm, 5.4 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [
        tbl,
        Spacer(1, 10),
        Paragraph("<b>Conclusions</b>", styles["Heading4"]),
        Paragraph("Baseline mucosal TL1A expression is strongly associated with response "
                  "to zoltarimab. Prospective validation in a biomarker-stratified trial "
                  "is warranted. A companion diagnostic is in development.", small),
        Spacer(1, 12),
        Paragraph("<i>Fictional abstract created for training purposes. Not real "
                  "clinical data. Disclosures: all authors are fictional.</i>", small),
    ]
    doc.build(story)


def make_poster_image():
    W, H = 1000, 720
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    def font(sz, bold=False):
        for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",):
            try:
                return ImageFont.truetype(p, sz)
            except OSError:
                pass
        return ImageFont.load_default()

    d.rectangle([0, 0, W, 90], fill="#1f3d5c")
    d.text((28, 22), "DDW 2026  |  Poster Sa1187", font=font(20, True), fill="white")
    d.text((28, 54), "Kestrel Bio / REALIZE-UC registry", font=font(15), fill="#c8d8e8")

    d.text((28, 118), "Time from prescription to first infusion:", font=font(21, True),
           fill="#1f3d5c")
    d.text((28, 148), "real-world initiation delay in ulcerative colitis",
           font=font(21, True), fill="#1f3d5c")

    d.text((28, 200), "Median 31 days (IQR 18-52). Infusion capacity was the stated",
           font=font(15), fill="black")
    d.text((28, 224), "cause in 58% of delays exceeding 30 days (n=340).",
           font=font(15), fill="black")

    # simple bar chart
    bars = [("0-14 d", 74), ("15-30 d", 96), ("31-60 d", 118), (">60 d", 52)]
    x0, y0, bw, gap, scale = 90, 620, 110, 60, 2.7
    d.line([x0 - 20, y0, W - 60, y0], fill="black", width=2)
    d.line([x0 - 20, y0, x0 - 20, 300], fill="black", width=2)
    for i, (lab, v) in enumerate(bars):
        x = x0 + i * (bw + gap)
        h = v * scale
        d.rectangle([x, y0 - h, x + bw, y0], fill="#3d7ab8")
        d.text((x + 30, y0 - h - 26), str(v), font=font(15, True), fill="black")
        d.text((x + 20, y0 + 10), lab, font=font(14), fill="black")
    d.text((x0 - 80, 290), "patients", font=font(13), fill="black")
    d.text((28, 678), "Fictional poster created for training purposes. Not real data.",
           font=font(12), fill="#666666")
    img.save(RAW / "ddw2026_poster_Sa1187.png")


if __name__ == "__main__":
    make_pdf()
    make_poster_image()
    print("wrote", RAW / "ecco2026_abstract_P0412.pdf")
    print("wrote", RAW / "ddw2026_poster_Sa1187.png")
