import pytesseract, re, cv2
from pdf2image import convert_from_path
import numpy as np
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = 'tesseract'  # On Linux

def preprocess_image(image):
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresh)

def extract_values(text):
    energy_match = re.search(r'Energy\s*\(kWh\)\s*\n?([\d,]+)', text)
    amount_match = re.search(r'Amount\s*\(INR\)\s*\n?([\d,]+)', text)

    energy_value = energy_match.group(1) if energy_match else "Not found"
    amount_value = amount_match.group(1) if amount_match else "Not found"

    return energy_value, amount_value

# def process_bill(file_path):
#     extracted_text = ""

#     if file_path.lower().endswith(".pdf"):
#         images = convert_from_path(file_path)  # Add poppler_path=... if needed
#     else:
#         images = [Image.open(file_path)]

#     for image in images:
#         processed_image = preprocess_image(image)
#         text = pytesseract.image_to_string(processed_image, config="--oem 3 --psm 6")
#         extracted_text += text + "\n"
    
#     return extracted_text

    # energy, amount = extract_values(extracted_text)  # Extract required values
    # print(f"Extracted Energy (kWh): {energy}")
    # print(f"Extracted Amount (INR): {amount}")
 
# Example Usage
# file_path = r"BRPL-20240919T114259Z-001\SECI Sitac\BRPL Sitac T-V July 2024.PDF"  # Change to your file path
# process_bill(file_path)


def process_bill(file_path):
    extracted_text = ""

    # Convert PDF pages to images
    if file_path.lower().endswith(".pdf"):
        # No need to set poppler_path if pdftoppm is in /usr/bin
        images = convert_from_path(file_path)
    else:
        images = [Image.open(file_path)]

    for image in images:
        processed_image = preprocess_image(image)
        text = pytesseract.image_to_string(processed_image, config="--oem 3 --psm 6")
        extracted_text += text + "\n"

    return extracted_text

    # Extract required values
#     energy, amount = extract_values(extracted_text)
#     print(f"Extracted Energy (kWh): {energy}")
#     print(f"Extracted Amount (INR): {amount}")

# # Example usage
# file_path = "/home/yourusername/Documents/BRPL_Sitac_TV_July_2024.pdf"  # Update this path
# process_bill(file_path)



# Basic number mapping
number_map = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
    'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
    'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40,
    'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80,
    'ninety': 90
}

# Multiplier map
multiplier_map = {
    'hundred': 100,
    'thousand': 1_000,
    'lakh': 1_00_000,
    'crore': 1_00_00_000
}

# Known typo corrections
typo_corrections = {
    'eightesn': 'eighteen',
    'falthtuly': 'faithfully',
    'pa': 'paise',
    'amountin': 'amount in',
    'amontin': 'amount in',
    'ammountin': 'amount in',
    'ammount': 'amount',
    'ninenty': 'ninety',
    'thrity': 'thirty',
    'twentty': 'twenty',
    'seventeeen': 'seventeen'
}

def correct_typos(word):
    return typo_corrections.get(word.lower(), word.lower())

def words_to_number(words):
    total = 0
    current = 0
    for word in words:
        word = correct_typos(word)

        if '-' in word:  # handle hyphenated words like "thirty-seven"
            parts = word.split('-')
            for part in parts:
                part = correct_typos(part)
                if part in number_map:
                    current += number_map[part]
        elif word in number_map:
            current += number_map[word]
        elif word in multiplier_map:
            if current == 0:
                current = 1
            current *= multiplier_map[word]
            total += current
            current = 0
    total += current
    return total

def extract_amount_in_words(text):
    match = re.search(
        r'(?:Amount\s+In\s+words|Amountin\s+words|Amount\s+in\s+Words):\s*([A-Za-z\s\-]+?)\s+Rupees(?:\s+([A-Za-z\s\-]+?)\s+(?:Paise|Pa|P))?',
        text,
        re.IGNORECASE
    )
    if match:
        rupees_text = match.group(1).strip()
        paise_text = match.group(2).strip() if match.group(2) else ""

        rupees = words_to_number(rupees_text.split())
        paise = words_to_number(paise_text.split()) if paise_text else 0

        return f"{rupees + (paise / 100):.2f}"
    else:
        return "No amount in words found."

# Test input
# a = """
# ESI FY A a eR ETT ag SNS SOS A Ge eC a
# se ie VARS a a Rees rls a Mees Rent epee er oe URE ee
# Fa FRG Us Oe TG Tes anit MERE el ues cleat ey an So reaatsiad bce eins (Sage al eae
# Provisional energy 27160000 3,612, 134,03141361 | oss | 19,866,737.17
# Amountin words: One Crore Ninety Eight Lakh Sixty Six Thousand Seven Hundred Thirty Seven Rupees Seventeen Paise
# tan
# Payment Term and Condition: HXomstsiteealy
# 1, Payment is to be deposited on or before Sep 4, 2024 ey Sos
# 2. Surcharges on delayed payment shall be applicable as per lerris and row aie Oy
# condition of agreement. . ea WoW AR WD
# 3. Payment of Invoice to be made with TCS in compl
# """

# print("Extracted Number:", extract_amount_in_words(a))
