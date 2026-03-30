from http.server import BaseHTTPRequestHandler
import json
import urllib.parse
import re
import traceback

class handler(BaseHTTPRequestHandler):
    
    # 🚀 NEW: Added OPTIONS method to prevent Frontend CORS Blocking!
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            import requests
            from bs4 import BeautifulSoup

            # 🚀 BUG FIX: Extract the FULL URL safely bypassing the '&' symbol issue!
            if 'url=' not in self.path:
                self.wfile.write(json.dumps({"error": "No URL provided"}).encode('utf-8'))
                return
            
            # Grab everything exactly as it is after 'url='
            raw_url = self.path.split('url=')[1]
            target_url = urllib.parse.unquote(raw_url)

            # 🚀 NEW: Stealth headers to ensure the exam portal doesn't block the server
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            
            res = requests.get(target_url, headers=headers, timeout=15)
            html_text = res.text
            soup = BeautifulSoup(html_text, 'html.parser')
            
            p_id, p_name, exam_name = "UNKNOWN", "UNKNOWN", "UNKNOWN"
            
            # 1. Extract Meta Data
            main_info = soup.find('div', class_='main-info-pnl')
            if main_info:
                for row in main_info.find_all('tr'):
                    cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                    if len(cells) >= 2:
                        key = cells[0].upper()
                        val = cells[1]
                        if 'PARTICIPANT ID' in key: p_id = val
                        elif 'PARTICIPANT NAME' in key: p_name = val
                        elif 'SUBJECT' in key: exam_name = val

            if exam_name == "UNKNOWN":
                m_subj = re.search(r'>\s*Subject\s*<.*?>\s*(.*?)\s*<', html_text, re.I)
                if m_subj: exam_name = m_subj.group(1).strip()

            all_sections_data = {}
            total_questions_count = 0
            current_section = "General"

            # 2. BULLETPROOF LOGIC: Flat Sequential Scan 
            for tag in soup.find_all(['div', 'table'], class_=re.compile(r'section-lbl|question-pnl', re.I)):
                classes = tag.get('class', [])
                
                # A. Section Label
                if any('section-lbl' in c.lower() for c in classes):
                    sec_name_tag = tag.find(class_='bold')
                    if sec_name_tag:
                        current_section = sec_name_tag.text.strip()
                    continue
                
                # B. Question Panel
                if any('question-pnl' in c.lower() for c in classes):
                    try:
                        menu_tbl = tag.find('table', class_='menu-tbl')
                        if not menu_tbl: continue
                        
                        menu_tds = menu_tbl.find_all('td')
                        cells = [td.get_text(strip=True) for td in menu_tds]
                        
                        qid = None
                        opts = {}
                        chosen_id = "-"
                        
                        for i in range(len(cells) - 1):
                            label = cells[i]
                            val = cells[i+1]
                            
                            if 'Question ID' in label: qid = val
                            elif 'Option 1 ID' in label: opts['1'] = val
                            elif 'Option 2 ID' in label: opts['2'] = val
                            elif 'Option 3 ID' in label: opts['3'] = val
                            elif 'Option 4 ID' in label: opts['4'] = val
                            elif 'Chosen Option' in label:
                                if val in opts: chosen_id = opts[val]
                        
                        if not qid or not qid.isdigit(): continue
                        
                        if current_section not in all_sections_data:
                            all_sections_data[current_section] = {}
                            
                        if qid in all_sections_data[current_section]:
                            continue
                        
                        prov_right_id = "-"
                        row_tbl = tag.find('table', class_='questionRowTbl')
                        if row_tbl:
                            right_ans_td = row_tbl.find('td', class_='rightAns')
                            if right_ans_td:
                                m = re.search(r'([1-4])\.', right_ans_td.get_text(strip=True))
                                if m and m.group(1) in opts:
                                    prov_right_id = opts[m.group(1)]
                        
                        all_sections_data[current_section][qid] = {
                            "chosen_id": chosen_id, 
                            "prov_right_id": prov_right_id
                        }
                        total_questions_count += 1
                        
                    except Exception:
                        continue

            # 3. Output Final JSON
            result = {
                "status": "success", 
                "meta": { "p_id": p_id, "p_name": p_name, "exam_name": exam_name },
                "total_q": total_questions_count,
                "sections": all_sections_data
            }
            
            self.wfile.write(json.dumps(result).encode('utf-8'))

        except Exception as e:
            error_trace = traceback.format_exc()
            self.wfile.write(json.dumps({
                "status": "error", 
                "error_message": str(e), 
                "trace": error_trace
            }).encode('utf-8'))
                        
