# Auto Crop Akta Tanah / PPAT (Rust)

Program berkinerja tinggi berbasis **Rust murni** untuk **memotong otomatis (auto-crop) bagian data identitas pembeli ("Pihak Kedua / Pembeli")** dari dokumen Akta Jual Beli (AJB) / Akta PPAT berformat PDF, serta mengekstrak informasi teks terstrukturnya (Nama, NIK, Tempat/Tanggal Lahir, Pekerjaan, Alamat).

---

## 🌟 Fitur Utama

1. **Native Rust & Performa Tinggi**:
   - Dibuat sepenuhnya dalam bahasa Rust tanpa ketergantungan runtime Python atau C++ eksternal.
   - Menggunakan API bawaan sistem Windows (`Windows.Data.Pdf` untuk rendering PDF dan `Windows.Media.Ocr` untuk pengenalan teks berakselerasi perangkat keras).
2. **Koreksi Orientasi Otomatis (*Auto-Rotate / Upright Alignment*)**:
   - Akta PPAT yang dipindai mendatar/miring (*landscape*) secara otomatis diputar tegak (*portrait 270°*) agar teks horizontal dan mudah dibaca.
3. **Deteksi Cerdas Lokasi Pembeli**:
   - Menemukan halaman tempat identitas pembeli berada di antara puluhan halaman akta.
   - Menghitung koordinat batas (*bounding box*) dari awal identitas (`II.-Tuan...`) hingga penutup (`-"Pihak Kedua/Pembeli".-`).
4. **Hasil Potongan Presisi & Berkualitas Tinggi**:
   - Dilengkapi padding margin yang rapi dan simetris.
   - Menghasilkan gambar potongan (PNG/JPG) yang jernih dan tajam.
5. **Ekstraksi Data Terstruktur (*JSON Export*)**:
   - Mengekstrak field:
     - **Nama Lengkap & Sapaan** (Tuan, Nyonya, dsb.)
     - **NIK** (Nomor Induk Kependudukan 16 digit)
     - **Tempat & Tanggal Lahir**
     - **Pekerjaan**
     - **Alamat Lengkap**
6. **Dukungan Pemrosesan Sekaligus (*Batch Processing*)**:
   - Mampu memproses satu file atau seluruh file PDF dalam folder sekaligus secara otomatis.

---

## 📁 Struktur Proyek Rust

```text
auto-crop-akta/
├── Cargo.toml                # Konfigurasi dependensi Rust
├── src/
│   ├── lib.rs                # Engine utama: render PDF, rotasi, OCR, cropping, anotasi
│   ├── main.rs               # CLI interface (Clap)
│   └── parser.rs             # Parser regex data pembeli (Nama, NIK, TTL, Alamat)
├── sample_input.pdf          # Contoh file PDF akta asli
├── sample_output_reference.png # Contoh output acuan
└── README.md                 # Dokumentasi
```

---

## 🚀 Kompilasi & Menjalankan

Pastikan Anda memiliki toolchain Rust (`cargo` dan `rustc`).

### 1. Kompilasi Release Binary
```bash
cargo build --release
```
File executable mandiri (*standalone executable*) akan berada di:
`target/release/auto-crop-akta.exe`

---

## 💻 Panduan Penggunaan CLI

### A. Memproses Satu File PDF
```bash
cargo run --release -- sample_input.pdf
```
*atau langsung menggunakan file executable:*
```bash
.\target\release\auto-crop-akta.exe sample_input.pdf
```
*Secara default hasil potongan akan disimpan sebagai `sample_input_crop_pembeli.png`.*

### B. Menentukan Nama File Output
```bash
cargo run --release -- sample_input.pdf -o hasil_crop.png
```

### C. Menyimpan Halaman Anotasi & Metadata JSON
Gunakan opsi `--annotated` untuk menghasilkan halaman penuh berkotak oranye, dan `--json` untuk menghasilkan file metadata `.json`:
```bash
cargo run --release -- sample_input.pdf -o hasil_crop.png --annotated --json
```

Contoh keluaran file `.json`:
```json
{
  "success": true,
  "page_number": 4,
  "total_pages": 8,
  "rotation_applied": 270,
  "bbox": {
    "x": 373,
    "y": 1231,
    "width": 1147,
    "height": 523
  },
  "raw_text": "11.-Tuan MUHAMMAD FADHLILLAH, Warga Negara Indonesia, lahir...",
  "buyer_info": {
    "sapaan": "Tuan",
    "nama": "MUHAMMAD FADHLILLAH",
    "nik": "3321010612060001",
    "ttl": "Demak, 06 (enam) Desember tahun 2006 (duaribu enam)",
    "pekerjaan": "Pelajar/ Mahasiswa",
    "alamat": "Kabupaten Demak, Pondok Majapahit I Blok KK Nomor 17, Rukun Tetangga 006, Rukun Warga 005, Desa Bandungrejo, Kecamatan Mranggen",
    "peran": "Pihak Kedua / Pembeli"
  }
}
```

### D. Memproses Seluruh File dalam Folder (*Batch Mode*)
```bash
cargo run --release -- ./folder_kumpulan_akta/ --out-dir ./folder_hasil/ --json
```

---

## 📦 Penggunaan Sebagai Library Rust (`src/lib.rs`)

Anda juga dapat memanggil engine ini langsung dari kode Rust lainnya:

```rust
use std::path::Path;
use auto_crop_akta::process_akta_pdf;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let pdf_path = Path::new("sample_input.pdf");
    let result = process_akta_pdf(pdf_path, 2.0).await?;

    println!("Halaman ditemukan: {}", result.page_number);
    println!("Nama Pembeli: {:?}", result.buyer_info.nama);
    println!("NIK: {:?}", result.buyer_info.nik);

    result.cropped_image.save("crop_output.png")?;
    Ok(())
}
```
