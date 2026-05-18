import requests
import io
from pypdf import PdfReader
from bs4 import BeautifulSoup
import os

class ReportAnalyzer:
    """
    Analyzer for PDF reports and XBRL-like data.
    Provides text extraction for LLM consumption.
    """
    
    def __init__(self, download_dir="workspace/potential-elephant/data/downloads"):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })

    def download_pdf(self, url, filename):
        """
        Download a PDF from a URL.
        """
        try:
            response = self.session.get(url, timeout=20)
            if response.status_code == 200:
                path = os.path.join(self.download_dir, filename)
                with open(path, "wb") as f:
                    f.write(response.content)
                return path
            else:
                print(f"Failed to download PDF: {url} (Status: {response.status_code})")
                return None
        except Exception as e:
            print(f"Error downloading PDF {url}: {e}")
            return None

    def extract_text_from_pdf(self, pdf_path):
        """
        Extract text content from a PDF file.
        """
        print(f"Extracting text from: {pdf_path}")
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            print(f"Error extracting text from PDF {pdf_path}: {e}")
            return None

    def analyze_disclosure_text(self, text):
        """
        A placeholder for basic rule-based analysis before passing to LLM.
        Can look for keywords like '増益' (profit increase), '減益' (profit decrease), etc.
        """
        if not text:
            return {}
            
        results = {
            "keywords": [],
            "word_count": len(text.split())
        }
        
        # Simple JP keyword check
        jp_keywords = ["増益", "減益", "上方修正", "下方修正", "配当", "自社株買い"]
        for kw in jp_keywords:
            if kw in text:
                results["keywords"].append(kw)
                
        return results

if __name__ == "__main__":
    analyzer = ReportAnalyzer()
    
    # Test with a sample disclosure PDF if possible, or just mock
    test_pdf_url = "https://www.release.tdnet.info/inbs/140120260518539655.pdf" # Example from earlier
    print(f"\n--- Testing PDF Extraction: {test_pdf_url} ---")
    
    # path = analyzer.download_pdf(test_pdf_url, "test_disclosure.pdf")
    # if path:
    #     text = analyzer.extract_text_from_pdf(path)
    #     if text:
    #         print(f"Extracted {len(text)} characters.")
    #         print("Preview:", text[:500])
    #         analysis = analyzer.analyze_disclosure_text(text)
    #         print("Basic Analysis:", analysis)
    
    print("PDF Ingestor initialized. Set up for local analysis.")
