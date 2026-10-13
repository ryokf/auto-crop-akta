"""
Auto Crop Akta: Program pemotong otomatis akta di lokasi data pembeli.
"""

from .cropper import process_akta_pdf
from .parser import parse_buyer_info

__all__ = ["process_akta_pdf", "parse_buyer_info"]
