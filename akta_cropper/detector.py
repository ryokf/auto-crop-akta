import re
import cv2
import numpy as np
import pymupdf
from typing import List, Tuple, Optional, Dict, Any
from rapidocr_onnxruntime import RapidOCR

# Lazy singleton OCR engine
_OCR_ENGINE: Optional[RapidOCR] = None

def get_ocr_engine() -> RapidOCR:
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def render_pdf_page(page: pymupdf.Page, dpi: int = 150) -> np.ndarray:
    """Render satu halaman PDF menjadi citra OpenCV BGR."""
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    elif pix.n == 1:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


def get_box_aspect_ratio(box: List[List[float]]) -> float:
    """Hitung rasio lebar / tinggi dari polygon bounding box."""
    pts = np.array(box)
    w = np.linalg.norm(pts[1] - pts[0])
    h = np.linalg.norm(pts[3] - pts[0])
    return (w / h) if h > 0 else 1.0


def detect_and_orient_upright(img: np.ndarray, engine: RapidOCR) -> Tuple[np.ndarray, int]:
    """
    Deteksi orientasi tegak (upright) dokumen akta.
    Akta tanah biasanya dicetak vertikal (portrait). Jika hasil scan miring/landscape,
    fungsi ini otomatis memutar ke 90_CCW, 90_CW, 180, atau tetap 0 derajat.
    """
    h, w = img.shape[:2]
    
    # Tentukan kandidat rotasi berdasarkan aspek rasio citra
    if w > h:
        # Dokumen berbentuk landscape (biasanya akta folio yang di-scan miring)
        candidates = [
            (cv2.ROTATE_90_COUNTERCLOCKWISE, "90_CCW", 270),
            (cv2.ROTATE_90_CLOCKWISE, "90_CW", 90),
            (None, "0", 0),
            (cv2.ROTATE_180, "180", 180)
        ]
    else:
        # Dokumen portrait
        candidates = [
            (None, "0", 0),
            (cv2.ROTATE_180, "180", 180),
            (cv2.ROTATE_90_COUNTERCLOCKWISE, "90_CCW", 270),
            (cv2.ROTATE_90_CLOCKWISE, "90_CW", 90)
        ]

    best_img = img
    best_angle = 0
    best_score = -1.0

    # Untuk kecepatan, kita bisa menguji kandidat menggunakan resize
    for rot_code, name, angle_deg in candidates:
        candidate_img = img if rot_code is None else cv2.rotate(img, rot_code)
        
        # Cek OCR pada kandidat
        # Resize untuk deteksi orientasi cepat
        scale = 800.0 / max(candidate_img.shape[:2])
        small = cv2.resize(candidate_img, (0, 0), fx=scale, fy=scale)
        
        results, _ = engine(small)
        if not results:
            continue
        
        # Evaluasi:
        # 1. Kotak teks harus horizontal (rasio lebar terhadap tinggi > 2)
        ratios = [get_box_aspect_ratio(item[0]) for item in results]
        horizontal_count = sum(1 for r in ratios if r > 2.0)
        
        # 2. Kata kunci khas akta dan posisi header/footer
        text_lines = [item[1].lower() for item in results]
        full_text = " ".join(text_lines)
        
        keywords = ["akta", "jual", "beli", "pihak", "pertama", "kedua", "halaman", "tuan", "nyonya", "notaris", "demak"]
        kw_matches = sum(1 for kw in keywords if kw in full_text)
        
        # 3. Posisi teks footer (misal "halaman ... dari ...") harus berada di bagian bawah (y tinggi)
        footer_penalty = 0
        for i, item in enumerate(results):
            txt = item[1].lower()
            box_y = item[0][0][1] # y koordinat atas
            if "halaman" in txt and "dari" in txt:
                # Jika kata halaman muncul di 30% teratas dokumen, kemungkinan terbalik (180 deg)
                if box_y < small.shape[0] * 0.35:
                    footer_penalty += 50
        
        # Skor akhir
        score = (horizontal_count * 2.0) + (kw_matches * 10.0) - footer_penalty
        
        if score > best_score:
            best_score = score
            best_img = candidate_img
            best_angle = angle_deg

    return best_img, best_angle


def is_buyer_conclusion_line(text: str) -> bool:
    """Memeriksa apakah baris ini adalah penutup pihak pembeli."""
    t = text.lower()
    return any(p in t for p in [
        "pihak kedua/pembeli",
        "pihak kedua / pembeli",
        "pihak kedua (pembeli)",
        "\"pihak kedua/pembeli\"",
        "pembeli\".-",
        "pembeli\""
    ]) or (("pihak kedua" in t or "pembeli" in t) and ("disebut" in t or "sebagai" in t or "akta ini" in t))


def is_seller_conclusion_line(text: str) -> bool:
    """Memeriksa apakah baris ini adalah penutup pihak penjual."""
    t = text.lower()
    return any(p in t for p in [
        "pihak pertama/penjual",
        "pihak pertama / penjual",
        "pihak pertama (penjual)",
        "\"pihak pertama/penjual\"",
        "penjual\".-",
        "penjual\""
    ])


def is_buyer_start_line(text: str) -> bool:
    """Memeriksa apakah baris ini merupakan awal identitas pembeli."""
    t = text.strip()
    # Format angka romawi atau arab: "II.-Tuan", "II.", "2.-", "2."
    if re.match(r'^(?:II|2)[\.\-\s]+', t, re.IGNORECASE):
        return True
    # Atau kata pengantar identitas
    if re.match(r'^(?:Tuan|Nyonya|Nona|Tn\.|Ny\.|Perseroan Terbatas|PT\.?)\s+', t):
        return True
    return False


def find_buyer_bounding_box(
    ocr_results: List[Any],
    img_shape: Tuple[int, int, int],
    dpi: int = 150
) -> Optional[Tuple[int, int, int, int, List[str]]]:
    """
    Cari rentang baris pembeli dan hitung bounding box (x1, y1, x2, y2).
    Mengembalikan (x1, y1, x2, y2, raw_lines) atau None jika tidak ditemukan.
    """
    if not ocr_results:
        return None

    end_idx = None
    # 1. Cari baris penutup pembeli (dari bawah ke atas atau atas ke bawah)
    for i, res in enumerate(ocr_results):
        box, text, score = res
        if is_buyer_conclusion_line(text):
            end_idx = i
            break

    # Fallback: cari baris yang mengandung 'pembeli'
    if end_idx is None:
        for i, res in enumerate(ocr_results):
            box, text, score = res
            if "pembeli" in text.lower():
                end_idx = i
                break

    if end_idx is None:
        return None

    # 2. Cari baris awal pembeli dengan melangkah mundur dari end_idx
    start_idx = 0
    for i in range(end_idx - 1, -1, -1):
        box, text, score = ocr_results[i]
        
        # Jika ketemu penutup penjual, maka baris sesudahnya adalah awal pembeli
        if is_seller_conclusion_line(text):
            start_idx = i + 1
            break
            
        # Jika ketemu penanda awal pembeli seperti II.- atau 2.-
        if is_buyer_start_line(text):
            start_idx = i
            break

    # Pastikan start_idx <= end_idx
    if start_idx > end_idx:
        start_idx = max(0, end_idx - 5)

    selected_results = ocr_results[start_idx : end_idx + 1]
    raw_lines = [item[1] for item in selected_results]

    # 3. Kumpulkan koordinat seluruh kotak teks terpilih
    all_boxes = [item[0] for item in selected_results]
    all_pts = np.array(all_boxes).reshape(-1, 2)
    
    min_x = float(np.min(all_pts[:, 0]))
    max_x = float(np.max(all_pts[:, 0]))
    min_y = float(np.min(all_pts[:, 1]))
    max_y = float(np.max(all_pts[:, 1]))

    # 4. Berikan padding yang rapi dan proporsional terhadap DPI
    # Skala padding relatif terhadap 150 DPI
    scale_factor = dpi / 150.0
    pad_left = int(22 * scale_factor)
    pad_right = int(32 * scale_factor)
    pad_top = int(14 * scale_factor)
    pad_bottom = int(16 * scale_factor)

    h_img, w_img = img_shape[:2]
    x1 = max(0, int(min_x - pad_left))
    x2 = min(w_img, int(max_x + pad_right))
    y1 = max(0, int(min_y - pad_top))
    y2 = min(h_img, int(max_y + pad_bottom))

    return (x1, y1, x2, y2, raw_lines)
