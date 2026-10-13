use regex::Regex;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BuyerJsonOutput {
    pub id: String,
    pub nik: String,
    pub nama: String,
    pub alamat: String,
    pub tempat_lahir: String,
    pub tgl_lahir: String,
    pub pekerjaan: String,
    pub tipe_bukti: String, // 1: KTP
}

pub fn clean_text(input: &str) -> String {
    let re_dashes = Regex::new(r"[-_]{2,}").unwrap();
    let re_spaces = Regex::new(r"\s+").unwrap();
    let no_dashes = re_dashes.replace_all(input, " ");
    re_spaces.replace_all(&no_dashes, " ").trim().to_string()
}

pub fn parse_indonesian_date(text: &str) -> Option<String> {
    let re_day = Regex::new(r"(?i)tanggal\s+(\d{1,2})").unwrap();
    let re_year = Regex::new(r"(?i)(?:tahun\s+)?\b(19\d{2}|20\d{2})\b").unwrap();

    let day = re_day.captures(text).map(|c| {
        let d: u32 = c[1].parse().unwrap_or(1);
        format!("{:02}", d)
    })?;

    let year = re_year.captures(text).map(|c| c[1].to_string())?;

    let lower = text.to_lowercase();
    let month = if lower.contains("januari") {
        "01"
    } else if lower.contains("februari") {
        "02"
    } else if lower.contains("maret") {
        "03"
    } else if lower.contains("april") {
        "04"
    } else if lower.contains("mei") {
        "05"
    } else if lower.contains("juni") {
        "06"
    } else if lower.contains("juli") {
        "07"
    } else if lower.contains("agustus") {
        "08"
    } else if lower.contains("september") {
        "09"
    } else if lower.contains("oktober") {
        "10"
    } else if lower.contains("november") {
        "11"
    } else if lower.contains("desember") {
        "12"
    } else {
        return None;
    };

    Some(format!("{}/{}/{}", day, month, year))
}

pub fn parse_buyer_to_custom_json(raw_text: &str, custom_id: Option<&str>) -> BuyerJsonOutput {
    let cleaned = clean_text(raw_text);

    // 1. ID
    let id = custom_id.unwrap_or("12345").to_string();

    // 2. NIK (16 digit)
    let nik_re = Regex::new(r"\b(\d{16})\b").unwrap();
    let nik = nik_re.captures(&cleaned).map(|c| c[1].to_string()).unwrap_or_default();

    // 3. Nama
    let nama_re = Regex::new(
        r"(?i)(?:(?:I{1,3}|IV|V|\d+)[\.\-\s]+)?(?:Tuan|Nyonya|Nona|Tn\.|Ny\.|Saudara|Sdri\.|Perseroan Terbatas|PT\.?)\s+([A-Z\s\.\,\'\`]+?)(?:,|\s+Warga|\s+lahir|\s+pemegang|\s+bertempat)"
    ).unwrap();

    let mut nama = String::new();
    if let Some(caps) = nama_re.captures(&cleaned) {
        let mut raw_name = caps[1].trim().to_string();
        raw_name = raw_name.trim_matches(|c: char| c == ',' || c == '.' || c == '-').trim().to_string();
        nama = raw_name;
    } else {
        // Fallback: cari kata-kata kapital di baris pertama
        let fallback_nama = Regex::new(r"(?i)(?:(?:I{1,3}|IV|V|\d+)[\.\-\s]+)?([A-Z\s]{4,35})(?:,|\s+Warga)").unwrap();
        if let Some(caps) = fallback_nama.captures(&cleaned) {
            nama = caps[1].trim().to_string();
        }
    }

    // 4. Tempat Lahir
    let tempat_re = Regex::new(r"(?i)lahir\s+di\s+([^,]+)").unwrap();
    let tempat_lahir = tempat_re.captures(&cleaned).map(|c| c[1].trim().to_string()).unwrap_or_default();

    // 5. Tanggal Lahir (DD/MM/YYYY)
    let tgl_lahir = parse_indonesian_date(&cleaned).unwrap_or_default();

    // 6. Pekerjaan
    let pek_re = Regex::new(r"(?i)(?:tahun\s+\d+|[a-z0-9]+\))\s*,\s*([A-Za-z\/\s\-]+?),\s*(?:pemegang|Nomor|Induk|Kependudukan)").unwrap();
    let pek_fallback = Regex::new(r"(?i)\b(Pelajar\/Mahasiswa|Pelajar\/\s*Mahasiswa|Karyawan\s+Swasta|Pegawai\s+Negeri\s+Sipil|PNS|Wiraswasta|Pedagang|Petani|Buruh|Ibu\s+Rumah\s+Tangga|Belum\/Tidak\s+Bekerja)\b").unwrap();

    let mut pekerjaan = String::new();
    if let Some(c) = pek_re.captures(&cleaned) {
        let p = c[1].trim().trim_matches(|ch: char| ch == ',' || ch == '.').trim().to_string();
        pekerjaan = p;
    } else if let Some(c) = pek_fallback.captures(&cleaned) {
        pekerjaan = c[1].trim().to_string();
    }
    // Normalkan ejaan: "Pelajar/ Mahasiswa" atau "Pelajar/Mahasiswa" -> "Pelajar / Mahasiswa"
    if pekerjaan.to_lowercase().contains("pelajar") && pekerjaan.to_lowercase().contains("mahasiswa") {
        pekerjaan = "Pelajar / Mahasiswa".to_string();
    }

    // 7. Alamat
    let mut alamat = String::new();
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
        alamat = raw_addr.to_string();
    }

    // 8. Tipe Bukti (1: KTP)
    let tipe_bukti = "1".to_string();

    BuyerJsonOutput {
        id,
        nik,
        nama,
        alamat,
        tempat_lahir,
        tgl_lahir,
        pekerjaan,
        tipe_bukti,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_sample_text() {
        let sample = r#"
11.-Tuan MUHAMMAD FADHLILLAH, Warga Negara Indonesia, lahir
di Demak, tanggal 06 (enam) Desember tahun 2006 (duaribu
enam), Pelajar/ Mahasiswa, Induk pemegang Nomor
Kependudukan (NIK): 3321010612060001, bertempat tinggal di
Kabupaten Demak, Pondok Majapahit I Blok KK Nomor 17,
Rukun Tetangga 006, Rukun Warga 005, Desa Bandungrejo,
Kecamatan Mranggen.-
-untuk selanjutnya dalam akta ini disebut:-
-"Pihak Kedua/ Pembeli".
"#;
        let res = parse_buyer_to_custom_json(sample, Some("12345"));
        assert_eq!(res.id, "12345");
        assert_eq!(res.nik, "3321010612060001");
        assert_eq!(res.nama, "MUHAMMAD FADHLILLAH");
        assert_eq!(res.tempat_lahir, "Demak");
        assert_eq!(res.tgl_lahir, "06/12/2006");
        assert_eq!(res.pekerjaan, "Pelajar / Mahasiswa");
        assert_eq!(res.tipe_bukti, "1");
        assert!(res.alamat.contains("Kabupaten Demak"));
    }
}
