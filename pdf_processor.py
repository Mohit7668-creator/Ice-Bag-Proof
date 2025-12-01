# app.py  (Streamlit ke liye perfect)

import streamlit as st
from pathlib import Path
import fitz  # PyMuPDF
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
import io
import zipfile
import os
from PIL import Image
import numpy as np

st.set_page_config(page_title="Ice Bag Proof Generator", layout="wide")
st.title("Ice Bag Multi Proof Generator")
st.markdown("**Ek hi text → 10 alag-alag template PDFs me daal do!**")

# ------------------ Text Input (Ek hi baar) ------------------
st.subheader("Text daalo (sab PDFs me yahi lagega)")
col1, col2 = st.columns(2)
with col1:
    line1 = st.text_input("First Line (Bold)", "8 lb Ice Bag", key="l1")
    line2 = st.text_input("Second Line", "Keep Frozen", key="l2")
with col2:
    line3 = st.text_input("Third Line", "Made in USA", key="l3")

lines = [line1.strip(), line2.strip(), line3.strip()]
lines = [ln for ln in lines if ln]  # remove empty

if not lines:
    st.error("Kam se kam first line toh daalo!")
    st.stop()

# ------------------ Multiple PDF Upload ------------------
st.subheader("Apne Template PDFs upload karo (red box wale)")
uploaded_files = st.file_uploader(
    "Yahan 1 se 10 PDFs daal do",
    type="pdf",
    accept_multiple_files=True
)

if not uploaded_files:
    st.info("Upload karo bhai, phir magic dikhega!")
    st.stop()

if len(uploaded_files) > 10:
    st.error("Zyada se zyada 10 PDFs hi allowed hai!")
    st.stop()

st.success(f"{len(uploaded_files)} PDFs loaded! Processing shuru...")

# ------------------ Temporary Folder ------------------
temp_dir = Path("/tmp/proofs")
temp_dir.mkdir(exist_ok=True)

final_pdfs = []
preview_images = []

progress_bar = st.progress(0)

for idx, uploaded_file in enumerate(uploaded_files):
    progress_bar.progress((idx + 1) / len(uploaded_files))

    # Save uploaded PDF temporarily
    temp_pdf_path = temp_dir / f"template_{idx}.pdf"
    with open(temp_pdf_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Open with PyMuPDF
    doc = fitz.open(str(temp_pdf_path))
    page = doc.load_page(0)
    page_rect = page.rect

    # High-res pixmap for red detection
    zoom = 3
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    arr = np.array(img)

    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    red_mask = (r > 160) & (r > g + 70) & (r > b + 70)
    if red_mask.sum() < 100:
        red_mask = (r > 130) & (r > g + 40) & (r > b + 40)

    ys, xs = np.where(red_mask)

    if len(xs) == 0:
        # Fallback: center 4x2 inch
        box_w = 4 * 72
        box_h = 2 * 72
        x0 = (page_rect.width - box_w) / 2
        y0 = (page_rect.height - box_h) / 2
        x1 = x0 + box_w
        y1 = y0 + box_h
        detected = False
    else:
        min_x, max_x = xs.min(), xs.max()
        min_y, max_y = ys.min(), ys.max()
        img_w, img_h = img.size

        x0 = min_x * (page_rect.width / img_w)
        x1 = max_x * (page_rect.width / img_w)
        y0 = page_rect.height - (max_y * (page_rect.height / img_h))
        y1 = page_rect.height - (min_y * (page_rect.height / img_h))
        detected = True

    # Create overlay
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_rect.width, page_rect.height))

    # Optional red border for debug
    c.setStrokeColorRGB(1, 0, 0)
    c.setLineWidth(1)
    c.rect(x0, y0, x1-x0, y1-y0, stroke=1, fill=0)

    # Auto font size
    padding = 12
    box_w = x1 - x0
    box_h = y1 - y0
    font_size = 36
    while font_size > 8:
        line_height = font_size * 1.2
        total_h = len(lines) * line_height
        max_w = max(stringWidth(ln, "Helvetica-Bold" if i == 0 else "Helvetica", font_size) for i, ln in enumerate(lines))
        if total_h <= (box_h - 2*padding) and max_w <= (box_w - 2*padding):
            break
        font_size -= 1

    # Draw text
    text_x = x0 + padding
    y_cursor = y1 - padding - font_size

    c.setFont("Helvetica-Bold", font_size)
    c.drawString(text_x, y_cursor, lines[0])

    c.setFont("Helvetica", font_size)
    for line in lines[1:]:
        y_cursor -= line_height
        c.drawString(text_x, y_cursor, line)

    c.save()
    packet.seek(0)

    # Merge
    overlay = PdfReader(packet)
    original = PdfReader(str(temp_pdf_path))
    writer = PdfWriter()

    page0 = original.pages[0]
    page0.merge_page(overlay.pages[0])
    writer.add_page(page0)
    for p in original.pages[1:]:
        writer.add_page(p)

    # Save final PDF
    output_name = f"Proof_{uploaded_file.name.replace('.pdf', '')}_with_text.pdf"
    output_path = temp_dir / output_name
    with open(output_path, "wb") as f:
        writer.write(f)

    final_pdfs.append((uploaded_file.name, output_path))

# ------------------ Create ZIP & Download ------------------
zip_path = temp_dir / "All_Ice_Bag_Proofs.zip"
with zipfile.ZipFile(zip_path, "w") as zipf:
    for original_name, pdf_path in final_pdfs:
        zipf.write(pdf_path, arcname=pdf_path.name)

with open(zip_path, "rb") as f:
    st.download_button(
        label="Download All Final Proofs (ZIP)",
        data=f.read(),
        file_name="Ice_Bag_Proofs_Ready.zip",
        mime="application/zip"
    )

st.success("Sab proofs ban gaye! Upar download button se ZIP le lo!")
st.balloons()

