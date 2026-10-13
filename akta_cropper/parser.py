import re
from typing import Dict, Optional, Any

def clean_ocr_text(text: str) -> str:
    """Bersihkan karakter garis putus-putus dan separator khas akta."""
    # Hapus deretan dash atau underscore panjang
    cleaned = re.sub(r'[-_]{2,}', ' ', text)
    # Normalkan spasi berlebih
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def parse_buyer_info(raw_text: str) -> Dict[str, Optional[str]]:
    """
    Ekstraksi data terstruktur pembeli dari teks akta:
    - Nama
    - Sapaan / Gelar (Tuan, Nyonya, dsb.)
    - NIK (Nomor Induk Kependudukan)
    - Tempat & Tanggal Lahir
    - Pekerjaan
    - Alamat
    """
    cleaned = clean_ocr_text(raw_text)
    
    # 1. NIK (16 digit)
    nik = None
    nik_match = re.search(r'(?:NIK|Nomor\s+Induk\s+Kependudukan)[^\d]*(\d{16})', cleaned, re.IGNORECASE)
    if not nik_match:
        nik_match = re.search(r'\b(\d{16})\b', cleaned)
    if nik_match:
        nik = nik_match.group(1)

    # 2. Sapaan & Nama
    # Biasanya: "II.-Tuan MUHAMMAD FADHLILLAH," atau "2. Nyonya ..."
    sapaan = None
    nama = None
    nama_pattern = re.search(
        r'(?:(?:I{1,3}|IV|V|\d+)[\.\-\s]+)?'
        r'(Tuan|Nyonya|Nona|Tn\.|Ny\.|Saudara|Sdri\.|Perseroan Terbatas|PT\.?)\s+'
        r'([A-Z\s\.\,\'\`]+?)'
        r'(?:,|\s+Warga|\s+lahir|\s+pemegang|\s+bertempat)',
        cleaned
    )
    if nama_pattern:
        sapaan = nama_pattern.group(1).strip()
        nama_candidate = nama_pattern.group(2).strip()
        # Bersihkan trailing koma atau tanda baca
        nama_candidate = re.sub(r'[,.\-]+$', '', nama_candidate).strip()
        # Filter jika tidak terlalu pendek
        if len(nama_candidate) > 2:
            nama = nama_candidate
    else:
        # Fallback: cari kata-kata huruf kapital setelah II.- atau di awal
        fallback_nama = re.search(r'(?:(?:I{1,3}|IV|V|\d+)[\.\-\s]+)?([A-Z\s]{4,35})(?:,|\s+Warga)', cleaned)
        if fallback_nama:
            nama = fallback_nama.group(1).strip()

    # 3. Tempat & Tanggal Lahir
    ttl = None
    ttl_match = re.search(
        r'lahir\s+di\s+([^,]+),\s*tanggal\s+([^,]+(?:\([^\)]+\)[^,]*)?)',
        cleaned,
        re.IGNORECASE
    )
    if ttl_match:
        tempat = ttl_match.group(1).strip()
        tanggal = ttl_match.group(2).strip()
        ttl = f"{tempat}, {tanggal}"

    # 4. Pekerjaan
    pekerjaan = None
    # Pola 1: format standar satu kalimat
    pek_match = re.search(
        r'(?:tahun\s+\d+|[a-z0-9]+\))\s*,\s*([A-Za-z\/\s\-]+?),\s*(?:pemegang|Nomor|Induk|Kependudukan)',
        cleaned,
        re.IGNORECASE
    )
    if not pek_match:
        # Pola 2: ambil teks di antara penutup tanggal dan Kependudukan / NIK
        pek_match = re.search(
            r'(?:tahun\s+\d+[^\,]*\)|[a-z0-9]+\))\s*,\s*([A-Za-z\/\s\-]+?)\s+(?:Nomor|pemegang|Induk|Kependudukan|NIK)',
            cleaned,
            re.IGNORECASE
        )
    if not pek_match:
        # Pola 3: daftar pekerjaan umum di Indonesia
        pek_match = re.search(
            r'\b(Pelajar\/Mahasiswa|Karyawan\s+Swasta|Pegawai\s+Negeri\s+Sipil|PNS|Wiraswasta|Pedagang|Petani|Buruh|Ibu\s+Rumah\s+Tangga|Belum\/Tidak\s+Bekerja)\b',
            cleaned,
            re.IGNORECASE
        )

    if pek_match:
        pek_candidate = pek_match.group(1).strip()
        pek_candidate = re.sub(r'^[a-z0-9\(\)\s]+\)\s*,?\s*', '', pek_candidate, flags=re.IGNORECASE).strip()
        pek_candidate = re.sub(r'[,.\-]+$', '', pek_candidate).strip()
        if pek_candidate and len(pek_candidate) > 2:
            pekerjaan = pek_candidate

    # 5. Alamat
    alamat = None
    alamat_match = re.search(
        r'bertempat\s+tinggal\s+di\s+(.+?)(?=(?:-?\s*untuk\s+selanjutnya|\"?Pihak\s+Kedua|\"?Pembeli|$))',
        cleaned,
        re.IGNORECASE
    )
    if alamat_match:
        alamat_str = alamat_match.group(1).strip()
        # Bersihkan tanda baca di akhir
        alamat_str = re.sub(r'[\.\-\s]+$', '', alamat_str).strip()
        if alamat_str:
            alamat = alamat_str

    return {
        "sapaan": sapaan,
        "nama": nama,
        "nik": nik,
        "ttl": ttl,
        "pekerjaan": pekerjaan,
        "alamat": alamat,
        "peran": "Pihak Kedua / Pembeli"
    }
