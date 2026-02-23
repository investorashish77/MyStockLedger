import pdfplumber
import pandas as pd
import re

class BSEFinancialParser:
    def __init__(self, file_path):
        self.file_path = file_path
        
    def extract_consolidated_table(self):
        with pdfplumber.open(self.file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    df = pd.DataFrame(table)
                    # Detect consolidated table by keywords
                    content = df.to_string().lower()
                    if "consolidated" in content and "revenue" in content:
                        return self._clean_table(df)
        return None

    def _clean_table(self, df):
        # Remove empty rows and handle spanning headers
        df = df.dropna(how='all').reset_index(drop=True)
        return df

    def parse_metrics(self, df):
        # The key is mapping row labels to columns: 
        # Col 1: Metrics | Col 2: Q3FY26 (Current) | Col 3: Q2FY26 (Preceding) | Col 4: Q3FY25 (YoY)
        results = {
            "Revenue": self._find_row(df, r"Revenue from operations|Total Income", 1),
            "EBITDA": self._calculate_ebitda(df),
            "PAT": self._find_row(df, r"Profit/(loss) for the period|Net Profit", 1),
            "EPS": self._find_row(df, r"Earnings per share", 1),
            "Special Items": self._find_row(df, r"Exceptional item", 1)
        }
        return results

    def _find_row(self, df, pattern, col_idx):
        for i, row in df.iterrows():
            if re.search(pattern, str(row[0]), re.I):
                return row[col_idx]
        return "NA"

    def _calculate_ebitda(self, df):
        # Professional approach: PBT + Finance Costs + Depreciation
        pbt = float(self._find_row(df, r"Profit/(loss) before tax", 1).replace(',', ''))
        finance = float(self._find_row(df, r"Finance cost", 1).replace(',', ''))
        dep = float(self._find_row(df, r"Depreciation", 1).replace(',', ''))
        return f"{pbt + finance + dep:.2f}"