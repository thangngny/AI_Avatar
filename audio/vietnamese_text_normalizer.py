"""
AI Avatar NextGen V2 - Vietnamese Text Normalizer
Normalizes raw Vietnamese scripts into speech-ready phonetic text for AI Presenter Studio.
Handles:
- Numbers, decimals, percentages
- Dates and time
- Currency (VND, USD)
- Abbreviations and proper names
- Tech and broadcast acronyms (AI, MC, GPU, VTV, etc.)
- Pause and rhythm punctuation conditioning
"""
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


class VietnameseTextNormalizer:
    def __init__(self):
        self.digits_map = {
            '0': 'không', '1': 'một', '2': 'hai', '3': 'ba', '4': 'bốn',
            '5': 'năm', '6': 'sáu', '7': 'bảy', '8': 'tám', '9': 'chín'
        }
        self.acronyms_map = {
            r'\bAI\b': 'A I',
            r'\bMC\b': 'M C',
            r'\bVTV\b': 'V T V',
            r'\bHTV\b': 'H T V',
            r'\bVOV\b': 'V O V',
            r'\bTP\.?HCM\b': 'Thành phố Hồ Chí Minh',
            r'\bHN\b': 'Hà Nội',
            r'\bVN\b': 'Việt Nam',
            r'\bGPU\b': 'G P U',
            r'\bCPU\b': 'C P U',
            r'\bRTX\b': 'R T X',
            r'\bVRAM\b': 'V Ram',
            r'\bRAM\b': 'Ram',
            r'\bSSD\b': 'S S D',
            r'\bFPS\b': 'F P S',
            r'\bAPI\b': 'A P I',
            r'\bTTS\b': 'T T S',
            r'\bUI\b': 'U I',
            r'\bUX\b': 'U X',
            r'\bCEO\b': 'C E O',
            r'\bCTO\b': 'C T O',
            r'\bUSD\b': 'đô la',
            r'\bVND\b': 'đồng',
            r'\bVNĐ\b': 'đồng',
            r'\%': ' phần trăm',
            r'\&': ' và ',
            r'\+': ' cộng '
        }

    def _read_2_digits(self, num_str: str) -> str:
        if len(num_str) == 1:
            return self.digits_map[num_str]
        d1, d2 = num_str[0], num_str[1]
        res = ""
        if d1 == '1':
            res = "mười"
        else:
            res = self.digits_map[d1] + " mươi"

        if d2 == '0':
            return res
        elif d2 == '1':
            return res + (" một" if d1 == '1' else " mốt")
        elif d2 == '5':
            return res + " lăm"
        else:
            return res + " " + self.digits_map[d2]

    def _read_3_digits(self, num_str: str, read_zero_hundred: bool = False) -> str:
        num_str = num_str.zfill(3)
        d0, d1, d2 = num_str[0], num_str[1], num_str[2]
        res = ""
        if d0 != '0' or read_zero_hundred:
            res = self.digits_map[d0] + " trăm"

        if d1 == '0':
            if d2 != '0':
                if res:
                    res += " linh " + self.digits_map[d2]
                else:
                    res = self.digits_map[d2]
        else:
            two_digit = self._read_2_digits(d1 + d2)
            res += (" " if res else "") + two_digit

        return res.strip()

    def number_to_words(self, n: int) -> str:
        if n == 0:
            return "không"
        scales = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ"]
        s = str(n)
        groups = []
        while s:
            groups.append(s[-3:])
            s = s[:-3]

        words = []
        for i, group in enumerate(groups):
            val = int(group)
            if val != 0:
                is_highest = (i == len(groups) - 1)
                group_words = self._read_3_digits(group, read_zero_hundred=not is_highest)
                scale = scales[i]
                part = f"{group_words} {scale}".strip()
                words.append(part)

        return " ".join(reversed(words)).strip()

    def normalize_dates(self, text: str) -> str:
        # DD/MM/YYYY or DD-MM-YYYY
        def date_repl(match):
            d, m, y = match.group(1), match.group(2), match.group(3)
            d_word = self.number_to_words(int(d))
            m_word = self.number_to_words(int(m))
            y_word = self.number_to_words(int(y))
            return f"ngày {d_word} tháng {m_word} năm {y_word}"

        text = re.sub(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', date_repl, text)

        # DD/MM
        def short_date_repl(match):
            d, m = match.group(1), match.group(2)
            d_word = self.number_to_words(int(d))
            m_word = self.number_to_words(int(m))
            return f"ngày {d_word} tháng {m_word}"

        text = re.sub(r'\b(\d{1,2})[/-](\d{1,2})\b', short_date_repl, text)
        return text

    def normalize_currency(self, text: str) -> str:
        # 5.000.000đ or 5,000,000 VND
        def curr_repl(match):
            num_clean = match.group(1).replace('.', '').replace(',', '')
            val = int(num_clean)
            return f"{self.number_to_words(val)} đồng"

        text = re.sub(r'\b(\d{1,3}(?:[.,]\d{3})+)\s*(?:đ|đồng|VND|VNĐ)\b', curr_repl, text, flags=re.IGNORECASE)

        # $100 or 100 USD
        def usd_repl(match):
            num_clean = match.group(1).replace('.', '').replace(',', '')
            val = int(num_clean)
            return f"{self.number_to_words(val)} đô la"

        text = re.sub(r'\$\s*(\d+(?:[.,]\d+)?)', usd_repl, text)
        text = re.sub(r'\b(\d+(?:[.,]\d+)?)\s*USD\b', usd_repl, text, flags=re.IGNORECASE)
        return text

    def normalize_numbers(self, text: str) -> str:
        # Standalone integers up to 12 digits
        def num_repl(match):
            n = int(match.group(0))
            return self.number_to_words(n)

        # Avoid matching numbers already in words or alphanumeric IDs
        return re.sub(r'\b\d+\b', num_repl, text)

    def normalize_acronyms(self, text: str) -> str:
        for pattern, replacement in self.acronyms_map.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    def clean_whitespace_and_punctuation(self, text: str) -> str:
        # Standardize multiple punctuation and spaces
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\s*([,.;:!?])\s*', r'\1 ', text)
        text = re.sub(r'\.{2,}', '...', text)
        return text.strip()

    def normalize(self, text: str) -> str:
        """Full pipeline normalization for Vietnamese speech."""
        if not text:
            return ""
        text = self.normalize_dates(text)
        text = self.normalize_currency(text)
        text = self.normalize_acronyms(text)
        text = self.normalize_numbers(text)
        text = self.clean_whitespace_and_punctuation(text)
        return text


if __name__ == "__main__":
    norm = VietnameseTextNormalizer()
    sample = "Hôm nay 23/10/2026, MC AI giới thiệu Studio V2 với GPU RTX 5090 giá $1.500 và 5.000.000đ cho VTV tại TP.HCM đạt 25 FPS."
    print("ORIGINAL  :", sample)
    print("NORMALIZED:", norm.normalize(sample))
