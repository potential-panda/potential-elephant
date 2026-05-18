import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time

class TDnetIngestor:
    """
    Ingestor for Timely Disclosure information from TDnet.
    Note: TDnet structure often uses iframes. The main list is typically at:
    https://www.release.tdnet.info/inbs/I_list_001_YYYYMMDD.html
    """
    
    BASE_URL = "https://www.release.tdnet.info/inbs/"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })

    def get_latest_disclosures(self, date_str=None):
        """
        Fetch disclosures for a specific date (YYYYMMDD). 
        Defaults to today if date_str is None.
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")
            
        url = f"{self.BASE_URL}I_list_001_{date_str}.html"
        print(f"Fetching disclosures from: {url}")
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                print(f"Failed to fetch data for {date_str}. Status: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error fetching TDnet: {e}")
            return None
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # TDnet rows have specific class structures like oddnew-L, evennew-L etc.
        # We can find all <tr> tags and check their children.
        rows = soup.find_all("tr")
        data = []
        for row in rows:
            cols = row.find_all("td")
            # A valid disclosure row has at least 5 columns and specific classes
            if len(cols) < 5:
                continue
            
            # Use the time column as an indicator of a data row
            time_td = cols[0]
            if "kjTime" not in time_td.get("class", []):
                continue
                
            try:
                disclosure = {
                    "time": time_td.get_text(strip=True),
                    "code": cols[1].get_text(strip=True),
                    "company": cols[2].get_text(strip=True),
                    "title": cols[3].get_text(strip=True),
                    "pdf_url": self.BASE_URL + cols[3].find("a")["href"] if cols[3].find("a") else None,
                }
                # XBRL is usually in column index 4 (0-indexed)
                xbrl_link = cols[4].find("a")
                if xbrl_link:
                    disclosure["xbrl_url"] = self.BASE_URL + xbrl_link["href"]
                else:
                    disclosure["xbrl_url"] = None

                data.append(disclosure)
            except Exception as e:
                # print(f"Skipping row due to error: {e}")
                continue
            
        return pd.DataFrame(data)

if __name__ == "__main__":
    ingestor = TDnetIngestor()
    # Try fetching for today
    df = ingestor.get_latest_disclosures()
    if df is not None and not df.empty:
        print(f"Found {len(df)} disclosures.")
        print(df.head())
    else:
        # If today is a weekend or early morning, try yesterday
        import datetime as dt
        yesterday = (dt.datetime.now() - dt.timedelta(days=1)).strftime("%Y%m%d")
        print(f"No data for today. Trying yesterday: {yesterday}")
        df = ingestor.get_latest_disclosures(yesterday)
        if df is not None and not df.empty:
            print(f"Found {len(df)} disclosures for {yesterday}.")
            print(df.head())
