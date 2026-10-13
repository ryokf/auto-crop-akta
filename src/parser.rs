use regex::Regex;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BuyerInfo {
    pub sapaan: Option<String>,
    pub nama: Option<String>,
    pub nik: Option<String>,
    pub ttl: Option<String>,
    pub pekerjaan: Option<String>,
    pub alamat: Option<String>,
    pub peran: String,
}

pub fn clean_text(input: &str) -> String {
    let re_dashes = Regex::new(r"[-_]{2,}").unwrap();
    let re_spaces = Regex::new(r"\s+").unwrap();
    let no_dashes = re_dashes.replace_all(input, " ");
    re_spaces.replace_all(&no_dashes, " ").trim().to_string()
}

pub fn parse_buyer_info(raw_text: &str) -> BuyerInfo {
    let cleaned = clean_text(raw_text);

    // 1. NIK (16 digit)
    let nik_re = Regex::new(r"\b(\d{16})\b").unwrap();
    let nik = nik_re.captures(&cleaned).map(|c| c[1].to_string());

    // 2. Sapaan & Nama
    let nama_re = Regex::new(
        r"(?i)(?:(?:I{1,3}|IV|V|\d+)[\.\-\s]+)?(Tuan|Nyonya|Nona|Tn\.|Ny\.|Saudara|Sdri\.|Perseroan Terbatas|PT\.?)\s+([A-Z\s\.\,\'\`]+?)(?:,|\s+Warga|\s+lahir|\s+pemegang|\s+bertempat)"
    ).unwrap();

    let mut sapaan = None;
    let mut nama = None;

    if let Some(caps) = nama_re.captures(&cleaned) {
        sapaan = Some(caps[1].trim().to_string());
        let mut raw_name = caps[2].trim().to_string();
        raw_name = raw_name.trim_matches(|c: char| c == ',' || c == '.' || c == '-').trim().to_string();
        if raw_name.len() > 2 {
            nama = Some(raw_name);
        }
    }

    // 3. Tempat & Tanggal Lahir
    let ttl_re = Regex::new(r"(?i)lahir\s+di\s+([^,]+),\s*tanggal\s+([^,]+(?:\([^\)]+\)[^,]*)?)").unwrap();
    let ttl = ttl_re.captures(&cleaned).map(|c| format!("{}, {}", c[1].trim(), c[2].trim()));

    // 4. Pekerjaan
    let pek_re = Regex::new(r"(?i)(?:tahun\s+\d+|[a-z0-9]+\))\s*,\s*([A-Za-z\/\s\-]+?),\s*(?:pemegang|Nomor|Induk|Kependudukan)").unwrap();
    let pek_fallback = Regex::new(r"(?i)\b(Pelajar\/Mahasiswa|Pelajar\/\s*Mahasiswa|Karyawan\s+Swasta|Pegawai\s+Negeri\s+Sipil|PNS|Wiraswasta|Pedagang|Petani|Buruh|Ibu\s+Rumah\s+Tangga|Belum\/Tidak\s+Bekerja)\b").unwrap();

    let mut pekerjaan = None;
    if let Some(c) = pek_re.captures(&cleaned) {
        let p = c[1].trim().trim_matches(|ch: char| ch == ',' || ch == '.').trim().to_string();
        if p.len() > 2 {
            pekerjaan = Some(p);
        }
    } else if let Some(c) = pek_fallback.captures(&cleaned) {
        pekerjaan = Some(c[1].trim().to_string());
    }

    // 5. Alamat (menggunakan pencarian substring tanpa regex look-around)
    let mut alamat = None;
    if let Some(pos) = cleaned.to_lowercase().find("bertempat tinggal di ") {
        let sub = &cleaned[pos + "bertempat tinggal di ".len()..];
        let sub_low = sub.to_lowercase();
        let mut end_pos = sub.len();

        for marker in ["-untuk", "untuk selanjutnya", "pihak kedua", "pembeli", "\"pihak"] {
            if let Some(idx) = sub_low.find(marker) {
                if idx < end_pos {
                    end_pos = idx;
                }
            }
        }

        let raw_addr = sub[..end_pos].trim().trim_matches(|ch: char| ch == '.' || ch == '-' || ch == ' ').trim();
        if !raw_addr.is_empty() {
            alamat = Some(raw_addr.to_string());
        }
    }

    BuyerInfo {
        sapaan,
        nama,
        nik,
        ttl,
        pekerjaan,
        alamat,
        peran: "Pihak Kedua / Pembeli".to_string(),
    }
}
