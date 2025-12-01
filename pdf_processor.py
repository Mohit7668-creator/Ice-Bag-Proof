# pdf_processor.py  (Streamlit Cloud ke liye perfect)

from pathlib import Path
from PIL import Image
import numpy as np
import io
import fitz
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import streamlit as st

# ------------------ STREAMLIT UI ------------------
st.title("Ice Bag Proof Generator")
st.write("Upload your Template PDF (jo red box wala hai)")

uploaded_file = st.file_uploader("Template.pdf upload karo", type="pdf")

if uploaded_file is None:
    st.warning("Pehle Template PDF upload karo!")
    st.stop()

# ------------------ Save uploaded file temporarily ------------------
template_path = Path("/tmp/Template.pdf")  # Streamlit Cloud me /tmp allowed hai
with open(template_path, "wb") as f:
    f.write(uploaded_file.getbuffer())

st.success("Template PDF successfully loaded!")

# Output folder (tmp me hi bana denge kyuki Cloud pe Desktop nahi hota)
base_dir = Path("/tmp")
output_overlay = base_dir / "overlay_text.pdf"
final_output = base_dir / "final_proof_with_text.pdf"
preview_png = base_dir / "preview_page.png"

# User se text lines input lo
st.write("### Text daalo jo red box ke andar aana chahiye")
line1 = st.text_input("First Line (Bold)", "8 lb Ice Bag")
line2 = st.text_input("Second Line", "Keep Frozen")
line3 = st.text_input("Third Line", "Made in USA")
lines = [line1, line2, line3]
lines = [ln.strip() for ln in lines if ln.strip()]  # empty lines remove

if not lines:
    st.error("Kam se kam ek line toh daalo!")
    st.stop()

# ------------------ Baaki saara code same (sirf path change) ------------------
doc = fitz.open(str(template_path))
page = doc.load_page(0)

zoom = 2
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat, alpha=False)
img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
img.save(preview_png)

arr = np.array(img)
r, g, b = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)

red_mask = (r > 150) & (r > g + 60) & (r > b + 60)
if red_mask.sum() < 50:
    red_mask = (r > 120) & (r > g + 40) & (r > b + 40)

ys, xs = np.where(red_mask)

if len(xs) == 0:
    detected = False
    page_rect = page.rect
    box_w_pts = 4 * 72
    box_h_pts = 2 * 72
    x0 = (page_rect.width - box_w_pts) / 2
    y0 = (page_rect.height - box_h_pts) / 2
    x1 = x0 + box_w_pts
    y1 = y0 + box_h_pts
    st.warning("Red box nahi mila → center me 4×2 inch area use kar raha hun")
else:
    detected = True
    min_x, max_x = xs.min(), xs.max()
    min_y, max_y = ys.min(), ys.max()
    img_w, img_h = img.size
    x0 = min_x * (page.rect.width / img_w)
    x1 = max_x * (page.rect.width / img_w)
    y0 = page.rect.height - (max_y * (page.rect.height / img_h))
    y1 = page.rect.height - (min_y * (page.rect.height / img_h))

# Font (Helvetica fallback - Cloud pe Arial nahi hota)
font_regular = "Helvetica"
font_bold = "Helvetica-Bold"

# Create overlay
packet = io.BytesIO()
c = canvas.Canvas(packet, pagesize=(page.rect.width, page.rect.height))

# Debug border (optional)
c.setStrokeColorRGB(1, 0, 0)
c.rect(x0, y0, x1-x0, y1-y0, stroke=1, fill=0)

# Auto font size
padding = 12
box_w = x1 - x0
box_h = y1 - y0
font_size = 32
from reportlab.pdfbase.pdfmetrics import stringWidth

while font_size > 8:
    line_height = font_size * 1.2
    total_h = len(lines) * line_height
    max_w = max(stringWidth(line, font_bold if i==0 else font_regular, font_size) for i, line in enumerate(lines))
    if total_h <= (box_h - 2*padding) and max_w <= (box_w - 2*padding):
        break
    font_size -= 1

# Draw text
text_x = x0 + padding
y_cursor = y1 - padding - font_size

c.setFont(font_bold, font_size)
c.drawString(text_x, y_cursor, lines[0])

c.setFont(font_regular, font_size)
for line in lines[1:]:
    y_cursor -= line_height
    c.drawString(text_x, y_cursor, line)

c.save()
packet.seek(0)

# Merge
overlay_pdf = PdfReader(packet)
original_pdf = PdfReader(str(template_path))
writer = PdfWriter()

page0 = original_pdf.pages[0]
page0.merge_page(overlay_pdf.pages[0])
writer.add_page(page0)
for p in original_pdf.pages[1:]:
    writer.add_page(p)

with open(final_output, "wb") as f:
    writer.write(f)

# ------------------ Show Results ------------------
st.success("Proof ban gaya!")
col1, col2 = st.columns(2)
with col1:
    st.image(str(preview_png), caption="Red box detection preview")
with col2:
    with open(final_output, "rb") as f:
        st.download_button(
            label="Download Final Proof PDF",
            data=f.read(),
            file_name="Ice_Bag_Proof_with_Text.pdf",
            mime="application/pdf"
        )

