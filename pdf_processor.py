# app.py

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

# ------------------ Page Config & Title ------------------
st.set_page_config(page_title="Ice Bag Proof Generator", layout="centered")
st.title("Ice Bag Multi Proof Generator")

# Yeh exact line tumne maangi thi
st.markdown(
    """
    <h3 style='text-align: center; color: #1E90FF;'>
    Enter text in the fields below (the output will appear in your PDF template within the red-marked brackets)
    </h3>
    """,
    unsafe_allow_html=True
)

st.markdown("---")

# ------------------ Text Input Section ------------------
st.subheader("Enter Your Text (Same text sab PDFs me lagega)")

col1, col2 = st.columns(2)

with col1:
    line1 = st.text_input("First Line (Bold & Large)", value="8 lb Ice Bag", help="Yeh line bold aur badi hogi")
    line2 = st.text_input("Second Line", value="Keep Frozen", help="Regular font")

with col2:
    line3 = st.text_input("Third Line", value="Made in USA", help="Regular font")
    # Optional 4th line
    line4 = st.text_input("Fourth Line (Optional)", value="", placeholder="Agar chahiye toh daalo")

# Collect non-empty lines
lines = [line1.strip(), line2.strip(), line3.strip(), line4.strip()]
lines = [ln for ln in lines if ln]

if not lines:
    st.error("Kam se kam pehli line toh bharo bhai!")
    st.stop()

# ------------------ Multiple PDF Upload ------------------
st.markdown("---")
st.subheader("Upload Your Template PDFs (Red border wale)")
st.info("Aap 1 se 10 PDFs tak upload kar sakte ho – sab me same text daal denge!")

uploaded_files = st.file_uploader(
    "Yahan drag & drop ya click karke PDFs daalo",
    type=["pdf"],
    accept_multiple_files=True,
    help="Sirf red border wale templates daalo"
)

if not uploaded_files:
    st.warning("Upload karo pehle, phir magic hoga!")
    st.stop()

if len(uploaded_files) > 10:
    st.error("Zyada se zyada 10 PDFs allowed hai!")
    st.stop()

st.success(f"Total {len(uploaded_files)} template(s) loaded! Processing shuru ho raha hai...")

# ------------------ Processing Starts ------------------
temp_dir = Path("/tmp/ice_bag_proofs")
temp_dir.mkdir(exist_ok=True)

final_pdf_paths = []
progress_bar = st.progress(0)
status_text = st.empty()

for idx, uploaded_file in enumerate(uploaded_files):
    status_text.text(f"Processing: {uploaded_file.name} ({idx+1}/{len(uploaded_files)})")

    # Save uploaded PDF
    temp_pdf_path = temp_dir / f"temp_{idx}_{uploaded_file.name}"
    with open(temp_pdf_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Open with PyMuPDF
    doc = fitz.open(str(temp_pdf_path))
    page = doc.load_page(0)
    page_rect = page.rect

    # High-res detection
    zoom = 3
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    arr = np.array(img)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]

    # Red detection
    red_mask = (r > 160) & (r > g + 70) & (r > b + 70)
    if red_mask.sum() < 100:
        red_mask = (r > 130) & (r > g + 40) & (r > b + 40)

    ys, xs = np.where(red_mask)

    if len(xs) == 0:
        # Fallback: center 4" × 2"
        box_w = 4 * 72
        box_h = 2 * 72
        x0 = (page_rect.width - box_w) / 2
        y0 = (page_rect.height - box_h) / 2
        x1 = x0 + box_w
        y1 = y0 + box_h
    else:
        min_x, max_x = xs.min(), xs.max()
        min_y, max_y = ys.min(), ys.max()
        img_w, img_h = img.size
        x0 = min_x * (page_rect.width / img_w)
        x1 = max_x * (page_rect.width / img_w)
        y0 = page_rect.height - (max_y * (page_rect.height / img_h))
        y1 = page_rect.height - (min_y * (page_rect.height / img_h))

    # Create overlay
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_rect.width, page_rect.height))

    # Debug red border (optional - helps verify placement)
    c.setStrokeColorRGB(1, 0, 0)
    c.setLineWidth(1)
    c.rect(x0, y0, x1-x0, y1-y0, stroke=1, fill=0)

    # Auto font size
    padding = 14
    box_w_px = x1 - x0
    box_h_px = y1 - y0
    font_size = 40
    while font_size > 8:
        line_height = font_size * 1.2
        total_h = len(lines) * line_height
        max_w = max(stringWidth(ln, "Helvetica-Bold" if i == 0 else "Helvetica", font_size) for i, ln in enumerate(lines))
        if total_h <= (box_h_px - 2*padding) and max_w <= (box_w_px - 2*padding):
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

    # Merge overlay
    overlay_pdf = PdfReader(packet)
    original_pdf = PdfReader(str(temp_pdf_path))
    writer = PdfWriter()

    page0 = original_pdf.pages[0]
    page0.merge_page(overlay_pdf.pages[0])
    writer.add_page(page0)
    for p in original_pdf.pages[1:]:
        writer.add_page(p)

    # Save final proof
    safe_name = "".join(c if c.isalnum() or c in " _-()" else "_" for c in uploaded_file.name)
    output_name = f"PROOF_{safe_name}"
    output_path = temp_dir / output_name
    with open(output_path, "wb") as f:
        writer.write(f)

    final_pdf_paths.append(output_path)

    progress_bar.progress((idx + 1) / len(uploaded_files))

# ------------------ Create ZIP & Download ------------------
zip_path = temp_dir / "All_Ice_Bag_Proofs_Ready.zip"
with zipfile.ZipFile(zip_path, "w") as zipf:
    for pdf_path in final_pdf_paths:
        zipf.write(pdf_path, arcname=pdf_path.name)

st.success("Sab proofs ban gaye!")
st.balloons()

with open(zip_path, "rb") as f:
    st.download_button(
        label="Download All Final Proofs (ZIP)",
        data=f.read(),
        file_name="Ice_Bag_Proofs_Ready.zip",
        mime="application/zip",
        use_container_width=True
    )

st.caption("Tip: Red border sirf preview ke liye hai – final PDF me nahi dikhega!")
