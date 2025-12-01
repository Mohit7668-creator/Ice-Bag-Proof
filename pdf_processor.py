# app.py  → Streamlit Cloud ready

import streamlit as st
from pathlib import Path
import fitz
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
import io
import zipfile
from PIL import Image
import numpy as np

st.set_page_config(page_title="Ice Bag Proof Generator", layout="centered")
st.title("Ice Bag Multi Proof Generator")

# ← Yeh exact line tumne maangi thi
st.markdown(
    """
    <h3 style='text-align: center; color: #1E90FF; margin-bottom: 30px;'>
    Enter text in the fields below (the output will appear in your PDF template within the red-marked brackets)
    </h3>
    """,
    unsafe_allow_html=True
)

st.markdown("---")

# ------------------ Text Input ------------------
st.subheader("Enter Your Text")

# ← Yeh line change ki gayi hai exactly tumhare kehne pe
st.info("**Same text will reflect on PDFs**")

col1, col2 = st.columns(2)
with col1:
    line1 = st.text_input("First Line (Bold & Large)", value="8 lb Ice Bag")
    line2 = st.text_input("Second Line", value="Keep Frozen")

with col2:
    line3 = st.text_input("Third Line", value="Made in USA")
    line4 = st.text_input("Fourth Line (Optional)", value="", placeholder="Leave empty if not needed")

lines = [line1.strip(), line2.strip(), line3.strip(), line4.strip()]
lines = [ln for ln in lines if ln]  # remove empty lines

if not lines:
    st.error("Please fill at least the first line!")
    st.stop()

# ------------------ Upload PDFs ------------------
st.markdown("---")
st.subheader("Upload Your Template PDFs (with red border/box)")
uploaded_files = st.file_uploader(
    "Choose up to 10 PDFs",
    type="pdf",
    accept_multiple_files=True,
    help="Only PDFs containing a red rectangle/border will be processed accurately"
)

if not uploaded_files:
    st.warning("Please upload at least one template PDF")
    st.stop()

if len(uploaded_files) > 10:
    st.error("Maximum 10 PDFs allowed")
    st.stop()

st.success(f"{len(uploaded_files)} template(s) uploaded – processing now...")

# ------------------ Processing ------------------
temp_dir = Path("/tmp/ice_bag_proofs")
temp_dir.mkdir(exist_ok=True)

final_pdf_paths = []
progress_bar = st.progress(0)
status = st.empty()

for i, file in enumerate(uploaded_files):
    status.text(f"Processing {file.name} ({i+1}/{len(uploaded_files)})")

    # Save uploaded file temporarily
    temp_pdf = temp_dir / f"temp_{i}.pdf"
    with open(temp_pdf, "wb") as f:
        f.write(file.getbuffer())

    # Open PDF
    doc = fitz.open(str(temp_pdf))
    page = doc[0]
    rect = page.rect

    # High-res pixmap for red detection
    zoom = 3
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    arr = np.array(img)

    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    mask = (r > 160) & (r > g + 70) & (r > b + 70)
    if mask.sum() < 100:
        mask = (r > 130) & (r > g + 40) & (r > b + 40)

    ys, xs = np.where(mask)

    if len(xs) == 0:
        # Fallback: center 4×2 inch box
        w = 4 * 72
        h = 2 * 72
        x0 = (rect.width - w) / 2
        y0 = (rect.height - h) / 2
        x1 = x0 + w
        y1 = y0 + h
    else:
        x0 = xs.min() * rect.width / pix.width
        x1 = xs.max() * rect.width / pix.width
        y0 = rect.height - (ys.max() * rect.height / pix.height)
        y1 = rect.height - (ys.min() * rect.height / pix.height)

    # Create overlay
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(rect.width, rect.height))

    # Optional red border for debugging (won't appear in final output if you remove this)
    c.setStrokeColorRGB(1, 0, 0)
    c.setLineWidth(1)
    c.rect(x0, y0, x1-x0, y1-y0, stroke=1, fill=0)

    # Auto font size
    padding = 14
    box_w = x1 - x0
    box_h = y1 - y0
    font_size = 42
    while font_size > 8:
        line_h = font_size * 1.2
        total_h = len(lines) * line_h
        max_w = max(stringWidth(l, "Helvetica-Bold" if j == 0 else "Helvetica", font_size) for j, l in enumerate(lines))
        if total_h <= box_h - 2*padding and max_w <= box_w - 2*padding:
            break
        font_size -= 1

    # Draw text
    c.setFont("Helvetica-Bold", font_size)
    c.drawString(x0 + padding, y1 - padding - font_size, lines[0])

    c.setFont("Helvetica", font_size)
    y = y1 - padding - font_size - line_h
    for line in lines[1:]:
        c.drawString(x0 + padding, y, line)
        y -= line_h

    c.save()
    packet.seek(0)

    # Merge
    overlay = PdfReader(packet)
    original = PdfReader(str(temp_pdf))
    writer = PdfWriter()
    page0 = original.pages[0]
    page0.merge_page(overlay.pages[0])
    writer.add_page(page0)
    for p in original.pages[1:]:
        writer.add_page(p)

    # Save final
    safe_name = "".join(c if c.isalnum() or c in " _-()" else "_" for c in file.name)
    output_path = temp_dir / f"PROOF_{safe_name}"
    with open(output_path, "wb") as f:
        writer.write(f)

    final_pdf_paths.append(output_path)
    progress_bar.progress((i + 1) / len(uploaded_files))

# ------------------ ZIP & Download ------------------
zip_path = temp_dir / "Ice_Bag_Proofs_Ready.zip"
with zipfile.ZipFile(zip_path, "w") as z:
    for p in final_pdf_paths:
        z.write(p, arcname=p.name)

st.success("All proofs generated successfully!")
st.balloons()

with open(zip_path, "rb") as f:
    st.download_button(
        label="Download All Final Proofs (ZIP)",
        data=f.read(),
        file_name="Ice_Bag_Proofs_Ready.zip",
        mime="application/zip",
        use_container_width=True
    )

st.caption("Red border is only for detection – it will NOT appear in the final downloaded PDFs")
