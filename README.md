# Auto Crop Akta Tanah / PPAT

Program cerdas untuk **memotong otomatis (auto-crop) bagian data identitas pembeli ("Pihak Kedua / Pembeli")** dari dokumen Akta Jual Beli (AJB) atau Akta PPAT berformat PDF, serta mengekstrak informasi teks terstrukturnya (Nama, NIK, TTL, Pekerjaan, Alamat).

---

## 🌟 Fitur Utama

1. **Deteksi Otomatis Halaman & Lokasi Pembeli**:
   - Memindai seluruh halaman dokumen akta secara cerdas.
   - Menemukan halaman dan koordinat batas (*bounding box*) tempat identitas pihak pembeli berada (dimulai dari `II.-Tuan...` hingga penutup `-"Pihak Kedua/Pembeli".-`).
2. **Koreksi Orientasi Otomatis (*Auto-Rotate / Upright Alignment*)**:
   - Akta PPAT yang di-scan mendatar/miring (*landscape*) otomatis diputar menjadi tegak (*portrait*) dengan teks horizontal yang siap dibaca.
3. **Hasil Potongan Presisi & Berkualitas Tinggi**:
   - Dilengkapi padding yang pas dan rapi sesuai margin dokumen asli.
   - Menghasilkan gambar beresolusi tinggi (PNG/JPG) yang jernih.
4. **Ekstraksi Metadata Terstruktur**:
   - Otomatis mengekstrak field:
     - **Nama Lengkap & Sapaan** (Tuan, Nyonya, dsb.)
     - **NIK** (Nomor Induk Kependudukan 16 digit)
     - **Tempat & Tanggal Lahir**
     - **Pekerjaan**
     - **Alamat Lengkap**
5. **Dua Mode Penggunaan Fleksibel**:
   - **CLI (Command Line)**: Untuk otomatisasi, skrip backend, dan pemrosesan ratusan file sekaligus (*batch processing*).
   - **Web GUI (Browser)**: Antarmuka modern dengan *drag & drop*, pratinjau langsung, tombol unduh, dan salin ke clipboard.

---

## 📁 Struktur Direktori

```text
auto-crop-akta/
├── akta_cropper/             # Modul inti pemrosesan
│   ├── __init__.py           # Package initializer
│   ├── detector.py           # Render PDF, rotasi otomatis, & deteksi bounding box
│   ├── cropper.py            # Pipeline pemotong & anotasi citra
│   └── parser.py             # Parser metadata (Nama, NIK, TTL, Alamat)
├── main.py                   # CLI tool utama
├── web_app.py                # Web GUI lokal (berbasis browser)
├── test_run.py               # Skrip pengujian otomatis
├── sample_input.pdf          # Contoh file PDF akta asli
├── sample_output_reference.png # Contoh output acuan
├── requirements.txt          # Dependensi Python
└── README.md                 # Dokumentasi
```

---

## 🚀 Instalasi & Persiapan

Pastikan Anda telah menginstal **Python 3.10+**. Jalankan perintah berikut di terminal:

```bash
pip install -r requirements.txt
```

Dependensi utama:
- `pymupdf`: Rendering cepat dan akurat halaman PDF.
- `rapidocr_onnxruntime`: Engine OCR berbasis ONNX (ringan, cepat, tidak memerlukan instalasi eksternal Tesseract).
- `opencv-python` & `pillow`: Pemrosesan dan manipulasi citra.
- `numpy`: Komputasi koordinat bounding box.

---

## 💻 Cara Penggunaan

### 1. Menggunakan Web GUI (Paling Mudah)

Jalankan perintah berikut:

```bash
python web_app.py
```
*atau melalui CLI:*
```bash
python main.py --gui
```

Browser Anda akan otomatis terbuka di `http://127.0.0.1:5050`:
1. **Tarik & letakkan file PDF akta** ke area upload.
2. Klik **Potong Data Pembeli**.
3. Hasil potongan gambar langsung tampil dan dapat diunduh dalam format PNG.
4. Data teks (Nama, NIK, Alamat) langsung dapat disalin dengan satu klik.

---

### 2. Menggunakan Command Line (CLI)

#### A. Memproses Satu File PDF
```bash
python main.py dokumen_akta.pdf
```
*Secara default hasil potongan akan disimpan sebagai `dokumen_akta_crop_pembeli.png`.*

#### B. Menentukan Nama File Output
```bash
python main.py dokumen_akta.pdf -o hasil_crop.png
```

#### C. Menyimpan Halaman Anotasi & Metadata JSON
Gunakan flag `--annotated` untuk menyimpan halaman penuh dengan kotak penanda oranye, dan `--json` untuk mengekstrak data teks ke file `.json`:
```bash
python main.py dokumen_akta.pdf -o hasil.png --annotated --json
```

Contoh isi file `.json` yang dihasilkan:
```json
{
  "file": "dokumen_akta.pdf",
  "halaman": 4,
  "bbox": {
    "x1": 290,
    "y1": 955,
    "x2": 1195,
    "y2": 1371,
    "width": 905,
    "height": 416
  },
  "data_pembeli": {
    "sapaan": "Tuan",
    "nama": "MUHAMMAD FADHLILLAH",
    "nik": "3321010612060001",
    "ttl": "Demak, 06 (enam) Desember tahun 2006 (duaribu enam)",
    "pekerjaan": "Pelajar/Mahasiswa",
    "alamat": "Kabupaten Demak, Pondok Majapahit I Blok KK Nomor 17, Rukun Tetangga 006, Rukun Warga 005, Desa Bandungrejo, Kecamatan Mranggen",
    "peran": "Pihak Kedua / Pembeli"
  }
}
```

#### D. Memproses Seluruh File dalam Folder (*Batch Mode*)
```bash
python main.py ./kumpulan_akta/ --out-dir ./semua_hasil/ --json
```

---

### 3. Menggunakan Sebagai Library Python

Anda dapat mengintegrasikan modul ini langsung ke dalam skrip Python lainnya:

```python
from akta_cropper import process_akta_pdf

# Proses PDF
hasil = process_akta_pdf(
    pdf_input="akta_tanah.pdf",
    output_image_path="pembeli.png",
    dpi=150
)

if hasil["success"]:
    print(f"Ditemukan pada halaman: {hasil['page_number']}")
    print("Data Pembeli:", hasil["buyer_info"])
else:
    print("Gagal:", hasil["error"])
```

---

## 🧪 Pengujian & Verifikasi

Untuk menjalankan pengujian pipeline menggunakan file sampel acuan:

```bash
python test_run.py
```
