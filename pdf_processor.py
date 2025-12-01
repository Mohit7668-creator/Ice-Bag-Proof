# Creating a PDF proof by detecting the red box in the uploaded template, placing the provided lines
# with Arial (bold first line, regular lines after), and producing a merged vector PDF.
# Output: saved merged PDF and a PNG preview image.
# If Arial is not available on the system, the code will fallback to Helvetica and report that.

from pathlib import Path
from PIL import Image
import numpy as np
import io
import fitz  # PyMuPDF
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch

# ==================== FIXED PATHS (No more UnicodeEscape Error) ====================

# Option 1: Agar aap local Windows pe run kar rahe ho → raw string use karo
template_path = Path(r"C:\Users\Mohit(MohitM)Mishra\Desktop\Ice Bag Automation\Template.pdf")

# Option 2: Agar Streamlit Cloud ya Linux/Mac pe deploy karoge → relative ya user-uploaded file use karna better hai
# Lekin abhi ke liye local testing ke liye upar wala sahi hai

# Output folder banao Desktop pe
base_dir = Path.home() / "Desktop" / "Pdf"
base_dir.mkdir(parents=True, exist_ok=True)

output_overlay = base_dir / "overlay_text.pdf"
final_output = base_dir / "8lbPLWK_with_text.pdf"
preview_png = base_dir / "preview_page.png"

# The text to insert (user provided)
lines = ["Test Line 1", "Test Line 2", "Test Line 3"]

# ==================== Check if Template Exists ====================
if not template_path.exists():
    raise FileNotFoundError(f"Template PDF not found! Looking for: {template_path}")

# ==================== Open PDF and detect red box ====================
doc = fitz.open(str(template_path))
page = doc.load_page(0)

# High resolution pixmap for accurate detection
zoom = 2
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat, alpha=False)
img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

# Save preview
img.save(preview_png)

# Convert to numpy array
arr = np.array(img)
r, g, b = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)

# Detect red box
red_mask = (r > 150) & (r > g + 60) & (r > b + 60)
if red_mask.sum() < 50:
    red_mask = (r > 120) & (r > g + 40) & (r > b + 40)

ys, xs = np.where(red_mask)

if len(xs) == 0:
    # Fallback: center 4"x2" box
    detected = False
    page_rect = page.rect
    box_w_pts = 4 * 72
    box_h_pts = 2 * 72
    x0 = (page_rect.width - box_w_pts) / 2
    y0 = (page_rect.height - box_h_pts) / 2
    x1 = x0 + box_w_pts
    y1 = y0 + box_h_pts
else:
    detected = True
    min_x, max_x = xs.min(), xs.max()
    min_y, max_y = ys.min(), ys.max()

    img_w, img_h = img.size
    page_w_pts = page.rect.width
    page_h_pts = page.rect.height

    x0 = min_x * (page_w_pts / img_w)
    x1 = max_x * (page_w_pts / img_w)
    y0 = page_h_pts - (max_y * (page_h_pts / img_h))   # PDF y=0 at bottom
    y1 = page_h_pts - (min_y * (page_h_pts / img_h))

# ==================== Font Registration (Arial fallback to Helvetica) ====================
def try_register(font_name, possible_paths):
    for p in possible_paths:
        path = Path(p)
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(path)))
                return True
            except:
                continue
    return False

# Common Arial locations (add Windows paths too for local testing)
arial_paths = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\Arial.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
]

arial_bold_paths = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\Arialbd.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]

have_arial = try_register("Arial", arial_paths)
have_arial_bold = try_register("Arial-Bold", arial_bold_paths)

font_regular = "Arial" if have_arial else "Helvetica"
font_bold = "Arial-Bold" if have_arial_bold else "Helvetica-Bold"

# ==================== Create Text Overlay PDF ====================
packet = io.BytesIO()
c = canvas.Canvas(packet, pagesize=(page.rect.width, page.rect.height))

# Optional: debug red border
c.setStrokeColorRGB(1, 0, 0)
c.setLineWidth(1)
c.rect(x0, y0, x1 - x0, y1 - y0, stroke=1, fill=0)

# Dynamic font sizing
padding = 10
box_w = x1 - x0
box_h = y1 - y0

from reportlab.pdfbase.pdfmetrics import stringWidth

font_size = 28
while font_size > 8:
    line_height = font_size * 1.2
    total_h = len(lines) * line_height
    max_w = max(stringWidth(line, font_regular if i > 0 else font_bold, font_size) for i, line in enumerate(lines))
    if total_h <= (box_h - 2 * padding) and max_w <= (box_w - 2 * padding):
        break
    font_size -= 1

# Draw text
text_x = x0 + padding
y_cursor = y1 - padding - font_size  # first line baseline

c.setFont(font_bold, font_size)
c.drawString(text_x, y_cursor, lines[0])

c.setFont(font_regular, font_size)
for line in lines[1:]:
    y_cursor -= line_height
    c.drawString(text_x, y_cursor, line)

c.save()
packet.seek(0)

# ==================== Merge Overlay with Original PDF ====================
overlay_pdf = PdfReader(packet)
original_pdf = PdfReader(str(template_path))
writer = PdfWriter()

page0 = original_pdf.pages[0]
page0.merge_page(overlay_pdf.pages[0])  # This works in modern PyPDF2
writer.add_page(page0)

for p in original_pdf.pages[1:]:
    writer.add_page(p)

with open(final_output, "wb") as f:
    writer.write(f)

# ==================== Final Result ====================
result = {
    "detected_red_box": detected,
    "final_pdf": str(final_output),
    "preview_png": str(preview_png),
    "font_used": font_regular,
    "font_bold_used": font_bold,
    "notes": ""
}

if not have_arial or not have_arial_bold:
    result["notes"] = "Arial not found on this system → using Helvetica fallback. Text is still crisp and vector!"

print("PDF Proof generated successfully!")
result

