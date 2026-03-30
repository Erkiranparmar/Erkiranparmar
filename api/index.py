from http.server import BaseHTTPRequestHandler
import json
import urllib.parse
import re
import traceback

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            import requests
            from bs4 import BeautifulSoup

            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            
            if 'url' not in params:
                self.wfile.write(json.dumps({"error": "No URL provided"}).encode('utf-8'))
                return

            target_url = params['url'][0]
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
            res = requests.get(target_url, headers=headers, timeout=15)
            
            html_text = res.text
            soup = BeautifulSoup(html_text, 'html.parser')
            
            p_id, p_name, exam_name = "UNKNOWN", "UNKNOWN", "UNKNOWN"
            
            # 1. 🚀 PRO MAX LOGIC: Extract Meta Data from main-info-pnl
            main_info = soup.find('div', class_='main-info-pnl')
            if main_info:
                for row in main_info.find_all('tr'):
                    cells = [td.get_text(strip=True) for td in row.find_all('td')]
                    if len(cells) >= 2:
                        key = cells[0].upper()
                        val = cells[1]
                        if 'PARTICIPANT ID' in key: p_id = val
                        elif 'PARTICIPANT NAME' in key: p_name = val
                        elif 'SUBJECT' in key: exam_name = val

            # Hardcore Regex Fallback for Subject
            if exam_name == "UNKNOWN":
                m_subj = re.search(r'>\s*Subject\s*<.*?>\s*(.*?)\s*<', html_text, re.I)
                if m_subj: exam_name = m_subj.group(1).strip()

            all_sections_data = {}
            total_questions_count = 0

            # 2. 🚀 NEW LOGIC: Loop through Parts/Sections (Part A, Part B, etc.)
            for section in soup.find_all('div', class_='section-cntnr'):
                # Get the section name (e.g., "Part A Reasoning...")
                sec_lbl = section.find('div', class_='section-lbl')
                if sec_lbl:
                    sec_name_tag = sec_lbl.find(class_='bold')
                    section_name = sec_name_tag.text.strip() if sec_name_tag else "General"
                else:
                    section_name = "General"

                parsed_questions = {}

                # 3. 🚀 Loop through Questions ONLY inside this section
                for q_pnl in section.find_all('div', class_='question-pnl'):
                    try:
                        # --- A. Get Data from Right Menu Table (menu-tbl) ---
                        menu_tbl = q_pnl.find('table', class_='menu-tbl')
                        if not menu_tbl: continue
                        
                        qid = None
                        opts = {}
                        chosen_id = "-"
                        
                        for row in menu_tbl.find_all('tr'):
                            cells = [td.get_text(strip=True) for td in row.find_all('td')]
                            if len(cells) == 2:
                                label = cells[0]
                                val = cells[1]
                                
                                if 'Question ID' in label: qid = val
                                elif 'Option 1 ID' in label: opts['1'] = val
                                elif 'Option 2 ID' in label: opts['2'] = val
                                elif 'Option 3 ID' in label: opts['3'] = val
                                elif 'Option 4 ID' in label: opts['4'] = val
                                elif 'Chosen Option' in label:
                                    # If student chose 1, 2, 3, or 4, map it to ID. If "--", it stays "-"
                                    if val in opts: chosen_id = opts[val]

                        if not qid or not qid.isdigit(): continue

                        # --- B. Get Correct Answer from Left Table (questionRowTbl) ---
                        prov_right_id = "-"
                        row_tbl = q_pnl.find('table', class_='questionRowTbl')
                        if row_tbl:
                            # Website uses class="rightAns" for the correct option
                            right_ans_td = row_tbl.find('td', class_='rightAns')
                            if right_ans_td:
                                # Extract "3" from "3. વહેતા પાણીના..."
                                m = re.search(r'^([1-4])\.', right_ans_td.get_text(strip=True))
                                if m and m.group(1) in opts:
                                    prov_right_id = opts[m.group(1)]

                        # Save the question
                        parsed_questions[qid] = {
                            "chosen_id": chosen_id, 
                            "prov_right_id": prov_right_id
                        }
                        total_questions_count += 1
                        
                    except Exception:
                        continue
                
                # If section had valid questions, add it to our main dictionary
                if parsed_questions:
                    all_sections_data[section_name] = parsed_questions

            # 4. 🚀 Prepare Final Output with Sections
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
            
